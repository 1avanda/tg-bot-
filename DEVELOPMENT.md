# Guide for Developers

This project follows professional software engineering standards. If you want to contribute or extend the functionality, please follow these guidelines.

## 🏗 Adding a New Feature

### 1. Data Layer (`db.py`)
If the feature requires new data, add the necessary tables to `init_db()` and create CRUD functions.

### 2. Service Layer (`services.py`)
Create a new Service class or add methods to existing ones. All business logic and validations must reside here. Never call `db.py` directly from handlers.

### 3. Interface Layer (`handlers/`)
Create a new handler module in `handlers/` or add functions to existing ones. Use `utils/keyboards.py` for any UI elements.

### 4. Registration (`bot.py`)
Register your new handlers or ConversationHandlers in the `main()` function of `bot.py`.

## ⚠️ Coding Standards
- **Type Hinting**: All functions must have type hints for arguments and return values.
- **Error Handling**: Use custom exceptions from `utils/exceptions.py`. Do not use bare `except: pass`.
- **UI**: All keyboards must be defined in `utils/keyboards.py`.
- **Docstrings**: Use Google Style docstrings for all public methods.
