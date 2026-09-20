import json
import os
import re
import logging
from datetime import date, datetime, timedelta

import httpx
import google.generativeai as genai

logger = logging.getLogger(__name__)

CATEGORIES = {"work", "personal", "study", "other"}
INTENTS = {
    "add_task",
    "complete_task",
    "add_habit",
    "check_habit",
    "start_pomodoro",
    "list_tasks",
    "none",
}

SYSTEM_PROMPT = """Ты — парсер намерений пользователя для бота продуктивности. 
Твоя задача: проанализировать текст и вернуть СТРОГИЙ JSON.

Доступные интенты (intent):
- add_task: пользователь хочет создать задачу.
- complete_task: пользователь отмечает задачу выполненной.
- add_habit: пользователь хочет завести новую привычку.
- check_habit: пользователь отмечает выполнение привычки.
- start_pomodoro: запуск таймера помидора.
- list_tasks: запрос списка задач.
- none: запрос не относится к этим действиям.

Формат JSON:
{{
  "intent": "название_интента",
  "title": "название задачи или привычки (если есть)",
  "description": "описание (если есть)",
  "category": "work/personal/study/other",
  "deadline": "YYYY-MM-DD HH:MM:SS (если указано)",
  "habit_name": "название привычки",
  "period_type": "daily/weekly/etc",
  "period_value": "значение периода",
  "duration": "длительность помидора в минутах (число)",
  "confidence": 0.0-1.0
}}

Сегодняшняя дата: {today}
Текущее время: {now}

Отвечай ТОЛЬКО чистым JSON.
"""

AI_ASSISTANT_PROMPT = """Ты — экспертный ИИ-ассистент по продуктивности. Твоя цель — помогать пользователю эффективно управлять своим временем, задачами и привычками.

Твои принципы:
1. Будь кратким, поддерживающим и структурированным.
2. Если пользователь делится данными о своих задачах или привычках, анализируй их и давай советы (например, по технике Pomodoro, матрице Эйзенхауэра или методу маленьких шагов).
3. Помогай разбивать сложные задачи на простые действия.
4. Мотивируй, но не будь навязчивым.
5. Ограничивайся темами продуктивности, тайм-менеджмента и саморазвития. Если вопрос совсем не об этом, вежливо верни пользователя к теме продуктивности.

Текущий контекст пользователя:
{context}

Отвечай дружелюбно и на русском языке.
"""


def empty_action(intent="none", confidence=0.0):
    return {
        "intent": intent,
        "title": None,
        "description": None,
        "category": "other",
        "deadline": None,
        "habit_name": None,
        "period_type": None,
        "period_value": None,
        "duration": None,
        "confidence": confidence,
    }


