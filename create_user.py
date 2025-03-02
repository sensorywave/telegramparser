import sqlite3

AUTH_DB = 'users.db'

def init_auth_db():
    conn = sqlite3.connect(AUTH_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            superadmin INTEGER DEFAULT 0,
            db_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, password, superadmin=0):
    conn = sqlite3.connect(AUTH_DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO admin_users (username, password, superadmin) VALUES (?, ?, ?)",
        (username, password, superadmin)
    )
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Создаем таблицу, если её нет
    init_auth_db()

    # Пример: Создаём супер-админа
    create_user("admin", "admin123", superadmin=1)

    # Пример: Обычный админ (получит отдельную базу user_test.db)
    create_user("test", "test123", superadmin=0)

    print("Пользователи добавлены!")
