import sqlite3
import telethon
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, Channel
from telethon.errors.rpcerrorlist import UserIsBlockedError, UserPrivacyRestrictedError, PeerIdInvalidError
from app import get_db_connection, get_statistics, get_message_statistics
import os
from telethon.errors import FloodWaitError
import time
from datetime import datetime, timedelta
import logging
from app import init_db, get_db_connection, get_statistics, get_message_statistics
# -----------------------------
# ДАННЫЕ ДЛЯ TELETHON
# -----------------------------
api_id = '28003573'
api_hash = '18f000a0ea5059fa6d22618ca51f0af2'
channel_username = "bot_prover"  # Имя вашего канала б  ез @

client = TelegramClient('session_name', api_id, api_hash)
# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
users_cleared = False


   


# Функция для сохранения пользователей в базу данных
# Функция для подключения к базе данных
def get_db_connection():
    return sqlite3.connect('participants.db')

# Функция для сохранения пользователей в базу данных
async def save_users_to_db(users, parse_mode, chat_link):
    global users_cleared  # Используем глобальную переменную

    conn = get_db_connection()
    cursor = conn.cursor()

    # Очищаем таблицу users только один раз, если это еще не было сделано
    if not users_cleared:
        logger.info("Очистка таблицы users перед сохранением новых данных.")
        cursor.execute("DELETE FROM users")
        conn.commit()
        logger.info("Таблица users успешно очищена.")
        users_cleared = True  # Устанавливаем флаг, чтобы больше не очищать

    # Создаем таблицу users, если её нет
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, 
                       first_name TEXT, last_name TEXT, phone TEXT, 
                       parse_mode TEXT, chat_link TEXT)''')
    
    for user in users:
        try:
            cursor.execute('''INSERT OR REPLACE INTO users 
                              (user_id, username, first_name, last_name, phone, parse_mode, chat_link) 
                              VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                           (user.id, user.username, user.first_name, user.last_name, user.phone, parse_mode, chat_link))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при сохранении пользователя {user.id}: {e}")
            continue  # Переходим к следующему пользователю
    
    logger.info(f"Сохранено {len(users)} пользователей в базу данных")
    conn.close()

# -----------------------------
# НАСТРОЙКИ СООБЩЕНИЙ
# -----------------------------


#### ШАБЛОНЫ СООБЩЕНИЙ
def get_message_templates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT iteration, message_type, message_content, wait_for_reply, file_path
        FROM message_templates
        ORDER BY iteration ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    # Превратим в dict {iteration: {...}, ...}
    templates = {}
    for row in rows:
        iteration, mtype, content, wfr, fpath = row
        templates[iteration] = {
            "type": mtype,
            "content": content if content else "",
            "wait_for_reply": bool(wfr),
            "file_path": fpath
        }
    return templates

# ОТПРАВКА СЛЕДУЮЩЕЙ ИТЕРАЦИИ
# ----------------------------- 


import os
import asyncio
from telethon.errors import FloodWaitError, UserIsBlockedError, UserPrivacyRestrictedError, PeerIdInvalidError

import asyncio
import random

