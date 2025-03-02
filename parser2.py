import asyncio
import sqlite3
import logging
import random
import os
from telethon import TelegramClient, events

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

last_sent_iteration = {}  # Ключ: user_id, значение: номер последней отправленной итерации

# Конфигурация ботов с заранее заданными номерами телефонов
BOTS = [
    {
        "name": "Бот 1",
        "api_id": 28003573,
        "api_hash": "18f000a0ea5059fa6d22618ca51f0af2",
        "phone": "+6283848520427"
    },
    {
        "name": "Бот 2",
        "api_id": 12787968,
        "api_hash": "6ebd64c506b792c344d0ee2f9c120368",
        "phone": "+79782944193"
    }
]

# Списки для приветственного сообщения
GREETING_WORDS = ["Привет", "Здравствуйте", "Добрый день", "Приветствую", "Салют", "Хеллоу"]
EMOJIS = ["😊", "👋", "🌟", "🚀", "🎯", "⚡️", "🔥", "💎"]

###########################
# Работа с базой данных
###########################

def get_db_connection():
    conn = sqlite3.connect("participants.db")
    conn.row_factory = sqlite3.Row
    return conn

# Создание/инициализация таблиц
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    # Таблица шаблонов сообщений должна уже существовать – полей: iteration, message_type, message_content, wait_for_reply, file_path, (video_category если нужно)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS message_templates (
            iteration INTEGER PRIMARY KEY,
            message_type TEXT DEFAULT 'text',
            message_content TEXT DEFAULT NULL,
            wait_for_reply INTEGER DEFAULT 0,
            file_path TEXT DEFAULT NULL,
            video_category TEXT DEFAULT NULL
        )
    ''')
    # Таблица статуса рассылки
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sender_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'idle',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Если нет записей, вставляем начальный статус "idle"
    cur.execute("SELECT COUNT(*) FROM sender_status")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO sender_status (status) VALUES ('idle')")
    # Таблица для хранения пользователей, которым уже отправлено сообщение
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sent_users (
            user_id TEXT PRIMARY KEY,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Все таблицы инициализированы.")


def get_message_templates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM message_templates ORDER BY iteration ASC")
    templates = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return templates

def get_sender_status():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM sender_status LIMIT 1")
        return cursor.fetchone()["status"]

def update_sender_status(new_status):
    with get_db_connection() as conn:
        conn.execute("UPDATE sender_status SET status = ?", (new_status,))
        conn.commit()
    logger.info(f"Статус рассылки обновлен на '{new_status}'")

def is_user_sent(user_id):
    """Проверяет, находится ли пользователь в таблице sent_users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_users WHERE user_id = ?", (str(user_id),))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_sent_user(user_id, username):
    """Добавляет пользователя в таблицу sent_users, чтобы не повторять рассылку."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO sent_users (user_id, username) VALUES (?, ?)", (str(user_id), username))
    conn.commit()
    conn.close()
    
def save_message(iteration, message_text, user_id=None, username=None):
    """Сохраняет сообщение в таблицу messages."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (user_id, username, iteration, message_text)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, iteration, message_text))
    conn.commit()
    conn.close()
    logger.info(f"Сообщение записано в таблицу messages. Итерация: {iteration}, Текст: {message_text}")

###########################
# Отправка сообщений
###########################

async def send_message_or_file(client, user_id, template):
    message_type = template.get("message_type", "text").lower()
    message_content = template.get("message_content", "")
    file_path = template.get("file_path", "")

    try:
        if message_type == "photo" and file_path:
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                logger.error(f"Файл не найден: {abs_path}")
                return
            await client.send_file(user_id, abs_path, caption=message_content)
            logger.info(f"Фото отправлено пользователю {user_id}. Файл: {abs_path}")
        else:
            await client.send_message(user_id, message_content)
            logger.info(f"Сообщение отправлено пользователю {user_id}. Текст: {message_content}")

        # Обновляем последнюю отправленную итерацию для пользователя
        last_sent_iteration[user_id] = template["iteration"]
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения для пользователя {user_id}: {e}")
    message_type = template.get("message_type", "text").lower()
    message_content = template.get("message_content", "")
    file_path = template.get("file_path", "")

    try:
        if message_type == "photo" and file_path:
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                logger.error(f"Файл не найден: {abs_path}")
                return
            await client.send_file(user_id, abs_path, caption=message_content)
            logger.info(f"Фото отправлено пользователю {user_id}. Файл: {abs_path}")
        else:
            await client.send_message(user_id, message_content)
            logger.info(f"Сообщение отправлено пользователю {user_id}. Текст: {message_content}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения для пользователя {user_id}: {e}")

async def wait_for_reply(client, user_id, timeout=300):
    future = asyncio.Future()
    @client.on(events.NewMessage(from_users=user_id))
    async def reply_handler(event):
        if not future.done():
            future.set_result(event.message.message)
        client.remove_event_handler(reply_handler, events.NewMessage)
    try:
        reply = await asyncio.wait_for(future, timeout=timeout)
        return reply
    except asyncio.TimeoutError:
        client.remove_event_handler(reply_handler, events.NewMessage)
        return None

###########################
# Клиенты Телеграма
###########################

clients = {}  # Словарь вида {bot_name: client}
pending_iterations = {}  # Ключ: user_id, значение: индекс следующей итерации

async def ensure_clients():
    for bot in BOTS:
        session_name = f"session_{bot['name']}"
        if bot['name'] not in clients:
            client = TelegramClient(session_name, bot["api_id"], bot["api_hash"])
            await client.start(phone=bot["phone"])
            logger.info(f"{bot['name']} успешно авторизован.")
            clients[bot['name']] = client
            client.add_event_handler(on_new_message, events.NewMessage)
    return clients

async def on_new_message(event):
    try:
        # Получаем текст сообщения
        message_text = event.message.message

        # Определяем номер итерации (по умолчанию 0, если информация недоступна)
        iteration = last_sent_iteration.get(event.sender_id, 0) if event.sender_id else 0

        # Проверяем, доступна ли информация о пользователе
        if event.sender is not None:  # Проверяем, что event.sender не равен None
            user_id = event.sender_id
            username = event.sender.username if event.sender.username else f"user_{user_id}"
        else:
            user_id = None
            username = None

        # Записываем в базу данных
        save_message(iteration, message_text, user_id, username)
        logger.info(f"Сообщение записано в таблицу messages. Итерация: {iteration}, Текст: {message_text}")
    except Exception as e:
        logger.error(f"Ошибка при обработке нового сообщения: {e}")
        return
async def process_pending_message(client, user_id, start_index):
    await asyncio.sleep(20)
    templates = get_message_templates()
    for i in range(start_index, len(templates)):
        template = templates[i]
        await send_message_or_file(client, user_id, template)
        logger.info(f"(pending) Отправлена итерация {template['iteration']} пользователю {user_id}.")
        if int(template.get("wait_for_reply", 0)) == 1:
            pending_iterations[user_id] = i + 1
            break
        else:
            await asyncio.sleep(5)

###########################
# Основной цикл рассылки
###########################

async def round_robin_sending():
    await ensure_clients()
    templates = get_message_templates()
    
    while True:
        if get_sender_status() != "active":
            logger.info("Рассылка не активна. Ожидание активации...")
            await asyncio.sleep(5)
            continue
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM users")
            users = [dict(row) for row in cursor.fetchall()]
        
        if not users:
            logger.info("Нет пользователей для рассылки. Ожидание 60 секунд...")
            await asyncio.sleep(60)
            continue
        
        logger.info(f"Начинаем рассылку для {len(users)} пользователей.")
        
        for idx, user in enumerate(users):
            # Проверяем, если пользователь уже получил сообщение, пропускаем его
            if is_user_sent(user["user_id"]):
                logger.info(f"Пользователь {user['username'] or user['user_id']} уже получил сообщение. Пропускаем.")
                continue

            bot_names = list(clients.keys())
            bot_name = bot_names[idx % len(bot_names)]
            client = clients[bot_name]
            user_identifier = user["username"] or str(user["user_id"])
            logger.info(f"{bot_name} обрабатывает пользователя {user_identifier}.")

            # Отправка приветственного сообщения
            greeting_message = f"{random.choice(GREETING_WORDS)}! {random.choice(EMOJIS)}"
            try:
                await client.send_message(user_identifier, greeting_message)
                logger.info(f"{bot_name}: Приветственное сообщение отправлено пользователю {user_identifier}.")
            except Exception as e:
                logger.error(f"{bot_name}: Ошибка отправки приветственного сообщения пользователю {user_identifier}: {e}")
            
            # После отправки приветственного сообщения добавляем пользователя в таблицу, чтобы не отправлять повторно
            add_sent_user(user["user_id"], user.get("username"))
            
            # Отправка итераций шаблонов
            for i, template in enumerate(templates):
                await send_message_or_file(client, user_identifier, template)
                if int(template.get("wait_for_reply", 0)) == 1:
                    logger.info(f"{bot_name}: Шаблон итерации {template['iteration']} требует ожидания ответа для пользователя {user_identifier}.")
                    pending_iterations[int(user["user_id"])] = i + 1
                    break
                else:
                    await asyncio.sleep(5)
        
        update_sender_status("idle")
        logger.info("Рассылка завершена для всех пользователей, статус переключен в 'idle'.")
        await asyncio.sleep(5)

async def main():
    await round_robin_sending()

if __name__ == '__main__':
    try:
        create_tables()
        # Создаем таблицу sent_users, если её ещё нет
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sent_users (
                user_id TEXT PRIMARY KEY,
                username TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Таблица sent_users и другие таблицы инициализированы.")
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Рассылка полностью остановлена.")
    input("Нажмите Enter, чтобы выйти...")
