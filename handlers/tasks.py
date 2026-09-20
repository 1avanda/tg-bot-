import logging
from datetime import date, datetime, timedelta
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from services import TaskService
from utils import keyboards as kb
from utils.exceptions import BotError
# Импортируем состояния из основного модуля
from bot import TaskState

logger = logging.getLogger(__name__)

async def newtask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса создания новой задачи."""
    await update.message.reply_text(
        "Введите название задачи:", 
        reply_markup=kb.main_// ... [truncated]

async def task_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка названия задачи."""
    context.user_data["title"] = update.message.text.strip()
    
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Пропустить", callback_data="skip_desc")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )
    await update.message.reply_text("Введите описание (или пропустите):", reply_markup=keyboard)
    return TaskState.DESCRIPTION

async def task_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка описания задачи."""
    context.user_data["description"] = update.message.text.strip()
    await ask_category(update, context)
    return TaskState.CATEGORY

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск ввода описания."""
    query = update.callback_query
    await query.answer()
    context.user_data["description"] = None
    await ask_category(update, context)
    return TaskState.CATEGORY

async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка клавиатуры выбора категории."""
    keyboard = kb.task_category_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text("Выберите категорию:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Выберите категорию:", reply_markup=keyboard)

async def task_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора категории."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        # Здесь вызывается функция отмены, которая будет в bot.py или utils
        return ConversationHandler.END
        
    context.user_data["category"] = query.data
    today = date.today()
    
    keyboard = kb.task_date_keyboard(
        today.strftime('%d.%m'),
        (today + timedelta(days=1)).strftime('%d.%m'),
        (today + timedelta(days=2)).strftime('%d.%m')
    )
    await query.edit_message_text("Выберите дату:", reply_markup=keyboard)
    return TaskState.DEADLINE_DATE

async def task_deadline_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора даты."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == "cancel":
        return ConversationHandler.END
    if choice == "custom_date":
        await query.edit_message_text("Введите дату: ДД.ММ или ДД.ММ.ГГГГ")
        return TaskState.CUSTOM_DATE
        
    today = date.today()
    mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "after_tomorrow": today + timedelta(days=2),
    }
    selected = mapping.get(choice)
    if not selected:
        await query.edit_message_text("Ошибка. Начните заново.")
        return ConversationHandler.END
        
    context.user_data["deadline_date"] = selected.strftime("%Y-%m-%d")
    await ask_time(update, context)
    return TaskState.DEADLINE_TIME

async def task_custom_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода произвольной даты."""
    selected = nlp.parse_date(update.message.text.strip())
    if not selected:
        await update.message.reply_text("Неверный формат. Пример: 24.06 или 24.06.2026")
        return TaskState.CUSTOM_DATE
    if selected < date.today():
        await update.message.reply_text("Дата не может быть в прошлом.")
        return TaskState.CUSTOM_DATE
    context.user_data["deadline_date"] = selected.strftime("%Y-%m-%d")
    await ask_time(update, context)
    return TaskState.DEADLINE_TIME

async def ask_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправка клавиатуры выбора времени."""
    keyboard = kb.task_time_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text("Выберите время:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Выберите время:", reply_markup=keyboard)

async def task_deadline_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора времени."""
    query = update.callback_query
    await query.answer()
    if query.data == "custom_time":
        await query.edit_message_text("Введите время ЧЧ:ММ, например 14:30")
        return TaskState.CUSTOM_TIME
    if query.data == "cancel":
        return ConversationHandler.END
    context.user_data["deadline_time"] = query.data
    await finish_task(update, context)
    return ConversationHandler.END

