# AIQuotaFlow — Master Prompt for Implementation

Ты — senior full-stack engineer, DevOps engineer и product architect.
Твоя задача: реализовать production-ready MVP Telegram-бота **AIQuotaFlow** — инструмента для ручного учёта AI-подписок, отслеживания cooldown-лимитов и получения уведомлений о восстановлении квот.

---

## ЧТО ТАКОЕ ЭТОТ ПРОЕКТ

AIQuotaFlow — это личный планировщик AI-аккаунтов. Аналог планировщика стиральных машин в общежитии: пользователь сам отмечает «занял аккаунт», бот считает время и присылает уведомление когда квота восстановилась.

**Проект НЕ предназначен для:**
- обхода ограничений провайдеров
- автоматизации логинов
- scraping или browser automation
- хранения паролей, токенов, OTP, cookies
- управления чужими аккаунтами
- автоматического переключения между аккаунтами

**Проект предназначён исключительно для:**
- ручного учёта AI-подписок
- отслеживания cooldown-таймеров
- уведомлений о восстановлении квот
- workspace-фильтрации аккаунтов по целям использования

---

## ТЕХНОЛОГИЧЕСКИЙ СТЕК

```
Python 3.12+
aiogram 3.x              — Telegram Bot framework
SQLAlchemy (async)       — ORM
aiosqlite                — async SQLite driver
APScheduler 3.x          — планировщик уведомлений
Pydantic v2 + pydantic-settings — конфиг и валидация
python-dotenv            — .env поддержка
Docker + Docker Compose  — деплой
```

---

## ИНФРАСТРУКТУРА

- VPS, Ubuntu 24.04
- Docker Compose, long polling (без webhook)
- SQLite (один файл, простой бэкап)
- Без Redis, Kubernetes, облачных сервисов
- Целевые ресурсы: 1 vCPU, 2 GB RAM, 20 GB SSD

---

## СТРУКТУРА ПРОЕКТА

```
aiquotaflow/
├── bot/
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── subscriptions.py
│   │   ├── status.py
│   │   ├── settings.py
│   │   └── help.py
│   ├── fsm/
│   │   ├── __init__.py
│   │   └── add_subscription.py
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── main_menu.py
│   │   └── subscription.py
│   └── middlewares/
│       ├── __init__.py
│       └── user_middleware.py
├── core/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── subscription.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_repo.py
│   │   └── subscription_repo.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── subscription_service.py
│   │   ├── status_service.py
│   │   └── notification_service.py
│   └── schemas/
│       ├── __init__.py
│       ├── user.py
│       └── subscription.py
├── scheduler/
│   ├── __init__.py
│   ├── setup.py
│   └── jobs.py
├── db/
│   ├── __init__.py
│   ├── engine.py
│   └── base.py
├── config.py
├── main.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## МОДЕЛИ ДАННЫХ

### User

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None]
    first_name: Mapped[str | None]
    timezone: Mapped[str] = mapped_column(default="UTC")          # IANA: "Europe/Moscow"
    reminder_minutes: Mapped[int] = mapped_column(default=15)     # уведомление за N минут до сброса
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### SubscriptionAccount

```python
class SubscriptionAccount(Base):
    __tablename__ = "subscription_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    provider: Mapped[str]           # "Claude", "ChatGPT", "Gemini", "Grok", "Custom"
    account_name: Mapped[str]       # обязательно — "Claude работа", "GPT Research"
    login_email: Mapped[str | None] # опционально — для тех кому нужно различать аккаунты
    plan: Mapped[str]               # "Free", "Pro", "Max", "Team", "Custom"

    current_status: Mapped[str] = mapped_column(default="available")
    # available | cooldown | exhausted | inactive

    cooldown_until: Mapped[datetime | None]       # UTC, когда восстановится квота
    subscription_end_date: Mapped[date | None]    # когда истекает подписка
    notes: Mapped[str | None]                     # произвольные заметки

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # relationships
    purposes: Mapped[list["Purpose"]] = relationship(
        secondary="subscription_purposes", back_populates="subscriptions"
    )
