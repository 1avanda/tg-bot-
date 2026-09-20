import logging
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import db
import nlp

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

from enum import IntEnum

class TaskState(IntEnum):
    TITLE = 0
    DESCRIPTION = 1
    CATEGORY = 2
    DEADLINE_DATE = 3
    CUSTOM_DATE = 4
    DEADLINE_TIME = 5
    CUSTOM_TIME = 6

class HabitState(IntEnum):
    NAME = 7
    PERIOD_TYPE = 8
    PERIOD_VALUE = 9
    REMINDER_TIME = 10

class PomoState(IntEnum):
    DURATION = 11
    TASK = 12

class EditState(IntEnum):
    TASK_TITLE = 13
    HABIT_NAME = 14

(
    TASK_TITLE,
    TASK_DESCRIPTION,
    TASK_CATEGORY,
    TASK_DEADLINE_DATE,
    TASK_CUSTOM_DATE,
    TASK_DEADLINE_TIME,
    TASK_CUSTOM_TIME,
) = [s.value for s in TaskState]
(HABIT_NAME, HABIT_PERIOD_TYPE, HABIT_PERIOD_VALUE, HABIT_REMINDER_TIME) = [s.value for s in HabitState]
(POMODORO_DURATION, POMODORO_TASK) = [s.value for s in PomoState]
(EDIT_TASK_TITLE, EDIT_HABIT_NAME) = [s.value for s in EditState]


MENU_NEW_TASK = "Новая задача"
MENU_MY_TASKS = "Мои задачи"
MENU_HABITS = "Привычки"
MENU_POMO = "Pomodoro"
MENU_STATS = "Статистика"
MENU_HELP = "Помощь"


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [MENU_NEW_TASK, MENU_MY_TASKS],
            [MENU_HABITS, MENU_POMO],
            [MENU_STATS, MENU_HELP],
            ["🤖 ИИ-Помощник"],
        ],
        resize_keyboard=True,
    )


def category_label(cat):
    return {"work": "Работа", "personal": "Личное", "study": "Учёба", "other": "Другое"}.get(cat, cat)


async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Выберите действие:"):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=main_menu_keyboard(),
    )


def uid(update: Update):
    user = update.effective_user
    return db.get_or_create_user(user.id, user.username)


def schedule_task_reminder(context, chat_id, title, deadline):
    when = deadline - timedelta(minutes=5)
    delay = (when - datetime.now()).total_seconds()
    if delay < 5:
        delay = 5
    context.job_queue.run_once(
        send_reminder_job,
        when=delay,
        data={"chat_id": chat_id, "task_title": title},
    )


# ====================== Напоминания ======================
async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.data["chat_id"]
    if job.data.get("task_title"):
        await context.bot.send_message(chat_id, f"Напоминание о задаче: {job.data['task_title']}")
    elif job.data.get("habit_name"):
        await context.bot.send_message(chat_id, f"Напоминание о привычке: {job.data['habit_name']}")


async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in db.get_due_tasks(now):
        await context.bot.send_message(row["telegram_id"], f"Дедлайн задачи «{row['title']}» наступил.")


