import asyncio
import sqlite3
import logging
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.errors import SessionPasswordNeededError, ApiIdInvalidError

# Настройка логгирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройки API для бота-парсера и ботов-рассыльщиков
parser_api_id = 12787968
parser_api_hash = '6ebd64c506b792c344d0ee2f9c120368'

sender1_api_id = 8473428
sender1_api_hash = 'a88e8e782d29fb0a97825f4c1cbfc143'

sender2_api_id = 12787968
sender2_api_hash = '6ebd64c506b792c344d0ee2f9c120368'

GROUP_TO_PARSE = '@chatikVB'
MAX_PARTICIPANTS = 100

# Создание клиентов
parser_bot = TelegramClient('parser_bot_session', parser_api_id, parser_api_hash)
sender_bot1 = TelegramClient('sender_bot1_session', sender1_api_id, sender1_api_hash)
sender_bot2 = TelegramClient('sender_bot2_session', sender2_api_id, sender2_api_hash)

# Подключение к базе данных
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Создание таблицы для хранения ID и username пользователей
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, processed INTEGER DEFAULT 0)''')

# Добавление столбца username в таблицу users
try:
    cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    conn.commit()
    logger.info("Столбец 'username' успешно добавлен в таблицу 'users'")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        logger.info("Столбец 'username' уже существует в таблице 'users'")
    else:
        logger.error(f"Ошибка при добавлении столбца 'username': {e}")

async def parse_group():
    try:
        async with parser_bot:
            channel = await parser_bot.get_entity(GROUP_TO_PARSE)
            offset = 0
            limit = 100
            all_participants = []

            while len(all_participants) < MAX_PARTICIPANTS:
                participants = await parser_bot(GetParticipantsRequest(
                    channel, ChannelParticipantsSearch(''), offset=offset, limit=limit, hash=0
                ))
                if not participants.users:
                    break
                all_participants.extend(participants.users[:MAX_PARTICIPANTS - len(all_participants)])
                offset += len(participants.users)
                logger.info(f"Получено {len(all_participants)} участников")
                
                if len(all_participants) >= MAX_PARTICIPANTS:
                    break

            parsed_count = 0
            for user in all_participants:
                cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
                               (user.id, user.username))
                parsed_count += 1

            conn.commit()
            logger.info(f"Парсер обработал {parsed_count} участников из группы {channel.title}")

    except Exception as e:
        logger.error(f"Ошибка при парсинге группы: {e}")

async def send_messages(bot, message, bot_name):
    try:
        async with bot:
            for _ in range(3):
                cursor.execute("SELECT user_id, username FROM users WHERE processed = 0 ORDER BY RANDOM() LIMIT 1")
                user = cursor.fetchone()
                if user:
                    user_id, username = user
                    try:
                        if username:
                            await bot.send_message(username, message)
                        else:
                            await bot.send_message(user_id, message)
                        cursor.execute("UPDATE users SET processed = 1 WHERE user_id = ?", (user_id,))
                        conn.commit()
                        logger.info(f"{bot_name}: Отправлено сообщение пользователю {username or user_id}")
                    except Exception as e:
                        logger.error(f"{bot_name}: Ошибка при отправке сообщения пользователю {username or user_id}: {e}")
                await asyncio.sleep(20)  # Пауза между отправками
    except ApiIdInvalidError:
        logger.error(f"{bot_name}: Неверный API ID или API Hash")
    except SessionPasswordNeededError:
        logger.error(f"{bot_name}: Требуется пароль двухфакторной аутентификации")
    except Exception as e:
        logger.error(f"{bot_name}: Неожиданная ошибка: {e}")

async def main():
    await parse_group()
    
    message = input("Введите сообщение для рассылки: ")
    
    while True:
        await send_messages(sender_bot1, message, "Бот 1")
        logger.info("Ожидание 20 секунд перед сменой бота...")
        await asyncio.sleep(20)  # Ожидание 20 секунд перед сменой бота
        
        await send_messages(sender_bot2, message, "Бот 2")
        logger.info("Ожидание 20 секунд перед сменой бота...")
        await asyncio.sleep(20)  # Ожидание 20 секунд перед сменой бота
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE processed = 0")
        remaining = cursor.fetchone()[0]
        if remaining == 0:
            logger.info("Все пользователи обработаны")
            break
        else:
            logger.info(f"Осталось обработать {remaining} пользователей")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        conn.close()