def parse_date(date_str):
    parts = date_str.strip().split(".")
    if len(parts) == 2:
        day, month = parts
        year = date.today().year
    elif len(parts) == 3:
        day, month, year = parts
        if len(str(year)) == 2:
            year = 2000 + int(year)
    else:
        return None
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _weekday_date(name):
    names = {
        "понедельник": 0,
        "вторник": 1,
        "среда": 2,
        "среду": 2,
        "четверг": 3,
        "пятница": 4,
        "пятницу": 4,
        "суббота": 5,
        "субботу": 5,
        "воскресенье": 6,
    }
    if name not in names:
        return None
    today = date.today()
    target = names[name]
    delta = (target - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _extract_when(text):
    today = date.today()
    selected = None
    if re.search(r"\bпослезавтра\b", text):
        selected = today + timedelta(days=2)
    elif re.search(r"\bзавтра\b", text):
        selected = today + timedelta(days=1)
    elif re.search(r"\bсегодня\b", text):
        selected = today
    else:
        m = re.search(
            r"\b(в\s+)?(понедельник|вторник|среду|среда|четверг|пятницу|пятница|субботу|суббота|воскресенье)\b",
            text,
        )
        if m:
            selected = _weekday_date(m.group(2))
        else:
            m = re.search(r"\b(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\b", text)
            if m:
                selected = parse_date(m.group(1))

    time_str = "18:00"
    tm = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
    if tm:
        time_str = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    else:
        tm = re.search(r"\bв\s+([01]?\d|2[0-3])\s*(?:час(?:а|ов)?)?\b", text)
        if tm:
            time_str = f"{int(tm.group(1)):02d}:00"

    if selected is None:
        selected = today
        if datetime.now().hour >= 18:
            selected = today + timedelta(days=1)

    return datetime.strptime(f"{selected.isoformat()} {time_str}", "%Y-%m-%d %H:%M")


def _clean_title(text):
    text = text.strip()
    text = re.sub(
        r"^(добавь|создай|поставь|запиши|напомни(?:ть)?|надо|нужно|задача[:\s]*)\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b(сегодня|завтра|послезавтра)\b", "", text, flags=re.I)
    text = re.sub(
        r"\bв\s+(понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)\b",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b", "", text)
    text = re.sub(r"\bв\s+\d{1,2}([:.]\d{2})?\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!")
    return text or "Задача"


def fallback_parse(text):
    raw = text.strip()
    t = raw.lower()

    if re.search(r"\b(какие задачи|мои задачи|список задач|что на сегодня)\b", t):
        return empty_action("list_tasks", 0.8)

    if re.search(r"\b(помидор|помодор|pomodoro|сфокусируйся|таймер)\b", t):
        action = empty_action("start_pomodoro", 0.75)
        m = re.search(r"(\d+)\s*(?:мин|минуты|минуту|минут)", t)
        if not m:
            m = re.search(r"(\d+)", t)
        action["duration"] = int(m.group(1)) if m else 25
        return action

    if re.search(r"\b(отметь привычк|привычка выполнена|сделал привычк)\b", t):
        action = empty_action("check_habit", 0.7)
        m = re.search(r"привычк[уиа]\s+(.+)$", raw, flags=re.I)
        action["habit_name"] = m.group(1).strip() if m else raw
        return action

    if re.search(r"\b(привычк|каждый день|ежедневн)\b", t) and re.search(
        r"\b(добавь|создай|хочу|начать)\b", t
    ):
        action = empty_action("add_habit", 0.7)
        name = re.sub(r".*привычк[уиа]\s*", "", raw, flags=re.I).strip() or raw
        action["habit_name"] = name[:80]
        action["period_type"] = "daily"
        action["period_value"] = "1"
        return action

    if re.search(r"\b(сделал|выполнил|готово|закрыл задачу)\b", t):
        action = empty_action("complete_task", 0.7)
        title = re.sub(r"^(я\s+)?(сделал|выполнил|готово|закрыл задачу)\s*", "", raw, flags=re.I)
        action["title"] = title.strip() or None
        return action

    looks_like_task = bool(
        re.search(r"\b(добавь|создай|поставь|запиши|напомни|надо|нужно|задача)\b", t)
        or re.search(r"\b(сегодня|завтра|послезавтра|\d{1,2}[:.]\d{2})\b", t)
    )
    if looks_like_task:
        action = empty_action("add_task", 0.72)
        action["title"] = _clean_title(raw)
        action["deadline"] = _extract_when(t).strftime("%Y-%m-%d %H:%M:%S")
        if re.search(r"\b(урок|дз|домашк|экзамен|учеба|учёба)\b", t):
            action["category"] = "study"
        elif re.search(r"\b(работ|встреч|созвон|отчёт|отчет)\b", t):
            action["category"] = "work"
        elif re.search(r"\b(мама|друг|магазин|дом)\b", t):
            action["category"] = "personal"
        return action

    return empty_action("none", 0.2)


def _normalize(data):
    action = empty_action()
    if not isinstance(data, dict):
        return action
    intent = data.get("intent") or "none"
    action["intent"] = intent if intent in INTENTS else "none"
    action["title"] = data.get("title") or None
    action["description"] = data.get("description") or None
    cat = data.get("category") or "other"
    action["category"] = cat if cat in CATEGORIES else "other"
    action["deadline"] = data.get("deadline") or None
    if action["deadline"]:
        dl = str(action["deadline"]).replace("T", " ")[:19]
        if len(dl) == 16:
            dl += ":00"
        try:
            datetime.strptime(dl, "%Y-%m-%d %H:%M:%S")
            action["deadline"] = dl
        except ValueError:
            action["deadline"] = None
    action["habit_name"] = data.get("habit_name") or None
    action["period_type"] = data.get("period_type") or "daily"
    action["period_value"] = data.get("period_value") or "1"
    dur = data.get("duration")
    try:
        action["duration"] = int(dur) if dur else None
    except (TypeError, ValueError):
        action["duration"] = None
    try:
        action["confidence"] = float(data.get("confidence") or 0)
    except (TypeError, ValueError):
        action["confidence"] = 0.0
    return action


def _get_gemini_model():
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or not gemini_key.strip():
        return None
    try:
        genai.configure(api_key=gemini_key)
        return genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        logger.error(f"Gemini configuration error: {e}")
        return None

async def llm_parse(text):
    model = _get_gemini_model()
    if model:
        try:
            prompt = SYSTEM_PROMPT.format(
                today=date.today().isoformat(),
                now=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
            response = model.generate_content(f"{prompt}\n\nUser text: {text}")
            content = response.text.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
            return _normalize(json.loads(content))
        except Exception as e:
            logger.error(f"Gemini parse error: {e}")

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    
    base = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
    model_name = os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"
    prompt = SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model_name,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    return _normalize(json.loads(content))


async def ai_assistant_reply(text, user_context=None):
    model = _get_gemini_model()

    if model:
        try:
            prompt = AI_ASSISTANT_PROMPT.format(context=user_context or "Нет данных о пользователе")
            response = model.generate_content(f"{prompt}\n\nUser request: {text}")
            return response.text.strip()
        except Exception as e:
            return f"Произошла ошибка при обращении к Gemini API: {e}"

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Ошибка конфигурации: Я не нашел ни GEMINI_API_KEY, ни DEEPSEEK_API_KEY в вашем файле .env."

    base = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
    model_name = os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"
    prompt = AI_ASSISTANT_PROMPT.format(context=user_context or "Нет данных о пользователе")
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model_name,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Произошла ошибка при обращении к ИИ (DeepSeek/OpenAI): {e}"

async def parse_user_text(text):
    fallback = fallback_parse(text)
    try:
        llm = await llm_parse(text)
    except Exception:
        llm = None
    if llm and llm["intent"] != "none" and llm["confidence"] >= 0.45:
        llm["source"] = "llm"
        return llm
    fallback["source"] = "rules"
    return fallback


def describe_action(action):
    intent = action["intent"]
    if intent == "add_task":
        when = action.get("deadline") or "без срока"
        return f"Создать задачу «{action.get('title')}»\nСрок: {when}\nКатегория: {action.get('category')}"
    if intent == "complete_task":
        return f"Отметить задачу выполненной: «{action.get('title') or 'ближайшую подходящую'}»"
    if intent == "add_habit":
        return f"Создать привычку «{action.get('habit_name')}» ({action.get('period_type')})"
    if intent == "check_habit":
        return f"Отметить привычку: «{action.get('habit_name')}»"
    if intent == "start_pomodoro":
        return f"Запустить Pomodoro на {action.get('duration') or 25} мин"
    if intent == "list_tasks":
        return "Показать список задач"
    return "Не понял запрос"