# ====================== Команды ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    uid(update)
    name = update.effective_user.first_name or ""
    
    text = (
        f"☁️  ☁️  ☁️  ☁️  ☁️  ☁️  ☁️\n"
        f"🌟 Здравствуйте, {name}!\n"
        f"Я ваш персональный ИИ-помощник по продуктивности.\n\n"
        f"🚀 *Что я умею:*\n"
        f"• Управлять задачами и дедлайнами\n"
        f"• Отслеживать привычки и серии (streaks)\n"
        f"• Запускать Pomodoro-таймеры\n"
        f"• Анализировать вашу статистику\n"
        f"• Помогать с планированием через ИИ\n\n"
        f"💡 *Подсказка:* Используйте меню или команды, например:\n"
        f" /newtask — создать задачу\n"
        f" /tasks — список активных дел\n"
        f" /habits — ваши привычки\n"
        f" /stats — отчет по продуктивности\n"
        f" /pomo — запуск таймера\n"
        f" /help — помощь\n\n"
        f"☁️  ☁️  ☁️  ☁️  ☁️  ☁️  ☁️"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    else:
        await send_menu(update, context, text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Справка по командам:*\n\n"
        "/start — Перезапустить бота\n"
        "/newtask — Создать новую задачу\n"
        "/tasks — Посмотреть список задач\n"
        "/habits — Управление привычками\n"
        "/pomo — Запустить Pomodoro\n"
        "/stats — Ваша статистика\n"
        "/help — Это сообщение\n\n"
        "💬 Также вы можете просто писать мне: \n"
        "«завтра в 10:00 купить хлеб» или «помидор 25 мин»"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")


# ====================== Задачи ======================
async def newtask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название задачи:", reply_markup=main_menu_keyboard())
    return TASK_TITLE


async def task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Пропустить", callback_data="skip_desc")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    await update.message.reply_text("Введите описание (или пропустите):", reply_markup=keyboard)
    return TASK_DESCRIPTION


async def task_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()
    await ask_category(update, context)
    return TASK_CATEGORY


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["description"] = None
    await ask_category(update, context)
    return TASK_CATEGORY


async def ask_category(update, context):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Работа", callback_data="work"),
                InlineKeyboardButton("Личное", callback_data="personal"),
            ],
            [
                InlineKeyboardButton("Учёба", callback_data="study"),
                InlineKeyboardButton("Другое", callback_data="other"),
            ],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    if update.callback_query:
        await update.callback_query.edit_message_text("Выберите категорию:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Выберите категорию:", reply_markup=keyboard)


async def task_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        return await cancel(update, context)
    context.user_data["category"] = query.data
    today = date.today()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Сегодня ({today.strftime('%d.%m')})", callback_data="today"),
                InlineKeyboardButton(
                    f"Завтра ({(today + timedelta(days=1)).strftime('%d.%m')})", callback_data="tomorrow"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"Послезавтра ({(today + timedelta(days=2)).strftime('%d.%m')})",
                    callback_data="after_tomorrow",
                ),
                InlineKeyboardButton("Своя дата", callback_data="custom_date"),
            ],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    await query.edit_message_text("Выберите дату:", reply_markup=keyboard)
    return TASK_DEADLINE_DATE


async def task_deadline_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == "cancel":
        return await cancel(update, context)
    if choice == "custom_date":
        await query.edit_message_text("Введите дату: ДД.ММ или ДД.ММ.ГГГГ")
        return TASK_CUSTOM_DATE
    today = date.today()
    mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "after_tomorrow": today + timedelta(days=2),
    }
    selected = mapping.get(choice)
    if not selected:
        await query.edit_message_text("Ошибка. Начните заново.")
        await send_menu(update, context)
        return ConversationHandler.END
    context.user_data["deadline_date"] = selected.strftime("%Y-%m-%d")
    await ask_time(update, context)
    return TASK_DEADLINE_TIME


async def task_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = nlp.parse_date(update.message.text.strip())
    if not selected:
        await update.message.reply_text("Неверный формат. Пример: 24.06 или 24.06.2026")
        return TASK_CUSTOM_DATE
    if selected < date.today():
        await update.message.reply_text("Дата не может быть в прошлом.")
        return TASK_CUSTOM_DATE
    context.user_data["deadline_date"] = selected.strftime("%Y-%m-%d")
    await ask_time(update, context)
    return TASK_DEADLINE_TIME


async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("09:00", callback_data="09:00"),
                InlineKeyboardButton("12:00", callback_data="12:00"),
                InlineKeyboardButton("15:00", callback_data="15:00"),
            ],
            [
                InlineKeyboardButton("18:00", callback_data="18:00"),
                InlineKeyboardButton("21:00", callback_data="21:00"),
                InlineKeyboardButton("Своё время", callback_data="custom_time"),
            ],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    if update.callback_query:
        await update.callback_query.edit_message_text("Выберите время:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Выберите время:", reply_markup=keyboard)


async def task_deadline_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "custom_time":
        await query.edit_message_text("Введите время ЧЧ:ММ, например 14:30")
        return TASK_CUSTOM_TIME
    if query.data == "cancel":
        return await cancel(update, context)
    context.user_data["deadline_time"] = query.data
    await finish_task(update, context)
    return ConversationHandler.END


async def task_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: 14:30")
        return TASK_CUSTOM_TIME
    context.user_data["deadline_time"] = time_str
    await finish_task(update, context)
    return ConversationHandler.END


async def finish_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        deadline = datetime.strptime(
            f"{context.user_data['deadline_date']} {context.user_data['deadline_time']}",
            "%Y-%m-%d %H:%M",
        )
    except KeyError:
        await update.effective_message.reply_text("Ошибка данных. Начните заново.")
        context.user_data.clear()
        await send_menu(update, context)
        return
    if deadline < datetime.now():
        await update.effective_message.reply_text("Нельзя поставить дедлайн в прошлом.")
        context.user_data.clear()
        await send_menu(update, context)
        return
    user_id = uid(update)
    title = context.user_data["title"]
    db.add_task(
        user_id,
        title,
        context.user_data.get("description"),
        context.user_data.get("category", "other"),
        deadline.strftime("%Y-%m-%d %H:%M:%S"),
    )
    schedule_task_reminder(context, update.effective_chat.id, title, deadline)
    if update.callback_query:
        await update.callback_query.edit_message_text(f"Задача «{title}» создана.")
    else:
        await update.message.reply_text(f"Задача «{title}» создана.")
    context.user_data.clear()
    await send_menu(update, context)


