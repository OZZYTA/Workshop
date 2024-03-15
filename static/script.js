// static/script.js

document.addEventListener('DOMContentLoaded', function () {
    const chatHistory = document.getElementById('chat-history');
    const userMessageInput = document.getElementById('user-message');
    const sendButton = document.getElementById('send-button');

    sendButton.addEventListener('click', function () {
        const userMessage = userMessageInput.value;
        appendMessage('user', userMessage);
        userMessageInput.value = ''; // Limpiar el campo de entrada

        // Enviar la pregunta al servidor y obtener la respuesta del chatbot
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `user_message=${encodeURIComponent(userMessage)}`,
        })
        .then(response => response.text())
        .then(responseData => {
            // Mostrar la respuesta del chatbot en el historial de chat
            appendMessage('bot', responseData);
        })
        .catch(error => console.error('Error:', error));
    });

    // Función para agregar mensajes al historial de chat
    function appendMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        messageDiv.textContent = content;
        chatHistory.appendChild(messageDiv);

        // Desplazarse automáticamente hacia abajo para mostrar el mensaje más reciente
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
});
