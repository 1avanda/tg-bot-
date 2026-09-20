from telegram import Update
from telegram.ext import ContextTypes
import db
from bot import uid

def get_user_id(update: Update) -> int:
    """Вспомогательная функция для получения внутреннего ID пользователя."""
    return uid(update)
