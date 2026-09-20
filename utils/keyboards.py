from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# --- Константы Меню ---
MENU_NEW_TASK = "Новая задача"
MENU_MY_TASKS = "Мои задачи"
MENU_HABITS = "Привычки"
MENU_POMO = "Pomodoro"
MENU_STATS = "Статистика"
MENU_HELP = "Помощь"

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает главную клавиатуру управления ботом."""
    return ReplyKeyboardMarkup(
        [
            [MENU_NEW_TASK, MENU_MY_TASKS],
            [MENU_HABITS, MENU_POMO],
            [MENU_STATS, MENU_HELP],
            ["🤖 ИИ-Помощник"],
        ],
        resize_keyboard=True,
    )

def task_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора категории задачи."""
    return InlineKeyboardMarkup(
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

def task_date_keyboard(today_str: str, tomorrow_str: str, after_tomorrow_str: str) -> InlineKeyboardMarkup:
    """Клавиатура для быстрого выбора даты дедлайна."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Сегодня ({today_str})", callback_data="today"),
                InlineKeyboardButton(f"Завтра ({tomorrow_str})", callback_data="tomorrow"),
            ],
            [
                InlineKeyboardButton(f"Послезавтра ({after_tomorrow_str})", callback_data="after_tomorrow"),
                InlineKeyboardButton("Своя дата", callback_data="custom_date"),
            ],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )

def task_time_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для быстрого выбора времени."""
    return InlineKeyboardMarkup(
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

def habit_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора периодичности привычки."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Ежедневно", callback_data="daily")],
            [InlineKeyboardButton("Через день", callback_data="every_2_days")],
            [InlineKeyboardButton("По дням недели", callback_data="weekly")],
            [InlineKeyboardButton("По выходным", callback_data="weekend")],
            [InlineKeyboardButton("Свой интервал (дни)", callback_data="custom_days")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")],
        ]
    )

def habit_days_keyboard(selected_days: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора конкретных дней недели."""
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard = []
    row = []
    for i, day in enumerate(days, start=1):
        # Здесь можно добавить визуальную отметку выбранных дней, если нужно
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
    return InlineKeyboardMarkup(keyboard)
