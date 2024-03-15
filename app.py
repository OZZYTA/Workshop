import os
import unicodedata
import requests
from flask import Flask, request, render_template, send_from_directory
import openai
import re
import csv
import json
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Configuración Azure OpenAI Service API

openai.api_type = os.getenv('OPENAI_API_TYPE')
openai.api_version = os.getenv('OPENAI_API_VERSION')
openai.api_base = os.getenv('OPENAI_API_BASE')
openai.api_key = os.getenv("OPENAI_API_KEY")
deployment_id = os.getenv("DEPLOYMENT_ID")
search_endpoint = os.getenv("SEARCH_ENDPOINT")
search_key = os.getenv("SEARCH_KEY")
search_index_name = os.getenv("SEARCH_INDEX_NAME")
embedding_endpoint=os.getenv("EMBEDDING_ENDPOINT")
embedding_key=os.getenv("OPENAI_API_KEY")

def setup_byod(deployment_id: str) -> None:

    class BringYourOwnDataAdapter(requests.adapters.HTTPAdapter):

        def send(self, request, **kwargs):
            request.url = f"{openai.api_base}/openai/deployments/{deployment_id}/extensions/chat/completions?api-version={openai.api_version}"
            return super().send(request, **kwargs)

    session = requests.Session()

    # Montar un adaptador personalizado que utilizará el punto final de extensiones para cualquier llamada utilizando el `deployment_id` dado.
    session.mount(
        prefix=f"{openai.api_base}/openai/deployments/{deployment_id}",
        adapter=BringYourOwnDataAdapter()
    )

    openai.requestssession = session

def remove_doc_fields(response):
    # Define el patrón de los campos [docX] donde X es un número
    pattern = r'\[doc\d+\]'

    # Utiliza re.sub para eliminar los campos [docX] y su contenido
    cleaned_response = re.sub(pattern, '', response)

    return cleaned_response

def extract_urls_from_response(completion, max_urls=2):
    urls = []

    # Revisa si hay mensajes de la herramienta en la respuesta
    for choice in completion['choices']:
        if 'context' in choice['message'] and 'messages' in choice['message']['context']:
            for message in choice['message']['context']['messages']:
                if message['role'] == 'tool':
                    # Analiza el contenido del mensaje de la herramienta como JSON
                    tool_content = json.loads(message['content'])

                    # Revisa si hay citas en el contenido y recopila los URLs
                    if 'citations' in tool_content:
                        for citation in tool_content['citations']:
                            if 'url' in citation and len(urls) < max_urls:
                                urls.append(citation['url'])
                                if len(urls) == max_urls:
                                    break

    # Retorna los URLs encontrados (hasta un máximo de 2)
    return urls

def mantener_historial(historial):
    while len(historial)>7:
        del historial[1]
        
# generar una respuesta
def generate_response(prompt, history, system):
    history.append({"role":"user","content":prompt})
    # Construye el mensaje completo para enviar a OpenAI
    messages = history

    completion = openai.ChatCompletion.create(
        messages=messages,  # mensajes filtrados
        max_tokens=400,
        temperature=0.3,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        deployment_id=deployment_id,
        dataSources=[{
            "type": "AzureCognitiveSearch",
            "parameters": {
                "endpoint": search_endpoint,
                "key": search_key,
                "indexName": search_index_name,
                "roleInformation": system,
                "queryType": "vectorSemanticHybrid",
                "semanticConfiguration":"default",
                "embeddingEndpoint": embedding_endpoint,
                "embeddingKey": embedding_key,
                "inScope": True
            }
        }]
    )

    response = completion.choices[0].message.content

    # Agrega la respuesta del asistente al historial de conversación
    assistant_message = {"role": "assistant", "content": response}
    history.append(assistant_message)
    response = unicodedata.normalize('NFKD', response)
    response = remove_doc_fields(assistant_message["content"])
    mantener_historial(history)
    
    return response, completion

def handle_feedback(user_message, bot_response, feedback):
    if feedback == "OK":
        save_feedback(user_message, bot_response, "OK")
    elif feedback == "Not OK":
        save_feedback(user_message, bot_response, "Not OK")

# Inicializar el historial de conversaciones
system=os.getenv("SYSTEM_MESSAGE")
history=[{"role":"system","content":system}]

#Setea el modelo desplegado
setup_byod(deployment_id)



@app.route('/')
def home():
    history.clear()  # Utiliza clear() para borrar el historial correctamente
    history.append({"role": "system", "content": system})  # Vuelve a agregar el mensaje de sistema
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form['user_input']
    output, completion = generate_response(user_input, history, system)
    urls = extract_urls_from_response(completion)

    frases_clave = [
        "¿Te interesaría saber más sobre", "puedo referirte a documentos relacionados",
        "La información recuperada no proporciona", "The requested information is not available",
        "Lo siento", "no esta disponible","The requested","please"
    ]

    if any(frase in output for frase in frases_clave):
        output = "Actualmente no cuento con esa información. Mis bases de conocimiento se están actualizando rápidamente. Por favor, pregunta sobre otro tema."
        urls = []

    # Eliminar URLs duplicadas
    urls = list(set(urls))

    return {"response": output, "urls": urls}

@app.route('/feedback', methods=['POST'])
def feedback():
    user_message = request.form['user_message']
    bot_response = request.form['bot_response']
    feedback = request.form['feedback']
    
    handle_feedback(user_message, bot_response, feedback)
    
    return {"response": "Feedback saved"}


@app.route('/clear-chat', methods=['POST'])
def clear_chat():
    history.clear()  # Utiliza clear() para borrar el historial correctamente
    history.append({"role": "system", "content": system})  # Vuelve a agregar el mensaje de sistema
    return {"response": "Chat cleared"}

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

def save_feedback(user_message, bot_response, feedback):
    with open('static/feedback.csv', mode='a', newline='', encoding='utf-8') as feedback_file:
        feedback_writer = csv.writer(feedback_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        feedback_writer.writerow([user_message, bot_response, feedback])


if __name__ == '__main__':
    app.run()