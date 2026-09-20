import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from services import PomoService
from utils.exceptions import BotError
from bot import PomoState

logger = logging.getLogger(__name__)

async def start_pomo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск процесса создания Pomodoro-сессии."""
    await update.message.reply_text(
        "Введите длительность помидора в минутах (по умолчанию 25):"
    )
    return PomoState.DURATION

async def pomo_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка длительности сессии."""
    text = update.message.text.strip()
    try:
        duration = int(text)
        if duration < 1 or duration > 1440:
            raise ValueError
    except ValueError:
        duration = 25
        await update.message.reply_text(f"Некорректный ввод. Установлено значение по умолчанию: {duration} мин.")
    
    context.user_data["pomo_duration"] = duration
    await update.message.reply_text("Для какой задачи запускаем таймер? (Пришлите название или 'пропустить')")
    return PomoState.TASK

async def pomo_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Привязка сессии к задаче и запуск через PomoService."""
    task_title = update.message.text.strip().lower()
    from bot import uid
    user_id = uid(update)
    
    task_id = None
    if task_title != "пропустить":
        import db
        task = db.find_task_by_title(user_id, task_title)
        if task:
            task_id = task["id"]
        else:
            await update.message.reply_text("Задача не найдена, запускаю общий таймер.")

    duration = context.user_data.get("pomo_duration", 25)
    
    try:
        session_id, end_time = PomoService.start_session(user_id, duration, task_id)
        context.user_data["active_pomo_id"] = session_id
        
        text = (
            f"🍅 Pomodoro запущен!\n"
            f"⏱ Длительность: {duration} мин\n"
            f"🏁 Завершится в: {end_time.strftime('%H:%M')}"
        )
        await update.message.reply_text(text)
    except BotError as e:
        await update.message.reply_text(f"❌ Ошибка запуска: {e.message}")
        return ConversationHandler.END

    return ConversationHandler.END

async def stop_pomo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ручная остановка/завершение помидора через PomoService."""
    session_id = context.user_data.get("active_pomo_id")
    if not session_id:
        await update.message.reply_text("У вас нет активного таймера.")
        return

    try:
        PomoService.stop_session(session_id)
        await update.message.reply_text("Сессия Pomodoro завершена! Отдыхайте. ✅")
        context.user_data.pop("active_pomo_id", None)
    except BotError as e:
        await update.message.reply_text(f"❌ Ошибка: {e.message}")
