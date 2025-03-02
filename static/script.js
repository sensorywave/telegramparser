// Функции загрузки статистики
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

// Единый обработчик, который срабатывает, когда DOM загружен
document.addEventListener("DOMContentLoaded", function() {
    console.log("Mini App загружен!");

    // Если мы на странице /parsing_stats, то сразу грузим статистику
    if (window.location.pathname === "/parsing_stats") {
        loadParsingStats();
    }

    // Если есть форма на странице, делаем проверку на пустые поля
    const form = document.querySelector("form");
    if (form) {
        form.addEventListener("submit", function(event) {
            let valid = true;
            // Проверка текстовых полей (например, textarea)
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
    }

    // Переключатель темы (тёмная/светлая)
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('change', () => {
            if (themeToggle.checked) {
                document.body.classList.add('dark-mode');
                // При желании: localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                // При желании: localStorage.setItem('theme', 'light');
            }
        });
    }
});