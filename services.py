from typing import List, Dict, Any, Optional
from datetime import datetime
import db
from utils.exceptions import DatabaseError, ValidationError, NotFoundError

class TaskService:
    """Сервис для управления задачами пользователя."""
    
    @staticmethod
    def create_task(user_id: int, title: str, description: Optional[str], category: str, deadline: datetime) -> int:
        """Создает новую задачу с валидацией данных."""
        if not title or len(title.strip()) == 0:
            raise ValidationError("Название задачи не может быть пустым.")
        
        if deadline < datetime.now():
            raise ValidationError("Дата дедлайна не может быть в прошлом.")
            
        try:
            return db.add_task(
                user_id, 
                title.strip(), 
                description, 
                category, 
                deadline.strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            raise DatabaseError(f"Ошибка при сохранении задачи в БД: {e}")

    @staticmethod
    def get_user_tasks(user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список активных задач пользователя."""
        try:
            return db.get_tasks(user_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при получении списка задач: {e}")

    @staticmethod
    def get_task_details(task_id: int) -> Dict[str, Any]:
        """Получает детали конкретной задачи."""
        task = db.get_task(task_id)
        if not task:
            raise NotFoundError("Задача не найдена.")
        return task

    @staticmethod
    def mark_as_done(task_id: int) -> None:
        """Отмечает задачу как выполненную."""
        try:
            db.complete_task(task_id)
        except Exception as e:
            raise DatabaseError(f"Не удалось отметить задачу как выполненную: {e}")

    @staticmethod
    def delete_task(task_id: int) -> None:
        """Удаляет задачу из системы."""
        try:
            db.delete_task(task_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при удалении задачи: {e}")

class HabitService:
    """Сервис для управления привычками."""
    
    @staticmethod
    def create_habit(user_id: int, name: str, period_type: str, period_value: str, reminder_time: str) -> int:
        """Создает новую привычку."""
        if not name or len(name.strip()) == 0:
            raise ValidationError("Название привычки не может быть пустым.")
            
        try:
            return db.add_habit(user_id, name.strip(), period_type, period_value, reminder_time)
        except Exception as e:
            raise DatabaseError(f"Ошибка при создании привычки: {e}")

    @staticmethod
    def get_user_habits(user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список привычек пользователя."""
        try:
            return db.get_habits(user_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при получении списка привычек: {e}")

    @staticmethod
    def check_habit(habit_id: int) -> bool:
        """Отмечает выполнение привычки и обновляет серию (streak)."""
        try:
            return db.check_habit(habit_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при отметке привычки: {e}")

class PomoService:
    """Сервис для управления сессиями Pomodoro."""
    
    @staticmethod
    def start_session(user_id: int, duration: int, task_id: Optional[int] = None) -> Tuple[int, datetime]:
        """Запускает новую Pomodoro-сессию."""
        if duration < 1 or duration > 1440:
            raise ValidationError("Длительность должна быть от 1 до 1440 минут.")
            
        try:
            return db.start_pomodoro(user_id, duration, task_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при запуске таймера: {e}")

    @staticmethod
    def stop_session(session_id: int) -> None:
        """Завершает текущую сессию."""
        try:
            db.complete_pomodoro(session_id)
        except Exception as e:
            raise DatabaseError(f"Ошибка при остановке таймера: {e}")
