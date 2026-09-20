import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).with_name("productivity_bot.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            category TEXT DEFAULT 'other',
            deadline TIMESTAMP,
            is_completed INTEGER DEFAULT 0,
            reminder_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            period_type TEXT,
            period_value TEXT,
            reminder_time TEXT,
            reminder_enabled INTEGER DEFAULT 1,
            streak INTEGER DEFAULT 0,
            last_checked DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS habit_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER,
            check_date DATE,
            UNIQUE(habit_id, check_date),
            FOREIGN KEY(habit_id) REFERENCES habits(id)
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )"""
        )


def get_or_create_user(telegram_id, username):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        row = c.fetchone()
        if row:
            return row["id"]
        c.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username),
        )
        return c.lastrowid


def add_task(user_id, title, description, category, deadline):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO tasks (user_id, title, description, category, deadline)
                 VALUES (?, ?, ?, ?, ?)""",
            (user_id, title, description, category, deadline),
        )
        return c.lastrowid


def get_tasks(user_id, on_date=None, include_completed=False):
    with get_conn() as conn:
        c = conn.cursor()
        sql = """SELECT id, title, description, category, deadline, is_completed, reminder_enabled
                 FROM tasks WHERE user_id = ?"""
        params = [user_id]
        if on_date:
            sql += " AND DATE(deadline) = DATE(?)"
            params.append(on_date)
        if not include_completed:
            sql += " AND is_completed = 0"
        sql += " ORDER BY deadline IS NULL, deadline"
        c.execute(sql, params)
        return c.fetchall()


def find_task_by_title(user_id, title):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, title FROM tasks
               WHERE user_id = ? AND is_completed = 0
               AND lower(title) LIKE ?
               ORDER BY deadline LIMIT 1""",
            (user_id, f"%{title.lower()}%"),
        )
        return c.fetchone()


def get_task(task_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, user_id, title, description, category, deadline, is_completed, reminder_enabled
                 FROM tasks WHERE id = ?""",
            (task_id,),
        )
        return c.fetchone()


def update_task(task_id, **kwargs):
    if not kwargs:
        return
    
    # Белый список разрешенных полей для защиты от SQL-инъекций
    allowed_fields = {"title", "description", "category", "deadline", "is_completed", "reminder_enabled"}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not filtered_kwargs:
        return

    fields = [f"{key}=?" for key in filtered_kwargs]
    values = list(filtered_kwargs.values()) + [task_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", values)


def complete_task(task_id):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET is_completed = 1 WHERE id = ?", (task_id,))


def delete_task(task_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def toggle_task_reminder(task_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET reminder_enabled = CASE WHEN reminder_enabled = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (task_id,),
        )


def add_habit(user_id, name, period_type, period_value, reminder_time):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO habits (user_id, name, period_type, period_value, reminder_time)
                 VALUES (?, ?, ?, ?, ?)""",
            (user_id, name, period_type, period_value, reminder_time),
        )
        return c.lastrowid


def get_habits(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, name, period_type, period_value, reminder_time, reminder_enabled, streak, last_checked
                 FROM habits WHERE user_id = ?""",
            (user_id,),
        )
        return c.fetchall()


def find_habit_by_name(user_id, name):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, name FROM habits
               WHERE user_id = ? AND lower(name) LIKE ? LIMIT 1""",
            (user_id, f"%{name.lower()}%"),
        )
        return c.fetchone()


def get_habit(habit_id):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, user_id, name, period_type, period_value, reminder_time, reminder_enabled, streak, last_checked
                 FROM habits WHERE id = ?""",
            (habit_id,),
        )
        return c.fetchone()


def update_habit(habit_id, **kwargs):
    if not kwargs:
        return
    
    # Белый список разрешенных полей
    allowed_fields = {"name", "period_type", "period_value", "reminder_time", "reminder_enabled", "streak", "last_checked"}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not filtered_kwargs:
        return

    fields = [f"{key}=?" for key in filtered_kwargs]
    values = list(filtered_kwargs.values()) + [habit_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE habits SET {', '.join(fields)} WHERE id=?", values)


def delete_habit(habit_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM habit_checks WHERE habit_id = ?", (habit_id,))
        conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))


def toggle_habit_reminder(habit_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE habits SET reminder_enabled = CASE WHEN reminder_enabled = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (habit_id,),
        )