async def send_next_message(user_id):
    """Отправляет следующее сообщение из шаблонов пользователю с задержками."""
    # Проверяем, есть ли пользователь в базе данных и отправлялось ли ему сообщение
    if has_user_received_message(user_id):
        print(f"🚫 Пользователь {user_id} уже получил сообщение. Пропускаем.")
        return

    while True:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT iteration FROM messages WHERE user_id=? ORDER BY iteration DESC LIMIT 1", (user_id,))
        last_iteration = cursor.fetchone()
        current_iteration = last_iteration[0] if last_iteration else 0
        conn.close()

        templates = get_message_templates()
        if not templates:
            print(f"🚫 Нет шаблонов сообщений в базе данных для пользователя {user_id}.")
            return

        # Ищем следующую непустую итерацию
        next_iteration = None
        for it in sorted(templates.keys()):
            if it > current_iteration:
                tpl = templates[it]
                message_content = tpl["content"]
                if message_content:  # Проверяем, что сообщение не пустое
                    next_iteration = it
                    break

        if not next_iteration:
            print(f"🚫 У пользователя {user_id} нет следующих непустых сообщений.")
            return  # Переходим к следующему пользователю

        tpl = templates[next_iteration]
        message_type = tpl["type"]
        message_content = tpl["content"]
        wait_for_reply = tpl["wait_for_reply"]
        file_path = tpl.get("file_path")  # Файл может быть None, если не указан

        print(f"➡️ Отправляем итерацию {next_iteration} пользователю {user_id} (type={message_type}).")

        try:
            # Разбиваем сообщение на части (если оно длинное)
            parts = message_content.split(". ")  # Разделяем по точкам
            if not parts:
                parts = [message_content]

            for part in parts:
                if not part.strip():
                    continue

                # Отправляем часть сообщения
                if file_path is not None and os.path.exists(file_path):
                    # Отправляем файл с текстовым сообщением
                    await client.send_file(user_id, file_path, caption=part.strip() + ".")
                    print(f"✅ Файл {file_path} отправлен {user_id}.")
                else:
                    # Отправляем просто текстовое сообщение
                    await client.send_message(user_id, part.strip() + ".")
                    print(f"✅ Сообщение отправлено {user_id}.")

                # Случайная задержка между частями (от 5 до 15 секунд)
                delay = random.randint(5, 15)
                await asyncio.sleep(delay)

            # Логируем отправку сообщения
            log_message(user_id, message_content, iteration=next_iteration, replied=0)

            # Задержка после отправки всего сообщения (от 10 до 20 секунд)
            final_delay = random.randint(10, 20)
            await asyncio.sleep(final_delay)

            if wait_for_reply:
                break  # Прерываем цикл, если нужно ждать ответа

        except FloodWaitError as e:
            print(f"⚠️ Ошибка FloodWait: ждём {e.seconds} секунд...")
            await asyncio.sleep(e.seconds)  # Ждём указанное время
        except UserIsBlockedError:
            set_user_blocked(user_id)
            print(f"🚫 Пользователь {user_id} нас заблокировал.")
            break
        except UserPrivacyRestrictedError:
            set_user_blocked(user_id)
            print(f"🚫 Приватность у {user_id}.")
            break
        except PeerIdInvalidError:
            set_user_blocked(user_id)
            print(f"🚫 PeerIdInvalidError.")
            break
        except Exception as e:
            print(f"⚠️ Ошибка при отправке {user_id}: {e}")
            break
# -----------------------------
# ПРИМЕР РАССЫЛКИ
#
# -----------------------------
# ФУНКЦИИ РАБОТЫ С БАЗОЙ
# -----------------------------
def has_user_received_message(user_id):
    """Проверяет, получал ли пользователь сообщение ранее."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()[0]
    conn.close()
    return result > 0

def log_message(user_id, message_text, iteration=None, replied=0):
    """Логируем отправленные сообщения в базе данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (user_id, message_text, sent_date, final_status, iteration, replied)
        VALUES (?, ?, CURRENT_TIMESTAMP, "pending", ?, ?)
    ''', (user_id, message_text, iteration, replied))
    conn.commit()
    conn.close()
def set_user_blocked(user_id):
    """Отмечаем пользователя как заблокированного"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE messages
        SET final_status = "blocked"
        WHERE user_id = ? AND final_status = "pending"
    ''', (user_id,))
    conn.commit()
    conn.close()

def update_joined_count(user_id):
    """Обновляем статус пользователя как вступившего"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE messages
        SET final_status = "joined"
        WHERE user_id = ? AND final_status = "pending"
    ''', (user_id,))
    conn.commit()
    conn.close()

def get_joined_count():
    """Получаем количество пользователей, которые вступили в канал"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE final_status = 'joined'")
    joined_count = cursor.fetchone()[0] or 0
    conn.close()
    return joined_count




