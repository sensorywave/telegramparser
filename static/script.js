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

    // 1. Восстанавливаем тему из localStorage
    const themeToggle = document.getElementById('theme-toggle');
    const savedTheme = localStorage.getItem('theme') || 'light';

    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (themeToggle) {
            themeToggle.checked = true;  // устанавливаем чекбокс в положение "вкл"
        }
    }

    // 2. Если мы на странице /parsing_stats, то сразу грузим статистику
    if (window.location.pathname === "/parsing_stats") {
        loadParsingStats();
    }

    // 3. Проверяем, есть ли форма на странице (для отправки сообщений), и вешаем проверку заполнения textarea
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

    // 4. Переключатель темы (тёмная/светлая)
    if (themeToggle) {
        themeToggle.addEventListener('change', () => {
            if (themeToggle.checked) {
                // Включаем тёмную тему
                document.body.classList.add('dark-mode');
                localStorage.setItem('theme', 'dark'); 
            } else {
                // Выключаем тёмную тему
                document.body.classList.remove('dark-mode');
                localStorage.setItem('theme', 'light');
            }
        });
    }

    // 5. Логика двойного клика для логаута
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        let confirmStage = 0; 
        logoutBtn.addEventListener('click', (e) => {
            if (confirmStage === 0) {
                // Первый клик: меняем текст на "Точно хотите выйти?"
                e.preventDefault();  // Отменяем переход по ссылке/действие
                logoutBtn.textContent = "Точно хотите выйти?";
                confirmStage = 1;
            } else {
                // Второй клик: выполняем реальный выход
                window.location.href = "/logout"; 
            }
        });
    }
});