async def mytasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    user_id = uid(update)
    tasks = db.get_tasks(user_id)
    keyboard = []
    if not tasks:
        text = "Активных задач нет. ✨"
    else:
        lines = ["📋 *Ваши активные задачи:*"]
        for task in tasks:
            dl = task["deadline"]
            when = ""
            if dl:
                try:
                    dt = datetime.strptime(str(dl)[:19], "%Y-%m-%d %H:%M:%S")
                    when = dt.strftime(" ⏰ %d.%m %H:%M")
                except ValueError:
                    when = f" ⏰ {dl}"
            bell = "🔔" if task["reminder_enabled"] else "🔕"
            lines.append(f"• {task['title']}{when} [{category_label(task['category'])}] {bell}")
            keyboard.append([InlineKeyboardButton(f"⚙️ {task['title']}", callback_data=f"task_{task['id']}")])
        text = "\n".join(lines)
    
    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="back_main")])
    markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def show_task_detail(query, task_id):
    task = db.get_task(task_id)
    if not task:
        await query.edit_message_text("Задача не найдена.")
        return
    desc = f"\n{task['description']}" if task["description"] else ""
    reminder = "🔔 Вкл" if task["reminder_enabled"] else "🔕 Выкл"
    status = "выполнена" if task["is_completed"] else "активна"
    text = (
        f"{task['title']}{desc}\n"
        f"Категория: {category_label(task['category'])}\n"
        f"Срок: {task['deadline']}\n"
        f"{reminder} · {status}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Отметить", callback_data=f"done_{task_id}"),
                InlineKeyboardButton("Редактировать", callback_data=f"edit_task_{task_id}"),
            ],
            [
                InlineKeyboardButton("Напоминание", callback_data=f"toggle_reminder_{task_id}"),
                InlineKeyboardButton("Удалить", callback_data=f"delete_task_{task_id}"),
            ],
            [InlineKeyboardButton("Назад", callback_data="back_to_tasks")],
        ]
    )
    await query.edit_message_text(text, reply_markup=keyboard)


async def task_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[1])
    await show_task_detail(query, task_id)


async def done_task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Готово")
    task_id = int(query.data.split("_")[-1])
    db.complete_task(task_id)
    await query.edit_message_text("Задача отмечена выполненной.")
    await send_menu(update, context)


async def delete_task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    db.delete_task(task_id)
    await query.edit_message_text("Задача удалена.")
    await send_menu(update, context)


async def toggle_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    db.toggle_task_reminder(task_id)
    await show_task_detail(query, task_id)


async def edit_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split("_")[-1])
    context.user_data["edit_task_id"] = task_id
    await query.edit_message_text("Введите новое название задачи:")
    return EDIT_TASK_TITLE


async def edit_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_id = context.user_data.get("edit_task_id")
    title = update.message.text.strip()
    if task_id and title:
        db.update_task(task_id, title=title)
        await update.message.reply_text("Название обновлено.")
    context.user_data.pop("edit_task_id", None)
    await send_menu(update, context)
    return ConversationHandler.END


async def close_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.delete_message()


# ====================== Привычки ======================
def period_text(ptype, pval):
    if ptype == "daily":
        return "ежедневно"
    if ptype == "every_x_days":
        return f"каждые {pval} дня(ей)"
    if ptype == "weekly":
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        days = [day_names[int(d) - 1] for d in str(pval).split(",") if d]
        return "по " + ", ".join(days)
    if ptype == "weekend":
        return "по выходным"
    if ptype == "custom_days":
        return f"интервал {pval} дней"
    return str(ptype)