def update_parsed_data(group_name, total_members, new_contacts):
    """Обновляет данные о парсинге в таблице parsed_data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Получаем текущую дату и дату начала недели
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Начало текущей недели (понедельник)

    # Проверяем, есть ли запись для этой группы
    cursor.execute("SELECT total_contacts, collected_date FROM parsed_data WHERE group_name = ?", (group_name,))
    result = cursor.fetchone()

    if result:
        # Если запись существует, обновляем её
        total_contacts, last_collected_date = result
        total_contacts += new_contacts

        # Убедимся, что total_contacts не превышает total_members
        if total_contacts > total_members:
            total_contacts = total_members

        # Обновляем данные за день и за неделю
        if last_collected_date == today:
            cursor.execute('''
                UPDATE parsed_data
                SET total_contacts = ?,
                    total_members = ?,
                    collected_date = ?,
                    contacts_today = contacts_today + ?,
                    contacts_this_week = contacts_this_week + ?
                WHERE group_name = ?
            ''', (total_contacts, total_members, today, new_contacts, new_contacts, group_name))
        else:
            # Если последняя дата сбора не сегодня, обнуляем contacts_today
            cursor.execute('''
                UPDATE parsed_data
                SET total_contacts = ?,
                    total_members = ?,
                    collected_date = ?,
                    contacts_today = ?,
                    contacts_this_week = contacts_this_week + ?
                WHERE group_name = ?
            ''', (total_contacts, total_members, today, new_contacts, new_contacts, group_name))
    else:
        # Если записи нет, создаем новую
        # Убедимся, что new_contacts не превышает total_members
        if new_contacts > total_members:
            new_contacts = total_members

        cursor.execute('''
            INSERT INTO parsed_data (group_name, total_contacts, total_members, collected_date, contacts_today, contacts_this_week)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (group_name, new_contacts, total_members, today, new_contacts, new_contacts))

    conn.commit()
    conn.close()
    
    
def get_bot_settings():
    """Получает настройки бота из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            send_period,
            contacts_count
        FROM sender_bot_settings
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        send_period, contacts_count = row
    else:
        send_period = 20 * 60  # Значение по умолчанию: 20 минут
        contacts_count = 100   # Значение по умолчанию: 100 контактов

    return send_period, contacts_count
# -----------------------------
# ФУНКЦИИ ОТПРАВКИ/ПРОВЕРКИ
# -----------------------------
async def check_if_user_joined(user_id):
    """Проверяем, вступил ли пользователь в канал, через некоторое время"""
    await asyncio.sleep(10)
    try:
        channel = await client.get_entity(channel_username)
        participants = await client.get_participants(channel)
        user_ids = {p.id for p in participants}
        if user_id in user_ids:
            update_joined_count(user_id)
    except Exception as e:
        print(f"Ошибка check_if_user_joined: {e}")

import asyncio
import os
from telethon.tl.types import PeerChannel, Channel
from telethon.errors import UserIsBlockedError, UserPrivacyRestrictedError