async def task_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода произвольного времени."""
    time_str = update.message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: 14:30")
        return TaskState.CUSTOM_TIME
    context.user_data["deadline_time"] = time_str
    await finish_task(update, context)
    return ConversationHandler.END

async def finish_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Завершение создания задачи и запись в БД."""
    try:
        deadline = datetime.strptime(
            f"{context.user_data['deadline_date']} {context.user_data['deadline_time']}",
            "%Y-%m-%d %H:%M",
        )
    except KeyError:
        await update.effective_message.reply_text("Ошибка данных. Начните заново.")
        context.user_data.clear()
        return

    if deadline < datetime.now():
        await update.effective_message.reply_text("Нельзя поставить дедлайн в прошлом.")
        context.user_data.clear()
        return

    # Вспомогательная функция uid будет перенесена в utils
    from bot import uid
    user_id = uid(update)
    title = context.user_data["title"]
    
    db.add_task(
        user_id,
        title,
        context.user_data.get("description"),
        context.user_data.get("category", "other"),
        deadline.strftime("%Y-%m-%d %H:%M:%S"),
    )
    
    # Напоминания
    from bot import schedule_task_reminder
    schedule_task_reminder(context, update.effective_chat.id, title, deadline)
    
    text = f"Задача «{title}» создана."
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)
        
    context.user_data.clear()
    
    # Возврат в меню
    from bot import send_menu
    await send_menu(update, context)

async def mytasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображение списка активных задач пользователя."""
    if update.callback_query:
        await update.callback_query.answer()
    
    from bot import uid
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
            
            # Категории
            cat_map = {"work": "Работа", "personal": "Личное", "study": "Учёба", "other": "Другое"}
            category = cat_map.get(task["category"], task["category"])
            bell = "🔔" if task["reminder_enabled"] else "🔕"
            
            lines.append(f"• {task['title']}{when} [{category}] {bell}")
            keyboard.append([InlineKeyboardButton(f"⚙️ {task['title']}", callback_data=f"task_{task['id']}")])
        text = "\n".join(lines)

    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="back_main")])
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def show_task_detail(query, task_id: int) -> None:
    """Отображение деталей конкретной задачи."""
    task = db.get_task(task_id)
    if not task:
        await query.edit_message_text("Задача не найдена.")
        return
        
    desc = f"\n{task['description']}" if task["description"] else ""
    reminder = "🔔 Вкл" if task["reminder_enabled"] else "🔕 Выкл"
    status = "выполнена" if task["is_completed"] else "активна"
    
    cat_map = {"work": "Работа", "personal": "Личное", "study": "Учёба", "other": "Другое"}
    category = cat_map.get(task["category"], task["category"])
    
    text = (
        f"{task['title']}{desc}\n"
        f"Категория: {category}\n"
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

async def task_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Хендлер для отображения деталей задачи."""
    query = update.callback_query
    await query.answer()
    try:
        task_id = int(query.data.split("_")[1])
        await show_task_detail(query, task_id)
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка в ID задачи.")

async def done_task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отметка задачи как выполненной."""
    query = update.callback_query
    await query.answer("Готово")
    try:
        task_id = int(query.data.split("_")[1])
        db.complete_task(task_id)
        await query.edit_message_text("Задача отмечена выполненной.")
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка при выполнении.")
    
    from bot import send_menu
    await send_menu(update, context)

async def delete_task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление задачи."""
    query = update.callback_query
    await query.answer()
    try:
        task_id = int(query.data.split("_")[2])
        db.delete_task(task_id)
        await query.edit_message_text("Задача удалена.")
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка при удалении.")
    
    from bot import send_menu
    await send_menu(update, context)

async def toggle_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключение напоминания для задачи."""
    query = update.callback_query
    await query.answer()
    try:
        task_id = int(query.data.split("_")[2])
        db.toggle_task_reminder(task_id)
        await show_task_detail(query, task_id)
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка с напоминанием.")

async def edit_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало редактирования задачи."""
    query = update.callback_query
    await query.answer()
    try:
        task_id = int(query.data.split("_")[2])
        context.user_data["edit_task_id"] = task_id
        await query.edit_message_text("Введите новое название задачи:")
        return EditState.TASK_TITLE
    except (ValueError, IndexError):
        await query.edit_message_text("Ошибка ID задачи.")
        return ConversationHandler.END

async def edit_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обновление названия задачи."""
    task_id = context.user_data.get("edit_task_id")
    title = update.message.text.strip()
    if task_id and title:
        db.update_task(task_id, title=title)
        await update.message.reply_text("Название обновлено.")
    
    context.user_data.pop("edit_task_id", None)
    from bot import send_menu
    await send_menu(update, context)
    return ConversationHandler.END