async def habits_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    user_id = uid(update)
    habits = db.get_habits(user_id)
    keyboard = []
    if not habits:
        text = "У вас нет привычек."
    else:
        lines = ["Ваши привычки:"]
        for h in habits:
            bell = "🔔" if h["reminder_enabled"] else "🔕"
            lines.append(f"{bell} {h['name']} (🔥 {h['streak']})")
            keyboard.append([InlineKeyboardButton(h["name"], callback_data=f"habit_{h['id']}")])
        text = "\n".join(lines)
    keyboard.append(
        [
            InlineKeyboardButton("Новая привычка", callback_data="new_habit"),
            InlineKeyboardButton("Назад", callback_data="back_main"),
        ]
    )
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def show_habit_detail(query, habit_id):
    habit = db.get_habit(habit_id)
    if not habit:
        await query.edit_message_text("Привычка не найдена.")
        return
    reminder_text = f"в {habit['reminder_time']}" if habit["reminder_time"] else "без времени"
    status = "🔔 Вкл" if habit["reminder_enabled"] else "🔕 Выкл"
    last_checked = f"Последний раз: {habit['last_checked']}" if habit["last_checked"] else "Ещё не отмечалась"
    text = (
        f"{habit['name']}\n{period_text(habit['period_type'], habit['period_value'])}\n"
        f"{reminder_text}\n{status}\n🔥 streak: {habit['streak']}\n{last_checked}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Отметить", callback_data=f"check_habit_{habit_id}"),
                InlineKeyboardButton("Редактировать", callback_data=f"edit_habit_{habit_id}"),
            ],
            [
                InlineKeyboardButton("Напоминание", callback_data=f"toggle_habit_reminder_{habit_id}"),
                InlineKeyboardButton("Удалить", callback_data=f"delete_habit_{habit_id}"),
            ],
            [InlineKeyboardButton("Назад", callback_data="back_to_habits")],
        ]
    )
    await query.edit_message_text(text, reply_markup=keyboard)


async def habit_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    habit_id = int(query.data.split("_")[1])
    await show_habit_detail(query, habit_id)


async def check_habit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    habit_id = int(query.data.split("_")[-1])
    marked = db.check_habit(habit_id)
    await query.answer("Отмечено" if marked else "Отметка снята")
    await show_habit_detail(query, habit_id)


async def toggle_habit_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    habit_id = int(query.data.split("_")[-1])
    db.toggle_habit_reminder(habit_id)
    await show_habit_detail(query, habit_id)


async def delete_habit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    habit_id = int(query.data.split("_")[-1])
    db.delete_habit(habit_id)
    await query.edit_message_text("Привычка удалена.")
    await send_menu(update, context)


async def edit_habit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["edit_habit_id"] = int(query.data.split("_")[-1])
    await query.edit_message_text("Введите новое название привычки:")
    return EDIT_HABIT_NAME


async def edit_habit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    habit_id = context.user_data.get("edit_habit_id")
    name = update.message.text.strip()
    if habit_id and name:
        db.update_habit(habit_id, name=name)
        await update.message.reply_text("Название обновлено.")
    context.user_data.pop("edit_habit_id", None)
    await send_menu(update, context)
    return ConversationHandler.END


async def newhabit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Введите название привычки:", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("Введите название привычки:", reply_markup=main_menu_keyboard())
    return HABIT_NAME


