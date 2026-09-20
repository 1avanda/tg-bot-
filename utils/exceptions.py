class BotError(Exception):
    """Базовый класс для всех исключений приложения."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DatabaseError(BotError):
    """Ошибка при работе с базой данных."""
    pass

class AIProviderError(BotError):
    """Ошибка при взаимодействии с ИИ-провайдером."""
    pass

class ValidationError(BotError):
    """Ошибка валидации входных данных."""
    pass

class NotFoundError(BotError):
    """Ошибка, когда запрашиваемый объект не найден."""
    pass
