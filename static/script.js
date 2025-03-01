
function loadParsingStats() {
    fetch('/get_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('total_users').innerText = data.total_users;
            document.getElementById('total_contacts').innerText = data.total_contacts;
            document.getElementById('total_contacts_today').innerText = data.total_contacts_today;
            document.getElementById('total_contacts_this_week').innerText = data.total_contacts_this_week;
        })
        .catch(error => console.error('Ошибка загрузки статистики парсинга:', error));
}

// Функция для загрузки статистики сообщений
function loadMessageStats() {
    fetch('/get_message_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('total_sent').innerText = data.total_sent;
            document.getElementById('first_reply').innerText = data.first_reply;
            document.getElementById('second_reply').innerText = data.second_reply;
            document.getElementById('third_reply').innerText = data.third_reply;
            document.getElementById('final_reply').innerText = data.final_reply;
        })
        .catch(error => console.error('Ошибка загрузки статистики сообщений:', error));
}

document.addEventListener("DOMContentLoaded", function() {
    console.log("Mini App загружен!");

    // Автозагрузка данных при открытии страницы
    if (window.location.pathname === "/parsing_stats") {
        fetch('/get_stats')
            .then(response => response.json())
            .then(data => {
                document.getElementById("total_users").innerText = data.total_users;
                document.getElementById("total_contacts").innerText = data.total_contacts;
                document.getElementById("total_contacts_today").innerText = data.total_contacts_today;
                document.getElementById("total_contacts_this_week").innerText = data.total_contacts_this_week;
            });
    }
});

document.querySelector("form").addEventListener("submit", function(event) {
    let valid = true;
    
    // Проверка на пустое сообщение
    const messageFields = document.querySelectorAll("textarea");
    messageFields.forEach(function(field) {
        if (field.value.trim() === "") {
            alert("Пожалуйста, заполните все поля для сообщений!");
            valid = false;
        }
    }); 

    if (!valid) {
        event.preventDefault();
    }
});