async def habit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["habit_name"] = update.message.text.strip()
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Ежедневно", callback_data="daily")],
            [InlineKeyboardButton("Через день", callback_data="every_2_days")],
            [InlineKeyboardButton("По дням недели", callback_data="weekly")],
            [InlineKeyboardButton("По выходным", callback_data="weekend")],
            [InlineKeyboardButton("Свой интервал (дни)", callback_data="custom_days")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    await update.message.reply_text("Выберите периодичность:", reply_markup=keyboard)
    return HABIT_PERIOD_TYPE


async def habit_period_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ptype = query.data
    if ptype == "cancel":
        return await cancel(update, context)
    context.user_data["period_type"] = ptype
    if ptype == "every_2_days":
        context.user_data["period_value"] = "2"
        await ask_habit_time(update, context)
        return HABIT_REMINDER_TIME
    if ptype == "weekend":
        context.user_data["period_value"] = "6,7"
        await ask_habit_time(update, context)
        return HABIT_REMINDER_TIME
    if ptype == "daily":
        context.user_data["period_value"] = "1"
        await ask_habit_time(update, context)
        return HABIT_REMINDER_TIME
    if ptype == "weekly":
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        keyboard, row = [], []
        context.user_data["selected_days"] = []
        for i, day in enumerate(days, start=1):
            row.append(InlineKeyboardButton(day, callback_data=f"day_{i}"))
            if i % 3 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append(
            [
                InlineKeyboardButton("Готово", callback_data="days_done"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ]
        )
        await query.edit_message_text(
            "Выберите дни недели, затем «Готово»:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return HABIT_PERIOD_VALUE
    if ptype == "custom_days":
        await query.edit_message_text("Введите число дней, например 3:")
        return HABIT_PERIOD_VALUE
    await query.edit_message_text("Ошибка. Начните заново.")
    await send_menu(update, context)
    return ConversationHandler.END


async def habit_period_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        data = query.data
        if data.startswith("day_"):
            day = data.split("_")[1]
            selected = context.user_data.setdefault("selected_days", [])
            if day in selected:
                selected.remove(day)
                await query.answer("День убран")
            else:
                selected.append(day)
                await query.answer("День выбран")
            return HABIT_PERIOD_VALUE
        await query.answer()
        if data == "days_done":
            if not context.user_data.get("selected_days"):
                await query.answer("Выберите хотя бы один день!", show_alert=True)
                return HABIT_PERIOD_VALUE
            context.user_data["period_value"] = ",".join(sorted(context.user_data["selected_days"]))
            await ask_habit_time(update, context)
            return HABIT_REMINDER_TIME
        return HABIT_PERIOD_VALUE
    try:
        num = int(update.message.text.strip())
        if num < 1:
            raise ValueError
        context.user_data["period_value"] = str(num)
        await ask_habit_time(update, context)
        return HABIT_REMINDER_TIME
    except ValueError:
        await update.message.reply_text("Введите целое положительное число.")
        return HABIT_PERIOD_VALUE


async def ask_habit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("09:00", callback_data="09:00"),
                InlineKeyboardButton("12:00", callback_data="12:00"),
                InlineKeyboardButton("15:00", callback_data="15:00"),
            ],
            [
                InlineKeyboardButton("18:00", callback_data="18:00"),
                InlineKeyboardButton("21:00", callback_data="21:00"),
                InlineKeyboardButton("Своё время", callback_data="custom_time"),
            ],
            [
                InlineKeyboardButton("Пропустить", callback_data="skip_time"),
                InlineKeyboardButton("Отмена", callback_data="cancel"),
            ],
        ]
    )
    text = "Время напоминания (можно пропустить):"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def habit_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data
    if time_str == "custom_time":
        await query.edit_message_text("Введите время ЧЧ:ММ")
        return HABIT_REMINDER_TIME
    if time_str in ("skip_time",):
        context.user_data["reminder_time"] = None
        await finish_habit(update, context)
        return ConversationHandler.END
    if time_str == "cancel":
        return await cancel(update, context)
    context.user_data["reminder_time"] = time_str
    await finish_habit(update, context)
    return ConversationHandler.END


async def habit_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: 14:30")
        return HABIT_REMINDER_TIME
    context.user_data["reminder_time"] = time_str
    await finish_habit(update, context)
    return ConversationHandler.END


async def finish_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    name = context.user_data["habit_name"]
    period_type = context.user_data["period_type"]
    if period_type == "every_2_days":
        period_type = "every_x_days"
    db.add_habit(
        user_id,
        name,
        period_type,
        context.user_data.get("period_value", "1"),
        context.user_data.get("reminder_time"),
    )
    msg = f"Привычка «{name}» создана."
    if update.callback_query:
        await update.callback_query.edit_message_text(msg)
    else:
        await update.effective_message.reply_text(msg)
    context.user_data.clear()
    await send_menu(update, context)