```

### Purpose (workspace)

```python
class Purpose(Base):
    __tablename__ = "purposes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str]   # свободный текст: "SaaS проект", "🎓", "работа", "2"
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    subscriptions: Mapped[list["SubscriptionAccount"]] = relationship(
        secondary="subscription_purposes", back_populates="purposes"
    )

# Join table
class SubscriptionPurpose(Base):
    __tablename__ = "subscription_purposes"

    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscription_accounts.id"), primary_key=True)
    purpose_id: Mapped[int] = mapped_column(ForeignKey("purposes.id"), primary_key=True)
```

**Важно: НЕ хранить** пароли, OTP, recovery phrases, cookies, session tokens, API keys.

---

## ЛОГИКА ВИЗУАЛЬНОГО СТАТУСА

Статус вычисляется динамически в service layer, НЕ хранится в БД.

```python
from enum import Enum
from datetime import datetime, timezone, timedelta

class StatusColor(Enum):
    GREEN = "🟢"
    YELLOW = "🟡"
    RED = "🔴"

def get_visual_status(subscription: SubscriptionAccount) -> StatusColor:
    now = datetime.now(timezone.utc)

    # Неактивна или исчерпана
    if subscription.current_status in ("exhausted", "inactive"):
        return StatusColor.RED

    # Подписка истекла
    if subscription.subscription_end_date:
        if subscription.subscription_end_date < now.date():
            return StatusColor.RED

    # Нет cooldown — доступна
    if not subscription.cooldown_until:
        return StatusColor.GREEN

    # cooldown завершён — автоматически доступна
    if subscription.cooldown_until <= now:
        return StatusColor.GREEN

    # cooldown в пределах 24 часов
    if subscription.cooldown_until <= now + timedelta(hours=24):
        return StatusColor.YELLOW

    # cooldown дольше 24 часов
    return StatusColor.RED
```

---

## COOLDOWN ЛОГИКА

Когда пользователь упёрся в лимит:

1. Выбирает аккаунт → нажимает "⏳ Cooldown"
2. Выбирает время: **1ч | 3ч | 5ч | 6ч | 12ч | 24ч | своё**
   - 5 часов — дефолтная кнопка для Claude (rolling window)
3. Бот устанавливает `cooldown_until = now + duration`, `current_status = "cooldown"`
4. APScheduler создаёт job на момент `cooldown_until`
5. В момент сброса бот присылает уведомление и меняет `current_status = "available"`

**Примечание по 5-часовому окну Claude:**
Лимит стартует с первого промпта сессии, не по расписанию. Поэтому пользователь сам нажимает "Cooldown" в момент когда уткнулся в лимит.

---

## УВЕДОМЛЕНИЯ

Три типа jobs в APScheduler:

```python
# 1. Cooldown завершён
async def notify_cooldown_finished(bot, user_telegram_id, subscription_id):
    # Обновить статус → available
    # Отправить сообщение

# 2. Подписка истекает скоро (за reminder_minutes до конца дня subscription_end_date)
async def notify_subscription_expiring(bot, user_telegram_id, subscription_id):
    ...

# 3. Подписка истекла
async def notify_subscription_expired(bot, user_telegram_id, subscription_id):
    ...
```

**APScheduler persistence:** использовать `SQLAlchemyJobStore` на той же SQLite БД.
Это обязательно — иначе после рестарта Docker все jobs теряются.

```python
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///data/aiquotaflow.db')
}
```

---

## TELEGRAM UX

### Главное меню (/start)

```
Привет, {first_name}! 👋

📋 Мои подписки    📊 Статусы
⚙️ Настройки       ❓ Помощь
```

4 кнопки, ничего лишнего.

### 📋 Мои подписки — список

```
📋 Мои подписки

🟢 ivan.work@gmail.com
   Claude · Max · SaaS проект

🟡 ivan.side@gmail.com
   Claude · Pro · Диссертация
   Сброс через 2ч 47м

🔴 ivan.old@gmail.com
   Claude · Pro
   Недельный лимит