"""async def send_message_to_commentators(channel_username):
    Получаем комментарии к постам канала и отправляем сообщение пользователям, которые оставили комментарий.
    try:
        channel = await client.get_entity(channel_username)
        if not isinstance(channel, (PeerChannel, Channel)):
            print(f"❌ Не удалось получить канал: {channel_username}")
            return

        # Получаем шаблоны сообщений
        templates = get_message_templates()
        if not templates:
            print("❌ Нет шаблонов сообщений в базе данных.")
            return

        # Ищем первую непустую итерацию
        first_template = None
        for it in sorted(templates.keys()):
            tpl = templates[it]
            message_content = tpl["content"]
            if message_content:  # Проверяем, что сообщение не пустое
                first_template = tpl
                break

        if not first_template:
            print("❌ Нет непустых шаблонов сообщений.")
            return

        message_content = first_template["content"]
        file_path = first_template.get("file_path")  # Файл может быть None, если не указан

        # Получаем последние сообщения с комментариями
        messages = await client.get_messages(channel, limit=100)  # Получаем последние 100 сообщений

        # Множество для хранения уникальных ID пользователей, оставивших комментарии
        unique_users = set()

        for message in messages:
            if message.replies and message.replies.comments:  # Если есть комментарии
                comments = await client.get_messages(channel, reply_to=message.id, limit=message.replies.comments)

                for comment in comments:
                    user = comment.sender_id  # Получаем ID пользователя, который оставил комментарий

                    if user is None:
                        continue

                    # Добавляем пользователя в множество уникальных пользователей
                    unique_users.add(user)  

                    try:
                        # Проверяем, было ли уже отправлено сообщение этому пользователю
                        if has_user_received_message(user):  # Используем вашу функцию
                            print(f"⚠ Пользователь {user} уже получил сообщение.")
                            continue

                        if file_path and os.path.exists(file_path):
                            # Отправляем файл с текстовым сообщением
                            await client.send_file(user, file_path, caption=message_content)
                            print(f"✅ Файл {file_path} отправлен пользователю {user}.")
                        else:
                            # Отправляем просто текстовое сообщение
                            await client.send_message(user, message_content)
                            print(f"✅ Сообщение отправлено пользователю {user}.")

                        # Логируем отправку сообщения в базу данных
                        log_message(user, message_content)  # Используем вашу функцию

                        # Задержка 10 секунд перед отправкой следующему пользователю
                        await asyncio.sleep(10)

                    except UserIsBlockedError:
                        print(f"⚠ Пользователь {user} заблокировал бота.")
                    except UserPrivacyRestrictedError:
                        print(f"⚠ Пользователь {user} имеет ограниченный доступ.")
                    except Exception as e:
                        print(f"⚠ Ошибка при отправке сообщения пользователю {user}: {e}")

        # Обновляем данные о канале в parsed_data
        total_users = len(unique_users)  # Общее количество уникальных пользователей
        update_parsed_data(channel_username, total_users, total_users)  # Обновляем parsed_data

    except Exception as e:
        print(f"Ошибка при обработке комментариев: {e}")"""

async def get_discussion_group(channel_link):
    """Получает связанную группу обсуждения для канала."""
    try:
        # Получаем сущность канала
        channel = await client.get_entity(channel_link)
        
        # Проверяем, есть ли связанная группа обсуждения
        if hasattr(channel, 'linked_chat_id'):
            discussion_group = await client.get_entity(channel.linked_chat_id)
            return discussion_group
        else:
            print(f"У канала {channel_link} нет связанной группы обсуждения.")
            return None
    except Exception as e:
        print(f"Ошибка при получении группы обсуждения: {e}")
        return None
    
    

# -----------------------------
# ПАРСИНГ УЧАСТНИКОВ И КОММЕНТАТОРОВ



# -----------------------------

async def process_commentators(channel_link, min_comments=0):
    """Парсинг комментаторов канала."""
    try:
        channel = await client.get_entity(channel_link)
        logger.info(f"Сущность канала {channel_link} получена.")
    except Exception as e:
        logger.error(f"Ошибка при получении канала {channel_link}: {e}")
        return

    commentators = {}
    try:
        # Получаем последние сообщения канала
        messages = await client.get_messages(channel, limit=100)  # Можно увеличить лимит при необходимости
        
        for message in messages:
            if message.replies:
                # Получаем комментарии к сообщению
                comments = await client.get_messages(channel, reply_to=message.id)
                for comment in comments:
                    if comment.sender_id:
                        commentators[comment.sender_id] = commentators.get(comment.sender_id, 0) + 1

        # Фильтруем комментаторов по минимальному количеству комментариев
        active_commentators = [user_id for user_id, count in commentators.items() if count >= min_comments]
        
        # Получаем информацию о пользователях
        users = []
        for user_id in active_commentators:
            try:
                user = await client.get_entity(user_id)
                users.append(user)
            except Exception as e:
                logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")

        logger.info(f"Найдено комментаторов: {len(users)}")
        await save_users_to_db(users, 'commentators', channel_link)

    except Exception as e:
        logger.error(f"Ошибка при парсинге комментаторов канала {channel_link}: {e}")
        
        
        