# ====================== Pomodoro ======================
async def pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = uid(update)
    active = db.get_active_pomodoro(user_id)
    if active:
        end_time = datetime.strptime(str(active["end_time"])[:19], "%Y-%m-%d %H:%M:%S")
        remaining = max(0, int((end_time - datetime.now()).total_seconds() // 60))
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Отменить", callback_data=f"cancel_pomodoro_{active['id']}")]]
        )
        text = f"Уже есть помидор. Осталось около {remaining} мин."
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await update.message.reply_text(text, reply_markup=keyboard)
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("25 мин", callback_data="pomodoro_25"),
                InlineKeyboardButton("35 мин", callback_data="pomodoro_35"),
                InlineKeyboardButton("45 мин", callback_data="pomodoro_45"),
            ],
            [InlineKeyboardButton("Описание техники", callback_data="pomodoro_info")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    text = "Выберите длительность помидора:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)
    return POMODORO_DURATION


async def pomodoro_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "Pomodoro — техника тайм-менеджмента:\n"
        "• 25 минут работы\n"
        "• 5 минут перерыва\n"
        "• После 4 циклов — длинный перерыв 15–30 минут"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_pomodoro")]])
    await query.edit_message_text(text, reply_markup=keyboard)
    return POMODORO_DURATION


async def pomodoro_duration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "pomodoro_info":
        return await pomodoro_info(update, context)
    if data == "back_to_pomodoro":
        return await pomodoro(update, context)
    if not data.startswith("pomodoro_"):
        return ConversationHandler.END
    duration = int(data.split("_")[1])
    user_id = uid(update)
    tasks = db.get_tasks(user_id, date.today().strftime("%Y-%m-%d"))
    if tasks:
        keyboard = [[InlineKeyboardButton(t["title"], callback_data=f"pomodoro_task_{t['id']}_{duration}")] for t in tasks]
        keyboard.append([InlineKeyboardButton("Без задачи", callback_data=f"pomodoro_notask_{duration}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_pomodoro")])
        await query.edit_message_text("Задача для помидора:", reply_markup=InlineKeyboardMarkup(keyboard))
        return POMODORO_TASK
    await launch_pomodoro(update, context, user_id, duration, None)
    return ConversationHandler.END


async def launch_pomodoro(update, context, user_id, duration, task_id):
    session_id, end_time = db.start_pomodoro(user_id, duration, task_id)
    delay = max(1, (end_time - datetime.now()).total_seconds())
    context.job_queue.run_once(
        pomodoro_end,
        when=delay,
        data={"chat_id": update.effective_chat.id, "session_id": session_id},
        name=f"pomo_{session_id}",
    )
    text = f"Помидор на {duration} мин до {end_time.strftime('%H:%M')}."
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.effective_message.reply_text(text)
    await send_menu(update, context)


async def start_pomodoro_with_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_to_pomodoro":
        return await pomodoro(update, context)
    if data.startswith("pomodoro_task_"):
        parts = data.split("_")
        task_id, duration = int(parts[2]), int(parts[3])
    elif data.startswith("pomodoro_notask_"):
        duration = int(data.split("_")[2])
        task_id = None
    else:
        return ConversationHandler.END
    await launch_pomodoro(update, context, uid(update), duration, task_id)
    return ConversationHandler.END


async def cancel_pomodoro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session_id = int(query.data.split("_")[2])
    db.complete_pomodoro(session_id)
    for job in context.job_queue.get_jobs_by_name(f"pomo_{session_id}"):
        job.schedule_removal()
    await query.edit_message_text("Помидор отменён.")
    await send_menu(update, context)


async def pomodoro_end(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    db.complete_pomodoro(job.data["session_id"])
    await context.bot.send_message(job.data["chat_id"], "Время вышло! Можно начать новый помидор.")


# ====================== Статистика ======================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    user_id = uid(update)
    today = date.today().isoformat()

    # Базовая статистика (на сегодня)
    s = db.get_stats(user_id, today)
    adv = db.get_advanced_stats(user_id)

    text = (
        f"📊 *Ваша продуктивность*\n\n"
        f"📅 *Сегодня:*\n"
        f"✅ Завершено задач: {s['completed_today']}\n"
        f"⏳ Активных задач: {s['active_tasks']}\n"
        f"🍅 Pomodoro сессий: {s['pomodoros_today']}\n"
        f"🔥 Общий стрик привычек: {s['total_streak']}\n\n"
        f"📈 *Общий прогресс:*\n"
        f"• Завершено: {adv['completed_tasks']}/{adv['total_tasks']} ({adv['completion_rate']}%)\n"
        f"• Время фокуса: {adv['total_pomo_minutes']} мин\n"
        f"• Топ категория: {adv['top_category']}\n\n"
        f"Keep going! 🚀"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ====================== NLP ======================
async def chat_reply(update, context, text):
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=main_menu_keyboard())


async def apply_nlp_action(update, context, action, user_id):
    intent = action["intent"]
    if intent == "list_tasks":
        tasks = db.get_tasks(user_id)
        if not tasks:
            await chat_reply(update, context, "Активных задач нет.")
            return True
        lines = ["Активные задачи:"]
        for task in tasks:
            lines.append(f"• {task['title']} ({task['deadline']})")
        await chat_reply(update, context, "\n".join(lines))
        return True
    if intent == "add_task":
        title = (action.get("title") or "").strip()
        if not title:
            return False
        deadline = action.get("deadline") or datetime.now().strftime("%Y-%m-%d 18:00:00")
        db.add_task(user_id, title, action.get("description"), action.get("category") or "other", deadline)
        try:
            schedule_task_reminder(
                context,
                update.effective_chat.id,
                title,
                datetime.strptime(deadline[:19], "%Y-%m-%d %H:%M:%S"),
            )
        except ValueError:
            pass
        await chat_reply(update, context, f"Записал задачу «{title}» на {deadline}.")
        return True
    if intent == "complete_task":
        title = (action.get("title") or "").strip()
        row = db.find_task_by_title(user_id, title) if title else None
        if not row:
            tasks = db.get_tasks(user_id)
            if len(tasks) == 1:
                row = tasks[0]
        if not row:
            await chat_reply(update, context, "Не нашёл такую активную задачу.")
            return True
        db.complete_task(row["id"])
        await chat_reply(update, context, f"Отметил «{row['title']}» выполненной.")
        return True
    if intent == "add_habit":
        name = (action.get("habit_name") or action.get("title") or "").strip()
        if not name:
            return False
        db.add_habit(
            user_id,
            name,
            action.get("period_type") or "daily",
            action.get("period_value") or "1",
            None,
        )
        await chat_reply(update, context, f"Привычка «{name}» создана.")
        return True
    if intent == "check_habit":
        name = (action.get("habit_name") or action.get("title") or "").strip()
        row = db.find_habit_by_name(user_id, name) if name else None
        if not row:
            await chat_reply(update, context, "Не нашёл такую привычку.")
            return True
        marked = db.check_habit(row["id"])
        await chat_reply(
            update,
            context,
            f"Привычка «{row['name']}» {'отмечена' if marked else 'снята'}.",
        )
        return True
    if intent == "start_pomodoro":
        duration = action.get("duration") or 25
        if db.get_active_pomodoro(user_id):
            await chat_reply(update, context, "Помидор уже идёт.")
            return True
        await launch_pomodoro(update, context, user_id, duration, None)
        return True
    return False


async def nlp_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Сначала проверяем, не нажал ли пользователь одну из кнопок меню
    # Это позволит меню работать даже во время активных диалогов
    if text == MENU_NEW_TASK:
        return await newtask(update, context)
    if text == MENU_MY_TASKS:
        await mytasks(update, context)
        return
    if text == MENU_HABITS:
        await habits_list(update, context)
        return
    if text == MENU_POMO:
        return await pomodoro(update, context)
    if text == MENU_STATS:
        await stats(update, context)
        return
    if text == MENU_HELP:
        await help_command(update, context)
        return
    if text == "🤖 ИИ-Помощник":
        await update.message.reply_text("Я готов помочь! Спроси меня о продуктивности, планировании или попроси совета по твоим задачам.", reply_markup=main_menu_keyboard())
        return

    action = await nlp.parse_user_text(text)
    
    if action["intent"] == "none" or action.get("confidence", 0) < 0.7:
        user_id = uid(update)
        today_stats = db.get_stats(user_id, date.today().isoformat())
        adv_stats = db.get_advanced_stats(user_id)
        context_str = (
            f"Статистика за сегодня: {today_stats}\\n"
            f"Общая статистика: {adv_stats}"
        )
        
        ai_reply = await nlp.ai_assistant_reply(text, user_context=context_str)
        await update.message.reply_text(ai_reply, reply_markup=main_menu_keyboard())
        return

    context.user_data["pending_nlp"] = action
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Записать", callback_data="nlp_yes"),
                InlineKeyboardButton("Отмена", callback_data="nlp_no"),
            ]
        ]
    )
    source = "нейросеть" if action.get("source") == "llm" else "правила"
    await update.message.reply_text(
        f"Понял так ({source}):\n{nlp.describe_action(action)}\n\nЗаписать в базу?",
        reply_markup=keyboard,
    )


