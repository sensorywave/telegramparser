from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
import random
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from threading import Thread
import subprocess
import telethon
import logging
import subprocess
from flask import flash, redirect, render_template, request, url_for
import subprocess
import telethon
import sys
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
bot_running = False

#
# Функция подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('participants.db', detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация базы данных
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Регистрируем адаптер и конвертер SQLite для datetime.date
    sqlite3.register_adapter(datetime.date, lambda date: date.isoformat())
    sqlite3.register_converter("DATE", lambda b: datetime.datetime.strptime(b.decode('ascii'), "%Y-%m-%d").date())

    # Таблица парсинга данных
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parsed_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            user_id INTEGER,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            total_contacts INTEGER DEFAULT 0,
            total_members INTEGER DEFAULT 1, 
            collected_date DATE DEFAULT (date('now'))
        )
    ''')

    # ✅ Таблица сообщений
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_text TEXT,
            sent_date TEXT DEFAULT CURRENT_TIMESTAMP,
            replied INTEGER DEFAULT 0,
            iteration INTEGER DEFAULT 1,
            final_status TEXT DEFAULT 'pending'
        )
    ''')

    # ✅ Таблица шаблонов сообщений для "Панели сборки"
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS message_templates (
            iteration INTEGER PRIMARY KEY,
            message_type TEXT DEFAULT 'text',
            message_content TEXT DEFAULT NULL,
            wait_for_reply INTEGER DEFAULT 0,
            file_path TEXT DEFAULT NULL  -- ✅ Добавляем путь к файлу
        )
    ''')
    
     # Таблица с настройками парсинга
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_link TEXT,
            channel_link TEXT,
            group_parse_mode TEXT,
            channel_parse_mode TEXT,
            min_msgs INTEGER,
            min_discussion_msgs INTEGER,
            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
         
        )
    ''')

    
    
    
     # Новая таблица для настроек бота отправителя
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS sender_bot_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            send_period INTEGER,
            contacts_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()



MAX_HISTORY_LENGTH = 20 
    
    

# 🟢 Функция получения статистики парсинга
from datetime import datetime, timedelta