async def get_participants_by_mode(chat_link, parse_mode, min_msgs, channel=False):
    """Парсинг участников группы или канала с учетом режима."""
    MAX_PARTICIPANTS = 100  # Ограничение на количество участников

    try:
        logger.info(f"Попытка получить сущность для {chat_link}...")
        entity = await client.get_entity(chat_link)
        logger.info(f"Сущность получена: {entity}")
    except Exception as e:
        logger.error(f"Ошибка при получении {chat_link}: {e}")
        return

    if parse_mode == 'all_members':
        logger.info("Режим: all_members")
        participants = []
        async for user in client.iter_participants(entity, limit=MAX_PARTICIPANTS):
            participants.append(user)
        logger.info(f"Найдено участников: {len(participants)}")
        await save_users_to_db(participants, parse_mode, chat_link)

    elif parse_mode == 'active_members':
        logger.info("Режим: active_members")
        messages = await client.get_messages(entity, limit=1000)
        user_msg_count = {}
        for msg in messages:
            if msg.sender_id:
                user_msg_count[msg.sender_id] = user_msg_count.get(msg.sender_id, 0) + 1

        active_ids = [user_id for user_id, count in user_msg_count.items() if count >= min_msgs]
        active_ids = active_ids[:MAX_PARTICIPANTS]  # Ограничиваем количество активных участников

        participants = []
        for user_id in active_ids:
            try:
                user = await client.get_entity(user_id)
                participants.append(user)
            except Exception as e:
                logger.error(f"Ошибка при получении участника {user_id}: {e}")

        logger.info(f"Найдено активных участников: {len(participants)}")
        await save_users_to_db(participants, parse_mode, chat_link)
     # Для комментаторов:
    elif parse_mode == 'commentators' and channel:
       logger.info("Режим: commentators (канал)")
       await process_commentators(chat_link, min_msgs)


    
async def get_discussion_group(channel_link):
    """Получает связанную группу обсуждения для канала."""
    try:
        # Получаем сущность канала
        channel = await client.get_entity(channel_link)
        
        # Проверяем, есть ли связанная группа обсуждения
        if hasattr(channel, 'linked_chat_id'):
            discussion_group = await client.get_entity(channel.linked_chat_id)
            return discussion_group
        else:
            print(f"У канала {channel_link} нет связанной группы обсуждения.")
            return None
    except Exception as e:
        print(f"Ошибка при получении группы обсуждения: {e}")
        return None


async def parse_discussion_participants(chat_link, min_discussion_msgs, all_participants=True):
    """Парсинг участников обсуждения канала."""
    MAX_PARTICIPANTS = 100  # Ограничение на количество участников

    try:
        entity = await client.get_entity(chat_link)
    except Exception as e:
        logger.error(f"Ошибка при получении {chat_link}: {e}")
        return

    if hasattr(entity, 'linked_chat_id'):
        try:
            discussion_chat = await client.get_entity(entity.linked_chat_id)
            participants = await client.get_participants(discussion_chat, limit=MAX_PARTICIPANTS)

            if not all_participants:
                logger.info("Парсинг активных участников обсуждения")
                messages = await client.get_messages(discussion_chat, limit=1000)
                user_msg_count = {}
                for msg in messages:
                    if msg.sender_id:
                        user_msg_count[msg.sender_id] = user_msg_count.get(msg.sender_id, 0) + 1

                active_ids = [user_id for user_id, count in user_msg_count.items() if count >= min_discussion_msgs]
                participants = [user for user in participants if user.id in active_ids][:MAX_PARTICIPANTS]

            logger.info(f"Найдено участников обсуждения: {len(participants)}")
            await save_users_to_db(participants, 'discussion', chat_link)
        except Exception as e:
            logger.error(f"Ошибка при парсинге обсуждения {chat_link}: {e}")
    else:
        logger.info(f"У канала {chat_link} нет обсуждения.")