async def nlp_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "nlp_no":
        context.user_data.pop("pending_nlp", None)
        await query.edit_message_text("Ок, не записываю.")
        return
    action = context.user_data.pop("pending_nlp", None)
    if not action:
        await query.edit_message_text("Запрос уже обработан.")
        return
    ok = await apply_nlp_action(update, context, action, uid(update))
    if ok:
        await query.edit_message_text("Готово: " + nlp.describe_action(action).split("\n")[0])
    else:
        await query.edit_message_text("Не хватило данных, попробуйте иначе.")


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == MENU_NEW_TASK:
        return await newtask(update, context)
    if text == MENU_MY_TASKS:
        await mytasks(update, context)
        return
    if text == MENU_HABITS:
        await habits_list(update, context)
        return
    if text == MENU_POMO:
        return await pomodoro(update, context)
    if text == MENU_STATS:
        await stats(update, context)
        return
    if text == MENU_HELP:
        await help_command(update, context)
        return
    if text == "🤖 ИИ-Помощник":
        await update.message.reply_text("Я готов помочь! Спроси меня о продуктивности, планировании или попроси совета по твоим задачам.")
        return
    await nlp_message(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Действие отменено.")
    elif update.message:
        await update.message.reply_text("Действие отменено.")
    context.user_data.clear()
    await send_menu(update, context)
    return ConversationHandler.END


async def post_init(application: Application):
    commands = [
        ("start", "Перезапустить бота"),
        ("newtask", "Создать новую задачу"),
        ("tasks", "Список активных задач"),
        ("habits", "Управление привычками"),
        ("pomo", "Запустить Pomodoro"),
        ("stats", "Ваша статистика"),
        ("help", "Помощь"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    db.init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token.startswith("your_"):
        raise SystemExit("Укажите TELEGRAM_BOT_TOKEN в файле .env")

    application = Application.builder().token(token).post_init(post_init).build()

    task_conv = ConversationHandler(
        entry_points=[
            CommandHandler("newtask", newtask),
            MessageHandler(filters.Regex(f"^{MENU_NEW_TASK}$"), newtask),
        ],
        states={
            TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_title)],
            TASK_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, task_description),
                CallbackQueryHandler(skip_description, pattern="^skip_desc$"),
            ],
            TASK_CATEGORY: [CallbackQueryHandler(task_category)],
            TASK_DEADLINE_DATE: [CallbackQueryHandler(task_deadline_date)],
            TASK_CUSTOM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_custom_date)],
            TASK_DEADLINE_TIME: [CallbackQueryHandler(task_deadline_time)],
            TASK_CUSTOM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_custom_time)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    )
    habit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(newhabit, pattern="^new_habit$"),
            CommandHandler("newhabit", newhabit),
        ],
        states={
            HABIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, habit_name)],
            HABIT_PERIOD_TYPE: [CallbackQueryHandler(habit_period_type)],
            HABIT_PERIOD_VALUE: [
                CallbackQueryHandler(habit_period_value),
                MessageHandler(filters.TEXT & ~filters.COMMAND, habit_period_value),
            ],
            HABIT_REMINDER_TIME: [
                CallbackQueryHandler(habit_reminder_time),
                MessageHandler(filters.TEXT & ~filters.COMMAND, habit_custom_time),
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    )
    pomo_conv = ConversationHandler(
        entry_points=[
            CommandHandler("pomodoro", pomodoro),
            MessageHandler(filters.Regex(f"^{MENU_POMO}$"), pomodoro),
        ],
        states={
            POMODORO_DURATION: [CallbackQueryHandler(pomodoro_duration_choice), CallbackQueryHandler(pomodoro_info, pattern="^pomodoro_info$")],
            POMODORO_TASK: [CallbackQueryHandler(start_pomodoro_with_task)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"), CommandHandler("cancel", cancel)],
    )
    edit_task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_task_start, pattern="^edit_task_")],
        states={EDIT_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_task_title)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    edit_habit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_habit_start, pattern="^edit_habit_")],
        states={EDIT_HABIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_habit_name)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(task_conv)
    application.add_handler(habit_conv)
    application.add_handler(pomo_conv)
    application.add_handler(edit_task_conv)
    application.add_handler(edit_habit_conv)
    
    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", mytasks))
    application.add_handler(CommandHandler("habits", habits_list))
    application.add_handler(CommandHandler("pomo", pomodoro))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("newtask", newtask))
    
    application.add_handler(CallbackQueryHandler(nlp_confirm, pattern="^nlp_(yes|no)$"))
    application.add_handler(CallbackQueryHandler(mytasks, pattern="^back_to_tasks$"))
    application.add_handler(CallbackQueryHandler(habits_list, pattern="^back_to_habits$"))
    application.add_handler(CallbackQueryHandler(start, pattern="^back_main$"))
    application.add_handler(CallbackQueryHandler(close_message, pattern="^close$"))
    application.add_handler(CallbackQueryHandler(done_task_handler, pattern="^done_"))
    application.add_handler(CallbackQueryHandler(task_detail, pattern="^task_"))
    application.add_handler(CallbackQueryHandler(delete_task_handler, pattern="^delete_task_"))
    application.add_handler(CallbackQueryHandler(toggle_reminder_handler, pattern="^toggle_reminder_"))
    application.add_handler(CallbackQueryHandler(habit_detail, pattern="^habit_"))
    application.add_handler(CallbackQueryHandler(check_habit_handler, pattern="^check_habit_"))
    application.add_handler(CallbackQueryHandler(toggle_habit_reminder_handler, pattern="^toggle_habit_reminder_"))
    application.add_handler(CallbackQueryHandler(delete_habit_handler, pattern="^delete_habit_"))
    application.add_handler(CallbackQueryHandler(cancel_pomodoro_handler, pattern="^cancel_pomodoro_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    if application.job_queue:
        application.job_queue.run_repeating(check_deadlines, interval=60, first=10)
    else:
        logger.warning("job-queue не установлен: pip install 'python-telegram-bot[job-queue]'")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