def get_statistics():
    """Получает статистику из базы данных."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Общее количество групп
    cursor.execute("SELECT COUNT(DISTINCT group_name) FROM parsed_data")
    total_groups = cursor.fetchone()[0]

    # Общее количество контактов
    cursor.execute("SELECT SUM(total_contacts) FROM parsed_data")
    total_contacts = cursor.fetchone()[0] or 0

    # Контакты за день
    today = datetime.now().date()
    cursor.execute("SELECT SUM(total_contacts) FROM parsed_data WHERE collected_date = ?", (today,))
    contacts_today = cursor.fetchone()[0] or 0

    # Контакты за неделю
    start_of_week = today - timedelta(days=today.weekday())
    cursor.execute("SELECT SUM(total_contacts) FROM parsed_data WHERE collected_date >= ?", (start_of_week,))
    contacts_this_week = cursor.fetchone()[0] or 0

    # Статистика по группам
    cursor.execute("SELECT group_name, total_contacts, total_members FROM parsed_data")
    group_stats = cursor.fetchall()

    conn.close()

    return {
        "total_groups": total_groups,
        "total_contacts": total_contacts,
        "contacts_today": contacts_today,
        "contacts_this_week": contacts_this_week,
        "group_stats": group_stats,
    }

# 🟢 Функция получения статистики сообщений
def get_message_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM messages")
    total_messages = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE replied = 1")
    total_replies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE iteration = 1")
    iteration_1 = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE iteration = 2")
    iteration_2 = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE iteration = 3")
    iteration_3 = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages WHERE final_status = 'joined'")
    final_joined = cursor.fetchone()[0]

    conn.close()

    return {
        "total_messages": total_messages,
        "total_replies": total_replies,
        "iteration_1": iteration_1,
        "iteration_2": iteration_2,
        "iteration_3": iteration_3,
        "final_joined": final_joined,
    }

# ✅ Получение шаблонов сообщений
def get_message_templates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM message_templates ORDER BY iteration ASC")
    templates = cursor.fetchall()
    conn.close()
    return templates

# ✅ Обновление шаблонов сообщений
def update_message_template(iteration, message_type, message_content, wait_for_reply, file_path):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO message_templates (iteration, message_type, message_content, wait_for_reply, file_path)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(iteration) DO UPDATE SET 
        message_type = excluded.message_type,
        message_content = excluded.message_content,
        wait_for_reply = excluded.wait_for_reply,
        file_path = excluded.file_path
    ''', (iteration, message_type, message_content, wait_for_reply, file_path))

    conn.commit()
    conn.close()
    
def add_new_iteration():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO message_templates (message_type, message_content, wait_for_reply) VALUES ('text', '', 0)")
    conn.commit()
    conn.close()

# 🏠 Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# 📊 Статистика парсинга
@app.route('/parsing_stats')    
def parsing_stats():    
    stats = get_statistics()
    return render_template('parsing_stats.html', **stats)

# 📩 Статистика сообщений
@app.route('/message_stats')
def message_stats():
    stats = get_message_statistics()
    return render_template('message_stats.html', **stats)

UPLOAD_FOLDER = "./static/uploads/"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Ограничение размера файла (16 MB)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_templates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT iteration, message_type, message_content, wait_for_reply, file_path
        FROM message_templates
        ORDER BY iteration ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_single_template(iteration):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT iteration, message_type, message_content, wait_for_reply, file_path
        FROM message_templates
        WHERE iteration=?
    ''', (iteration,))
    row = cursor.fetchone()
    conn.close()
    return row

def create_or_update_template(iteration, message_type, message_content, wait_for_reply, file_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO message_templates (iteration, message_type, message_content, wait_for_reply, file_path)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(iteration) DO UPDATE SET
          message_type = excluded.message_type,
          message_content = excluded.message_content,
          wait_for_reply = excluded.wait_for_reply,
          file_path = excluded.file_path
    ''', (iteration, message_type, message_content, wait_for_reply, file_path))
    conn.commit()
    conn.close()

def delete_template(iteration):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM message_templates WHERE iteration=?', (iteration,))
    conn.commit()
    conn.close()




@app.route('/parse_settings', methods=['GET', 'POST'])
def parse_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_settings':
            # Сохраняем настройки из формы (до 5 наборов полей)
            for i in range(5):
                link = request.form.get(f'link{i}')
                # Если поле заполнено – сохраняем
                if link:
                    link_type = request.form.get(f'type{i}')
                    if link_type == 'group':
                        group_link = link
                        group_parse_mode = request.form.get(f'parse_mode{i}', 'all_members')
                        min_msgs = request.form.get(f'min_msgs{i}', 1, type=int)
                        channel_link = None
                        channel_parse_mode = None
                        min_discussion_msgs = None
                    else:
                        group_link = None
                        group_parse_mode = None
                        channel_link = link
                        channel_parse_mode = request.form.get(f'parse_mode{i}', 'commentators')
                        min_discussion_msgs = request.form.get(f'min_discussion_msgs{i}', 1, type=int)
                        min_msgs = None
                    cursor.execute('''
                        INSERT INTO settings (
                            group_link, channel_link,
                            group_parse_mode, channel_parse_mode,
                            min_msgs, min_discussion_msgs
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (group_link, channel_link, group_parse_mode, channel_parse_mode, min_msgs, min_discussion_msgs))
                    conn.commit()
            # Если количество записей превышает MAX_HISTORY_LENGTH – удаляем самые ранние
            cursor.execute(f'''
                DELETE FROM settings
                WHERE id NOT IN (
                    SELECT id FROM settings ORDER BY created_at DESC LIMIT {MAX_HISTORY_LENGTH}
                )
            ''')
            conn.commit()
            flash('Настройки успешно сохранены!', 'success')
        elif action == 'start_parsing':
            try:
                # Запуск парсера (предполагается, что файл parser.py находится в той же папке)
                parser_path = os.path.join(os.path.dirname(__file__), 'parser.py')
                subprocess.Popen(['start', 'cmd', '/k', 'python', parser_path], shell=True)
                flash('Парсинг запущен в новом терминале!', 'success')
                return redirect(url_for('parsing_stats'))
            except Exception as e:
                flash(f'Ошибка при запуске парсера: {str(e)}', 'error')
        conn.close()
        return redirect(url_for('parse_settings'))
    conn.close()
    return render_template('parse_settings.html')



# Отдельный маршрут для отображения истории настроек
@app.route('/settings_history')
def settings_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            COALESCE(group_link, channel_link) as link,
            CASE 
                WHEN group_link IS NOT NULL THEN 'Группа' 
                ELSE 'Канал' 
            END as type,
            COALESCE(group_parse_mode, channel_parse_mode) as parse_mode,
            min_msgs,
            min_discussion_msgs,
            created_at
        FROM settings
        ORDER BY created_at DESC
    ''')
    history = cursor.fetchall()
    conn.close()
    return render_template('settings_history.html', history=history)



# -- Панель (CRUD) --
@app.route('/build_panel')
def build_panel():
    all_templates = get_all_templates()
    return render_template('build_panel.html', all_templates=all_templates)
        
@app.route('/create_template', methods=['GET', 'POST'])
def create_template():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем следующий номер из БД
        cursor.execute("SELECT MAX(iteration) FROM message_templates")
        max_iter = cursor.fetchone()[0] or 0
        next_number = max_iter + 1

        # Обработка данных формы
        message_type = request.form.get('message_type', 'text')
        message_content = request.form.get('message_content', '').strip()
        wait_for_reply = 1 if request.form.get('wait_for_reply') else 0

        # Обработка файла
        file_path = None
        if message_type != 'text':
            file = request.files.get('file')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(local_path)
                file_path = os.path.abspath(local_path)

        # Сохранение в БД
        create_or_update_template(
            iteration=next_number,
            message_type=message_type,
            message_content=message_content,
            wait_for_reply=wait_for_reply,
            file_path=file_path
        )
        
        conn.commit()
        conn.close()
        
        flash(f"Сообщение №{next_number} успешно создано!", "success")
        return redirect(url_for('build_panel'))

    # GET запрос
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(iteration) FROM message_templates")
    max_iter = cursor.fetchone()[0] or 0
    next_number = max_iter + 1
    conn.close()
    
    return render_template('edit_template.html', 
                         template_data=None,
                         next_number=next_number)

@app.route('/edit_template/<int:iteration>', methods=['GET', 'POST'])
def edit_template(iteration):
    # Получаем данные из базы данных
    template_data = get_single_template(iteration)
    
    if not template_data:
        flash("Сообщение не найдено!", "error")
        return redirect(url_for('build_panel'))

    if request.method == 'POST':
        # Получаем данные из формы
        message_type = request.form.get('message_type', 'text')
        message_content = request.form.get('message_content', '').strip()
        wait_for_reply = 1 if request.form.get('wait_for_reply') else 0
        video_category = request.form.get('video_category')
        file_path = template_data[4]  # Сохраняем текущий путь к файлу

        # Обработка нового файла
        new_file = request.files.get('file')
        if new_file and allowed_file(new_file.filename):
            # Удаляем старый файл при необходимости
            if template_data[4]:
                try:
                    os.remove(template_data[4])
                except Exception as e:
                    flash(f"Ошибка удаления файла: {str(e)}", "warning")
            
            # Сохраняем новый файл
            filename = secure_filename(new_file.filename)
            local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            new_file.save(local_path)
            file_path = os.path.abspath(local_path)

        # Обновляем запись в базе данных
        create_or_update_template(
            iteration=iteration,
            message_type=message_type,
            message_content=message_content,
            wait_for_reply=wait_for_reply,
            file_path=file_path,
            video_category=video_category if message_type == 'video' else None
        )

        flash(f"Сообщение №{iteration} успешно обновлено!", "success")
        return redirect(url_for('build_panel'))

    # Преобразуем Row в словарь для шаблона
    template_dict = {
        'iteration': template_data[0],
        'message_type': template_data[1],
        'message_content': template_data[2],
        'wait_for_reply': template_data[3],
        'file_path': template_data[4],
        'video_category': template_data[5] if template_data[1] == 'video' else None
    }

    return render_template('edit_template.html', 
                         template_data=template_dict,
                         next_number=None)


@app.route('/delete_template/<int:iteration>', methods=['POST'])
def delete_template_route(iteration):
    delete_template(iteration)
    flash(f"Итерация {iteration} удалена!", "success")
    return redirect(url_for('build_panel'))
# 📊 API для статистики (JSON)
@app.route('/get_stats')
def get_stats():
    stats = get_statistics()
    return jsonify(stats)

# Роут для страницы настроек бота отправителя
@app.route('/sender_bot_settings', methods=['GET', 'POST'])
def sender_bot_settings():
    if request.method == 'POST':
        send_period = request.form.get('send_period', type=int)
        contacts_count = request.form.get('contacts_count', type=int)

        # Сохраняем настройки в базу данных
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(''' 
            INSERT INTO sender_bot_settings (send_period, contacts_count)
            VALUES (?, ?)
        ''', (send_period, contacts_count))
        conn.commit()
        conn.close()

        flash("Настройки бота отправителя успешно сохранены!", "success")
        return redirect(url_for('sender_bot_settings'))

    # Если GET-запрос, просто отображаем страницу
    return render_template('sender_bot_settings.html')

def run_bot():
    """Запускает парсер как отдельный процесс."""
    global bot_running
    bot_running = True
    try:
        subprocess.run(["python", "parser.py"], check=True) 
    except subprocess.CalledProcessError as e:
        print(f"Ошибка запуска парсера: {e}")
    finally:
        bot_running = False

@app.route('/start_bot', methods=['POST'])
def start_bot():
    """Запускает парсер в отдельном потоке."""
    global bot_running
    if not bot_running:
        thread = Thread(target=run_bot)
        thread.daemon = True  # Завершить поток при закрытии приложения
        thread.start()
        print('Парсер запущен!')
    else:
        print('Парсер уже запущен!')
    return jsonify({'success': True})

# Роут для запуска парсинга
@app.route('/start_parsinsg', methods=['POST'])
def start_parsing():
    stats = get_statistics()
    return render_template("parsing_stats.html", **stats)
  


if __name__ == '__main__':  
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)