"""async def process_participants(participants, parse_mode, chat_link, max_work_time=None):
    #Обработка участников и отправка сообщений на основе шаблонов.
    
   
    if not participants:
        print(f"Для {chat_link} список участников пуст (parse_mode={parse_mode}).")
        return

    # Получаем настройки бота из базы данных
    _, contacts_count = get_bot_settings()

    # Считаем общее кол-во и пишем в parsed_data
    total_members = len(participants)
    group_name = chat_link  # Используем ссылку на канал или группу как имя
    new_contacts = min(total_members, contacts_count)  # Ограничиваем количество контактов

    # Обновляем данные в parsed_data
    update_parsed_data(group_name, total_members, new_contacts)

    # Засекаем время начала работы
    start_time = time.time()

    # Обрабатываем только первых new_contacts участников
    for i, participant in enumerate(participants[:new_contacts]):
        # Проверяем, не превышено ли максимальное время работы
        if max_work_time and (time.time() - start_time) > max_work_time:
            print(f"Превышено максимальное время работы ({max_work_time} секунд). Остановка.")
            break

        # Фильтруем ботов и пустые first_name
        if participant.bot or not participant.first_name:
            continue

        # Проверяем, писали ли уже
        if has_user_received_message(participant.id):
            continue

        try:
            # Отправляем все сообщения из шаблонов
            await send_next_message(participant.id)
            # Запускаем проверку вступления (необязательно)
            asyncio.create_task(check_if_user_joined(participant.id))

        except UserIsBlockedError:
            set_user_blocked(participant.id)
        except UserPrivacyRestrictedError:
            set_user_blocked(participant.id)
        except PeerIdInvalidError:
            set_user_blocked(participant.id)
        except Exception as e:
            print(f"Ошибка при отправке сообщения {participant.id}: {e}")

        # Делаем паузу 20 секунд после обработки каждого пользователя
        await asyncio.sleep(20)

    # Логирование результатов
    if max_work_time and (time.time() - start_time) > max_work_time:
        print(f"Обработано {i} участников за отведенное время ({max_work_time} секунд).")
    else:
        print(f"Обработаны все {new_contacts} участников.")
    # Логирование результатов
    if max_work_time and (time.time() - start_time) > max_work_time:
        print(f"Обработано {i} участников за отведенное время ({max_work_time} секунд).")
    else:
        print(f"Обработаны все {new_contacts} участников.")"""
async def main():
    """Основной цикл для парсинга участников."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        logger.info("Получение настроек парсинга из базы данных...")
        cursor.execute("""
            SELECT
                group_link,
                channel_link,
                group_parse_mode,
                channel_parse_mode,
                min_msgs,
                min_discussion_msgs
            FROM settings
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        if rows:
            chat_links = []
            for row in rows:
                group_link, channel_link, group_parse_mode, channel_parse_mode, min_msgs, min_discussion_msgs = row
                if group_link:
                    chat_links.append((group_link, group_parse_mode, min_msgs, False))  # False = группа
                if channel_link:
                    chat_links.append((channel_link, channel_parse_mode, min_discussion_msgs, True))  # True = канал

            logger.info(f"Найдено {len(chat_links)} ссылок для парсинга.")

            for chat_link, parse_mode, min_msgs, is_channel in chat_links:
                try:
                    logger.info(f"Начинаем парсинг для: {chat_link}, режим: {parse_mode}")
                    await get_participants_by_mode(chat_link, parse_mode, min_msgs, is_channel)
                    logger.info(f"Парсинг {chat_link} завершен.")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге {chat_link}: {e}")
                    continue  # Продолжаем со следующей группой/каналом

        else:
            logger.warning("Настройки парсинга не найдены.")

    except Exception as e:
        logger.error(f"Ошибка в основном цикле: {e}")
    finally:
        logger.info("Парсинг завершен, завершение работы.")
        try:
            await client.disconnect()
            logger.info("Клиент отключен.")
        except Exception as e:
            logger.error(f"Ошибка при отключении клиента: {e}")

async def start():
    """Запускает клиент и выполняет основной цикл."""
    try:
        await client.start()
        logger.info("Клиент Telethon успешно запущен.")
        await main()
    except Exception as e:
        logger.error(f"Ошибка при запуске клиента: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(start())