def check_habit(habit_id, check_date=None):
    if check_date is None:
        check_date = date.today()
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM habit_checks WHERE habit_id = ? AND check_date = ?",
            (habit_id, check_date.isoformat()),
        )
        already = c.fetchone() is not None
        if already:
            c.execute(
                "DELETE FROM habit_checks WHERE habit_id = ? AND check_date = ?",
                (habit_id, check_date.isoformat()),
            )
            c.execute(
                "SELECT COUNT(*) AS cnt FROM habit_checks WHERE habit_id = ?",
                (habit_id,),
            )
            streak = c.fetchone()["cnt"]
            c.execute(
                "SELECT MAX(check_date) AS last FROM habit_checks WHERE habit_id = ?",
                (habit_id,),
            )
            last = c.fetchone()["last"]
            c.execute(
                "UPDATE habits SET last_checked = ?, streak = ? WHERE id = ?",
                (last, streak, habit_id),
            )
            return False

        c.execute(
            "INSERT INTO habit_checks (habit_id, check_date) VALUES (?, ?)",
            (habit_id, check_date.isoformat()),
        )
        c.execute("SELECT last_checked, streak FROM habits WHERE id = ?", (habit_id,))
        row = c.fetchone()
        last_checked, streak = row["last_checked"], row["streak"] or 0
        if last_checked:
            last = datetime.strptime(str(last_checked)[:10], "%Y-%m-%d").date()
            new_streak = streak + 1 if (check_date - last).days <= 1 else 1
        else:
            new_streak = 1
        c.execute(
            "UPDATE habits SET last_checked = ?, streak = ? WHERE id = ?",
            (check_date.isoformat(), new_streak, habit_id),
        )
        return True


def start_pomodoro(user_id, duration, task_id=None):
    start = datetime.now().replace(microsecond=0)
    end = start + timedelta(minutes=duration)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO pomodoro_sessions (user_id, task_id, start_time, end_time, duration)
                 VALUES (?, ?, ?, ?, ?)""",
            (user_id, task_id, start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), duration),
        )
        return c.lastrowid, end


def get_active_pomodoro(user_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, task_id, end_time, duration FROM pomodoro_sessions
                 WHERE user_id = ? AND completed = 0 AND end_time > ?
                 ORDER BY id DESC LIMIT 1""",
            (user_id, now),
        )
        return c.fetchone()


def complete_pomodoro(session_id):
    with get_conn() as conn:
        conn.execute("UPDATE pomodoro_sessions SET completed = 1 WHERE id = ?", (session_id,))


def get_due_tasks(now_str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT t.id, t.title, u.telegram_id
                 FROM tasks t JOIN users u ON t.user_id = u.id
                 WHERE t.is_completed = 0 AND t.reminder_enabled = 1
                   AND t.deadline <= ? AND t.deadline > datetime(?, '-1 hour')""",
            (now_str, now_str),
        )
        return c.fetchall()


def get_stats(user_id, today):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND is_completed = 1 AND DATE(deadline) = ?",
            (user_id, today),
        )
        completed_today = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND is_completed = 0", (user_id,))
        active_tasks = c.fetchone()[0]
        c.execute("SELECT COUNT(*), COALESCE(SUM(streak), 0) FROM habits WHERE user_id = ?", (user_id,))
        habits_count, total_streak = c.fetchone()
        c.execute(
            "SELECT COUNT(*) FROM pomodoro_sessions WHERE user_id = ? AND DATE(start_time) = ?",
            (user_id, today),
        )
        pomodoros_today = c.fetchone()[0]
    return {
        "completed_today": completed_today,
        "active_tasks": active_tasks,
        "habits_count": habits_count or 0,
        "total_streak": total_streak or 0,
        "pomodoros_today": pomodoros_today,
    }

def get_advanced_stats(user_id):
    with get_conn() as conn:
        c = conn.cursor()
        # 1. Общий прогресс задач
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
        total_tasks = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND is_completed = 1", (user_id,))
        completed_tasks = c.fetchone()[0] or 0
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # 2. Общее время Pomodoro (в минутах)
        c.execute("SELECT SUM(duration) FROM pomodoro_sessions WHERE user_id = ? AND completed = 1", (user_id,))
        total_pomo_time = c.fetchone()[0] or 0

        # 3. Топ категория
        c.execute(
            "SELECT category, COUNT(*) as cnt FROM tasks WHERE user_id = ? GROUP BY category ORDER BY cnt DESC LIMIT 1",
            (user_id,),
        )
        top_cat_row = c.fetchone()
        top_category = top_cat_row["category"] if top_cat_row else "Нет данных"

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": round(completion_rate, 1),
            "total_pomo_minutes": total_pomo_time,
            "top_category": top_category,
        }