➕ Добавить   ⬅️ Назад
```

**Логика отображения имени аккаунта:**
- Если `login_email` заполнен → показывать email
- Если нет → показывать `account_name`

### Экран аккаунта

```
🟡 ivan.side@gmail.com
Claude Pro

📧 ivan.side@gmail.com
🏷 account_name: "Claude side"
📅 Подписка до: 15 июля 2025
⏰ Cooldown до: 16:47 (через 2ч 47м)
🎯 Цели: Диссертация, SaaS проект
📝 Заметки: основной рабочий

⏳ Cooldown   ✅ Доступен   🔴 Исчерпан
✏️ Редактировать   🗑 Удалить
⬅️ Назад
```

### ⏳ Cooldown — быстрые кнопки

```
Выбери время cooldown:

1ч    3ч    5ч ⭐
6ч    12ч   24ч
✍️ Своё время

⬅️ Назад
```

5ч отмечена ⭐ как рекомендованная для Claude Pro.

### 📊 Статусы

```
📊 Статусы

Все аккаунты | SaaS проект | Диссертация

🟢 Доступны сейчас:
• ivan.work@gmail.com — Claude Max

🟡 Восстановятся в течение 24ч:
• ivan.side@gmail.com — через 2ч 47м

🔴 Недоступны:
• ivan.old@gmail.com — недельный лимит
```

Workspace-фильтр: кнопки сверху переключают между "все" и конкретными purposes.

### ➕ Добавление подписки — FSM wizard

**Обязательных шагов — 3:**

1. Provider (кнопки): Claude | ChatGPT | Gemini | Grok | Custom
2. Название аккаунта (текст): "Введи название — например 'Claude работа' или email"
3. Plan (кнопки): Free | Pro | Max | Team | Custom

**После создания — предложить опциональные поля:**

```
✅ Аккаунт добавлен!

Хочешь добавить детали?
📧 Email   🎯 Цели
📅 Дата подписки   📝 Заметки
⏭ Пропустить
```

### ⚙️ Настройки

```
⚙️ Настройки

🌍 Часовой пояс: Europe/Moscow
⏰ Напоминание за: 15 минут
🔔 Уведомления: ВКЛ
🕐 Формат времени: 24ч
📋 Сортировка: по статусу
```

### ❓ Помощь

```
❓ Помощь

🟢 Зелёный — аккаунт свободен
🟡 Жёлтый — cooldown < 24 часов
🔴 Красный — cooldown > 24ч или истёк

Команды:
/start — главное меню
/status — быстрый статус
/add — добавить аккаунт

По вопросам: @username
```

---

## WORKSPACE (PURPOSES) ЛОГИКА

Purpose — отдельная сущность, не просто строка. Это нужно для корректной фильтрации.

**Создание workspace:**
- Пользователь вводит свободный текст: "SaaS проект", "🎓", "работа", "2"
- Никакого предустановленного списка

**Привязка аккаунтов к workspace:**
- Many-to-many: один аккаунт может быть в нескольких workspace
- Управляется через экран редактирования аккаунта

**Workspace view в Статусах:**
- Кнопки-фильтры: "Все" + имя каждого workspace пользователя
- При выборе workspace — показывать только привязанные аккаунты с их статусами

---

## MULTI-USER АРХИТЕКТУРА

- Telegram ID = primary auth identity
- Регистрация при первом /start автоматически
- Все данные изолированы по `owner_id`
- user_middleware создаёт/обновляет запись пользователя при каждом обращении

```python
class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_service = data["user_service"]
        tg_user = event.from_user
        user = await user_service.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        data["current_user"] = user
        return await handler(event, data)
```

---

## SCHEDULER SETUP

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def create_scheduler(db_url: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(
        jobstores={'default': SQLAlchemyJobStore(url=db_url)},
        job_defaults={'coalesce': True, 'max_instances': 1},
        timezone='UTC'
    )
```

Scheduler запускается как asyncio task в `main.py`, не в отдельном thread.

При установке cooldown:

```python
scheduler.add_job(
    notify_cooldown_finished,
    trigger='date',
    run_date=cooldown_until,
    args=[bot, user.telegram_id, subscription.id],
    id=f"cooldown_{subscription.id}",
    replace_existing=True,   # перезаписывает если cooldown обновили
)
```

---

## КОНФИГ

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///data/aiquotaflow.db"
    LOG_LEVEL: str = "INFO"
    ADMIN_IDS: list[int] = []

    class Config:
        env_file = ".env"

settings = Settings()
```

```env
# .env.example
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=sqlite+aiosqlite:///data/aiquotaflow.db
LOG_LEVEL=INFO
```

---

## DOCKER

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data        # SQLite persistence
      - ./.env:/app/.env
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/aiquotaflow.db
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## LOGGING

```python
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
```

Логировать: startup, shutdown, scheduler jobs, errors, новые пользователи.

---

## MAIN.PY BOOTSTRAP

```python
async def main():
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting AIQuotaFlow bot...")

    # DB init
    await init_db()

    # Bot + dispatcher
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Middlewares
    dp.update.middleware(UserMiddleware())

    # Routers
    dp.include_router(start_router)
    dp.include_router(subscriptions_router)
    dp.include_router(status_router)
    dp.include_router(settings_router)
    dp.include_router(help_router)

    # Scheduler
    scheduler = create_scheduler(settings.DATABASE_URL)
    scheduler.start()

    logger.info("Bot started, polling...")
    try:
        await dp.start_polling(bot, scheduler=scheduler)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")
```

---

## ПОРЯДОК РЕАЛИЗАЦИИ

Реализуй строго в этом порядке, каждый шаг как отдельный коммит:

1. `config.py`, `.env.example`, `requirements.txt`
2. `db/engine.py`, `db/base.py` — async engine, session factory
3. `core/models/` — все модели (User, SubscriptionAccount, Purpose, SubscriptionPurpose)
4. `core/repositories/` — base repo + user_repo + subscription_repo + purpose_repo
5. `core/services/status_service.py` — логика визуального статуса
6. `core/services/subscription_service.py`, `user_service.py`
7. `bot/middlewares/user_middleware.py`
8. `bot/keyboards/` — main_menu, subscription keyboards
9. `bot/handlers/start.py` — /start, главное меню
10. `bot/fsm/add_subscription.py` — FSM wizard добавления
11. `bot/handlers/subscriptions.py` — просмотр, управление, cooldown
12. `bot/handlers/status.py` — dashboard + workspace фильтр
13. `bot/handlers/settings.py`, `help.py`
14. `scheduler/setup.py`, `scheduler/jobs.py`
15. `main.py` — сборка всего
16. `Dockerfile`, `docker-compose.yml`

---

## ВАЖНЫЕ ТРЕБОВАНИЯ К КОДУ

- Python typing везде (Mapped[], Annotated[], etc.)
- async/await везде где возможно
- Repository pattern — handlers не обращаются к БД напрямую
- Service layer — бизнес-логика только в services
- Ошибки обрабатываются gracefully, пользователь получает понятное сообщение
- Все datetime хранить в UTC, отображать в timezone пользователя через `zoneinfo`
- FSM states — строгая типизация через StatesGroup

---

## FUTURE-READY (не реализовывать сейчас)

Архитектура должна позволять в будущем добавить без переписывания:
- PostgreSQL (поменять только DATABASE_URL и драйвер)
- Web dashboard / REST API (services независимы от Telegram)
- Mobile app
- Export/import данных
- Shared subscriptions (командное использование)
- Analytics

---

## ФИНАЛЬНЫЙ ЧЕКЛИСТ ПЕРЕД ДЕПЛОЕМ

- [ ] `.env` не попадает в git (`.gitignore`)
- [ ] `data/` директория создаётся автоматически
- [ ] APScheduler jobs переживают рестарт контейнера
- [ ] Все cooldown timers корректно обновляются при изменении
- [ ] Timezone корректно применяется к отображению времени
- [ ] Multi-user изоляция — пользователь видит только свои данные
- [ ] Graceful shutdown бота и scheduler
