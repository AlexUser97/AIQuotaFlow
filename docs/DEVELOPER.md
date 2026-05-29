# AIQuotaFlow — гайд для разработчика

Этот документ — длинное «как и почему» для тех, кто хочет:

1. Разобраться, как устроен этот конкретный бот.
2. Понять общую процедуру создания Telegram-ботов на Python — на боевом примере.
3. Узнать, куда копать дальше, чтобы перестать копировать чужой код и писать свой.

Я предполагаю, что ты уже умеешь писать на Python простые скрипты, видел `async/await`, но Telegram-бота своими руками ещё не собирал. Если что-то знакомо — пролистывай.

---

## Оглавление

1. [Идея и контекст](#1-идея-и-контекст)
2. [Анатомия Telegram-бота](#2-анатомия-telegram-бота)
3. [Технологический стек и почему именно он](#3-технологический-стек-и-почему-именно-он)
4. [Архитектура проекта по слоям](#4-архитектура-проекта-по-слоям)
5. [Слой конфигурации: `config.py` и `.env`](#5-слой-конфигурации-configpy-и-env)
6. [Слой БД: `db/`](#6-слой-бд-db)
7. [Доменные модели: `core/models/`](#7-доменные-модели-coremodels)
8. [Репозитории: `core/repositories/`](#8-репозитории-corerepositories)
9. [Сервисы: `core/services/`](#9-сервисы-coreservices)
10. [Telegram-слой: aiogram 3](#10-telegram-слой-aiogram-3)
11. [Middleware и Dependency Injection](#11-middleware-и-dependency-injection)
12. [Клавиатуры](#12-клавиатуры)
13. [Хендлеры и роутеры](#13-хендлеры-и-роутеры)
14. [FSM — конечный автомат для многошаговых диалогов](#14-fsm--конечный-автомат-для-многошаговых-диалогов)
15. [Планировщик: APScheduler с persistent jobstore](#15-планировщик-apscheduler-с-persistent-jobstore)
16. [Сборка приложения: `main.py`](#16-сборка-приложения-mainpy)
17. [Деплой через Docker](#17-деплой-через-docker)
18. [Типичные ошибки и как их ловил я](#18-типичные-ошибки-и-как-их-ловил-я)
19. [Как развивать проект дальше](#19-как-развивать-проект-дальше)
20. [Дополнительная литература](#20-дополнительная-литература)

---

## 1. Идея и контекст

Сначала самое важное — **зачем вообще писать бота**.

У многих сейчас по 2–5 AI-аккаунтов: основной Claude Pro, второй Claude для пет-проекта, ChatGPT, может Gemini. Каждый имеет свои лимиты: Claude Pro — rolling window 5 часов, ChatGPT — суточный, у Free вообще плавающие. В голове это всё держать невозможно. Бот выступает в роли «диспетчера» — ты вручную говоришь «занял этот аккаунт», он считает таймер и пингует, когда квота восстановилась.

Это пример **CRUD-приложения с уведомлениями по расписанию**. Понять его — значит понять 80% реальных ботов, потому что ровно такая же архитектура у трекеров, напоминалок, дашбордов, чек-листов и личных ассистентов.

---

## 2. Анатомия Telegram-бота

Любой Telegram-бот — это **серверное приложение**, которое общается с серверами Telegram по HTTP.

Два способа получать сообщения от пользователей:

| Способ          | Как работает                                                                 | Когда выбирать                                  |
|-----------------|------------------------------------------------------------------------------|-------------------------------------------------|
| **Long polling**| Бот сам опрашивает Telegram: «есть новые сообщения?» и ждёт ответа           | MVP, простой VPS, нет публичного домена/HTTPS   |
| **Webhook**     | Telegram POST'ит на твой публичный HTTPS-эндпоинт сразу при новом сообщении  | Production с доменом, нужна минимальная задержка|

Мы выбрали **long polling**, потому что:

- не нужен HTTPS-домен и сертификат,
- проще тестировать и дебажить,
- ресурсов на VPS почти не расходует (одно соединение к Telegram).

Webhook быстрее, но требует дополнительной инфраструктуры (TLS, reverse proxy, проверка подписи запросов). Можно мигрировать позже — aiogram поддерживает обе схемы, бизнес-код менять не придётся.

### Telegram Bot API в трёх словах

- Каждый бот — это HTTP-аккаунт у Telegram, идентифицируется **токеном** (выдаёт [@BotFather](https://t.me/BotFather)).
- Все операции — это вызовы методов вроде `sendMessage`, `editMessageText`, `answerCallbackQuery` через `https://api.telegram.org/bot<TOKEN>/<method>`.
- Сообщения, нажатия кнопок и прочие события приходят в одном формате — `Update`.

Библиотеки (aiogram, python-telegram-bot, telebot) — это обёртки, которые превращают сырой HTTP в удобные Python-вызовы и роутят `Update` в твои функции-обработчики.

---

## 3. Технологический стек и почему именно он

| Зависимость          | Зачем                                                                |
|----------------------|----------------------------------------------------------------------|
| **Python 3.12+**     | typing-плюшки (`Mapped[]`, `Annotated`), `zoneinfo` в stdlib         |
| **aiogram 3**        | Главный async-фреймворк для ботов. Роутеры, middleware, FSM, фильтры |
| **SQLAlchemy 2 async**| ORM + миграции (если позже), асинхронные движки                     |
| **aiosqlite**        | async-драйвер для SQLite                                             |
| **APScheduler**      | Шедулер задач (cron / интервал / `date`). Поддерживает persistence   |
| **pydantic v2 + pydantic-settings** | Типизированный конфиг, валидация env переменных       |
| **python-dotenv**    | Подхватывает `.env` в окружение                                      |
| **Docker + compose** | Воспроизводимый деплой, изоляция, авто-рестарт                       |

### Что заметно сознательно НЕ используется

- **Redis** — для MVP избыточен; APScheduler хранит jobs в SQLite, FSM в памяти.
- **PostgreSQL** — для одного пользователя SQLite в файле проще, бэкап = `cp file.db file.db.bak`.
- **Celery** — APScheduler покрывает все наши кейсы и работает в том же asyncio-loop.
- **Webhook / FastAPI** — long polling достаточно.

Главный принцип: **минимум зависимостей, максимум стандартной библиотеки**. Чем меньше движущихся частей, тем меньше падает в проде и тем легче новичку понять.

---

## 4. Архитектура проекта по слоям

Я разделил код на четыре чётких слоя. Это **layered / clean architecture lite**: каждый слой зависит только от того, что ниже, и ничего не знает о том, что выше.

```
┌────────────────────────────────────────────────────────────┐
│  bot/         ←  Telegram (handlers, keyboards, FSM)       │
├────────────────────────────────────────────────────────────┤
│  core/services/  ←  бизнес-логика (use cases)              │
├────────────────────────────────────────────────────────────┤
│  core/repositories/  ←  работа с БД (CRUD)                 │
├────────────────────────────────────────────────────────────┤
│  core/models/  +  db/  ←  схема данных и подключение       │
└────────────────────────────────────────────────────────────┘
                ↑
       scheduler/  ←  фоновые задачи, дёргает services
                ↑
       config.py + main.py  ←  всё связывает вместе
```

Зачем такая строгость на маленьком проекте?

- **Тестируемость.** Сервис можно протестировать без Telegram — просто передать сессию БД и вызвать метод.
- **Замена слоёв.** Если завтра ты захочешь сделать web-UI или CLI, добавишь четвёртый слой рядом с `bot/` — `core/services/` останется тем же.
- **Дисциплина при росте.** Когда хендлеров станет 30, без слоёв они превратятся в кашу.

Антипаттерн (так делают в туториалах): «хендлер сразу пишет в БД». Это быстро, но через месяц переписывать.

---

## 5. Слой конфигурации: `config.py` и `.env`

Файл [`config.py`](../config.py):

```python
class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///data/aiquotaflow.db"
    LOG_LEVEL: str = "INFO"
    ADMIN_IDS: list[int] = Field(default_factory=list)

    model_config = SettingsConfigDict(env_file=".env", ...)

settings = Settings()
```

Что здесь происходит:

- `BaseSettings` из `pydantic-settings` берёт значения сначала из **environment variables**, потом из `.env`, потом из дефолтов в классе.
- Поля типизированы — если кто-то впишет `LOG_LEVEL=42`, Pydantic не упадёт, потому что `int` валидно кастуется, **но** мы получим явный класс ошибок при невалидных значениях.
- `BOT_TOKEN: str` без дефолта = обязательное поле. Если его нет — приложение не запустится, и это правильно: лучше упасть на старте, чем мучительно дебажить «почему бот не отвечает».
- `settings = Settings()` создаёт единый объект, который импортируется по всему проекту.

### Формат `.env`

```env
BOT_TOKEN=1234567890:AAA-your-token
DATABASE_URL=sqlite+aiosqlite:///data/aiquotaflow.db
LOG_LEVEL=INFO
```

**Грабли, на которые я уже наступил в этом проекте:**

- Пробелы вокруг `=` ломают парсер: `BOT_TOKEN = "..."` → dotenv не распарсит.
- Кавычки вокруг значения не обязательны и в нашем случае нежелательны.
- `.env` **не должен попасть в git** — он в [`.gitignore`](../.gitignore).
- `.env` **не должен попасть в Docker-образ** — он в [`.dockerignore`](../.dockerignore). Иначе старый `.env` запекается в образ и тенью затирает свежий с хоста.

### Сообщение для самопроверки

Если бот падает с `ValidationError: BOT_TOKEN ... Field required` — почти всегда дело в .env. Проверь:

```bash
cat .env
docker exec aiquotaflow_bot env | grep BOT_TOKEN
```

Второй командой видно, что реально пробросилось в контейнер.

---

## 6. Слой БД: `db/`

Файл [`db/base.py`](../db/base.py):

```python
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
```

Это базовый класс для всех ORM-моделей в SQLAlchemy 2. Все наследники появятся в `Base.metadata` — оттуда `create_all` создаст схему.

Файл [`db/engine.py`](../db/engine.py) делает три вещи:

1. **Гарантирует, что директория для SQLite существует.** Иначе при первой записи получишь `OperationalError: unable to open database file`.

2. **Создаёт async-engine и фабрику сессий:**

   ```python
   engine = create_async_engine(settings.DATABASE_URL, future=True)
   async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
   ```

   `expire_on_commit=False` — важная деталь. По умолчанию после `session.commit()` все объекты «истекают» и при следующем доступе к их полям SQLAlchemy лезет в БД за свежими данными. В async-контексте это происходит **снаружи** open-сессии и роняет приложение с `MissingGreenlet`. С `False` объекты остаются годными.

3. **`init_db()`** — идемпотентное создание таблиц при старте.

   ```python
   async def init_db() -> None:
       from core import models  # импорт моделей, чтобы они попали в metadata
       async with engine.begin() as conn:
           await conn.run_sync(Base.metadata.create_all)
   ```

   Импорт моделей **внутри функции** — не баг, а лекарство от циклических импортов: `db.engine` импортируется моделями, а они — в свою очередь — нужны `init_db`. Ленивый импорт разрывает цикл.

### Когда пора уезжать с SQLite

- Больше 50–100 одновременных пользователей.
- Нужны параллельные writes (SQLite сериализует записи).
- Нужны полноценные миграции с zero-downtime.

Переезд на PostgreSQL = поменять одну строку в `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@db/aiquotaflow
```

Установить `asyncpg`, добавить Alembic для миграций — и всё. Это и есть смысл слоистой архитектуры.

---

## 7. Доменные модели: `core/models/`

[`core/models/user.py`](../core/models/user.py):

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=15)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ...
```

Несколько важных решений:

- **`telegram_id` — отдельное поле**, а не PK. Это позволяет хранить telegram_id как BigInteger (Telegram даёт большие ID), а PK оставить простым int — удобно для foreign keys.
- **`unique=True, index=True`** на `telegram_id`: и валидация на уровне БД, и быстрый поиск.
- **`Mapped[]`** — новая аннотация SQLAlchemy 2.0. Она даёт настоящую типизацию (IDE и mypy видят типы).
- Все datetime — `DateTime(timezone=True)` и хранятся в **UTC**. Переводим в локальный TZ только при отображении (в `notification_service.format_local_time`).

[`core/models/subscription.py`](../core/models/subscription.py) добавляет:

- `SubscriptionAccount` — основная сущность.
- `Purpose` — workspace/цель.
- `SubscriptionPurpose` — join-таблица для **many-to-many** между подписками и целями.

Many-to-many декларируется так:

```python
class SubscriptionAccount(Base):
    purposes: Mapped[list["Purpose"]] = relationship(
        secondary="subscription_purposes",
        back_populates="subscriptions",
        lazy="selectin",
    )

class Purpose(Base):
    subscriptions: Mapped[list["SubscriptionAccount"]] = relationship(
        secondary="subscription_purposes",
        back_populates="purposes",
        lazy="selectin",
    )
```

`lazy="selectin"` означает: когда ты подгружаешь `SubscriptionAccount`, связанные `purposes` подтягиваются одним отдельным запросом `SELECT ... WHERE ID IN (...)`. Без этого они бы лениво грузились при доступе — и в async это снова `MissingGreenlet`.

### Почему `current_status` хранится, а `visual_status` вычисляется

Поле `current_status` принимает значения `available | cooldown | exhausted | inactive` и **хранится в БД** — это «факт», который меняется только по явному действию пользователя или планировщика.

А цвет 🟢/🟡/🔴 — это **производная** от `current_status + cooldown_until + subscription_end_date + now()`. Хранить его в БД бессмысленно: через секунду он может стать другим (cooldown истёк → 🟡 стал 🟢). Поэтому считаем налету в `StatusService.get_visual_status()`. Это пример «вычисляемого vs хранимого состояния».

---

## 8. Репозитории: `core/repositories/`

Репозиторий — это **только про данные**. Он умеет:

- найти,
- создать,
- удалить,
- обновить отдельные поля.

Он **не** знает, что такое cooldown, что значит «доступен» и когда отправлять уведомление.

[`core/repositories/base.py`](../core/repositories/base.py):

```python
class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance
```

`Generic[ModelT]` даёт типизацию: `UserRepository(BaseRepository[User])` — и IDE подсказывает, что `repo.add(...)` возвращает `User`.

`flush()` против `commit()`:
- `flush()` шлёт изменения в БД, но **внутри транзакции**. Объект получает реальный `id`, но если транзакцию откатить — всё пропадёт.
- `commit()` фиксирует транзакцию.

Принцип: **репозиторий делает `flush`, сервис делает `commit`**. Так несколько репозиториев могут участвовать в одной транзакции.

[`core/repositories/subscription_repo.py`](../core/repositories/subscription_repo.py):

```python
async def list_for_owner(self, owner_id: int) -> list[SubscriptionAccount]:
    stmt = (
        select(SubscriptionAccount)
        .where(SubscriptionAccount.owner_id == owner_id)
        .options(selectinload(SubscriptionAccount.purposes))
        .order_by(SubscriptionAccount.created_at.asc())
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())
```

`selectinload` — явная инструкция «подтяни ещё и purposes». В async-контексте всегда указывай eager loading явно — это спасает от загадочных падений.

---

## 9. Сервисы: `core/services/`

Сервис — это **use case**. Один публичный метод сервиса = одно действие пользователя (или системы).

### `StatusService` — чисто-функциональный сервис

[`core/services/status_service.py`](../core/services/status_service.py) не работает с БД вообще. Он берёт `SubscriptionAccount` и текущее время, возвращает цвет:

```python
@classmethod
def get_visual_status(cls, subscription, now=None) -> StatusColor:
    current = now or cls._now()
    if subscription.current_status in ("exhausted", "inactive"):
        return StatusColor.RED
    if subscription.subscription_end_date and \
       subscription.subscription_end_date < current.date():
        return StatusColor.RED
    if subscription.cooldown_until is None:
        return StatusColor.GREEN
    ...
```

Почему это отдельный сервис, а не функция в модели? Чтобы можно было подменить «текущее время» в тестах. Передал `now=datetime(...)`, и тест становится детерминированным.

### `SubscriptionService` — оркестратор

[`core/services/subscription_service.py`](../core/services/subscription_service.py) умеет:

```python
async def set_cooldown(self, subscription, hours=None, minutes=None):
    cooldown_until = now + timedelta(hours=hours, minutes=minutes)
    await self.repo.set_cooldown(subscription, cooldown_until)
    await self.session.commit()
    if self.scheduler is not None:
        await self.scheduler.schedule_cooldown_finished(
            subscription_id=subscription.id, run_date=cooldown_until,
        )
```

Это и есть **бизнес-операция**: одновременно обновляем БД и регистрируем фоновую задачу. Хендлер вызывает один метод сервиса — никогда не дергает шедулер и БД сам.

### Сервисы и сессии

Каждый сервис получает `AsyncSession` в конструкторе. Сессия живёт ровно один update (запрос пользователя). Это делает middleware — см. ниже.

---

## 10. Telegram-слой: aiogram 3

aiogram 3 — это:

- **`Bot`** — клиент к Telegram Bot API. Один объект на всё приложение.
- **`Dispatcher`** — мозг, принимает `Update` и роутит его в нужный обработчик.
- **`Router`** — группа обработчиков по теме (можно сравнить с Flask Blueprint).
- **Хендлеры (`@router.message(...)`, `@router.callback_query(...)`)** — твои функции.
- **Фильтры (`F.data == "..."`)** — условия для роутинга, объявляются декларативно.
- **Middleware** — перехватчики, которые работают вокруг хендлеров (логирование, DI, авторизация).
- **FSM** — конечный автомат для пошаговых диалогов.
- **Storage** — куда сохранять FSM-состояние (`MemoryStorage`, Redis, и т.д.).

Структура минимального обработчика:

```python
router = Router(name="start")

@router.message(CommandStart())
async def cmd_start(message: Message, current_user: User, state: FSMContext):
    await state.clear()
    await message.answer("Привет!", reply_markup=main_menu_keyboard())
```

`current_user` тут приходит из middleware — настоящее волшебство aiogram 3 в том, что **любая зависимость**, которую middleware кладёт в `data` dict, передаётся хендлеру по имени параметра. Это и есть DI без библиотек.

---

## 11. Middleware и Dependency Injection

[`bot/middlewares/di_middleware.py`](../bot/middlewares/di_middleware.py):

```python
class DIMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with self.session_factory() as session:
            data["session"] = session
            data["user_service"] = UserService(session)
            data["subscription_service"] = SubscriptionService(session, scheduler=self.scheduler)
            data["purpose_service"] = PurposeService(session)
            data["notification_service"] = self.notification_service
            data["scheduler"] = self.scheduler
            return await handler(event, data)
```

Это **scoped session**: на каждый update открывается своя сессия, и в её рамках инстанцируются сервисы. После хендлера сессия закрывается. Аналог «request-scoped» в Django/FastAPI.

[`bot/middlewares/user_middleware.py`](../bot/middlewares/user_middleware.py) делает следующий шаг:

```python
class UserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        tg_user = _extract_tg_user(event)
        user_service: UserService = data["user_service"]
        user = await user_service.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        data["current_user"] = user
        return await handler(event, data)
```

Это автоматическая регистрация: первый раз бот видит юзера → создаёт запись, дальше — обновляет имя/username, если поменялись. Хендлерам остаётся просто принять `current_user: User` параметром.

### Порядок имеет значение

В `main.py`:

```python
dp.update.outer_middleware(DIMiddleware(...))
dp.update.outer_middleware(UserMiddleware())
```

`UserMiddleware` идёт **после** `DIMiddleware`, потому что зависит от `user_service`, который кладёт DI.

`outer_middleware` срабатывает на любом апдейте на верхнем уровне диспетчера — это то, что нам нужно, чтобы сессия и юзер были везде.

---

## 12. Клавиатуры

В Telegram два типа клавиатур:

- **ReplyKeyboard** — кнопки внизу экрана, как меню. Возвращают **текст**.
- **InlineKeyboard** — кнопки прямо под сообщением. Возвращают **callback_data** (произвольная строка, до 64 байт).

Мы используем только inline — они удобнее: можно редактировать сообщение, не засоряют чат, имеют callback_data, которую легко парсить.

[`bot/keyboards/subscription.py`](../bot/keyboards/subscription.py):

```python
def cooldown_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hours, label in ((1, "1ч"), (3, "3ч"), (5, "5ч ⭐"), ...):
        builder.button(text=label, callback_data=f"sub:cd:set:{subscription_id}:{hours}")
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()
```

### Соглашение по callback_data

Я использую двоеточие как разделитель: `домен:действие:[параметры]`. Например:

- `menu:main` — открыть главное меню
- `sub:open:42` — открыть подписку #42
- `sub:cd:set:42:5` — поставить cooldown на 5 часов подписке #42

Это позволяет в хендлере фильтровать по префиксу:

```python
@router.callback_query(F.data.startswith("sub:cd:set:"))
async def cooldown_set(callback: CallbackQuery, ...):
    parts = callback.data.split(":")
    sub_id, hours = int(parts[3]), int(parts[4])
    ...
```

Ограничение в 64 байта намекает, что хранить в callback_data большие данные нельзя. Большие — клади в FSM или в БД, в callback_data только ID и команды.

---

## 13. Хендлеры и роутеры

Каждый файл в `bot/handlers/` — это один Router. Они подключаются в `main.py`:

```python
dp.include_router(start_router)
dp.include_router(subscriptions_router)
dp.include_router(status_router)
dp.include_router(settings_router)
dp.include_router(help_router)
```

Порядок имеет значение — Dispatcher проходит роутеры по очереди и берёт первый, чей фильтр совпал.

### Структура хендлера

```python
@router.callback_query(F.data.startswith("sub:open:"))
async def open_subscription(
    callback: CallbackQuery,
    current_user: User,
    subscription_service: SubscriptionService,
    state: FSMContext,
) -> None:
    await state.clear()
    sub_id = int(callback.data.rsplit(":", 1)[-1])
    sub = await subscription_service.get_for_owner(sub_id, current_user.id)
    if sub is None:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return
    if callback.message is not None:
        await _open_subscription_view(callback.message, sub, current_user)
    await callback.answer()
```

Ключевые моменты:

- Параметры функции — **DI**. aiogram сам подставит то, что лежит в `data` под этим именем.
- `callback.answer()` — обязательно вызывать на каждом callback, иначе у пользователя крутится спиннер на кнопке.
- `callback.answer("текст", show_alert=True)` — показать popup с текстом.
- Проверка `if callback.message is not None` — потому что у старых сообщений (>48 часов) `message = None`.
- `get_for_owner(sub_id, current_user.id)` — мы **всегда** проверяем, что запрашиваемая сущность принадлежит текущему пользователю. Это защита от подделки callback_data: иначе кто-то с известным sub_id мог бы изменить чужую подписку.

### Команды vs кнопки

```python
@router.message(Command("status"))    # /status
@router.message(CommandStart())       # /start
@router.callback_query(F.data == "menu:main")    # нажатие inline-кнопки
```

Декоратор + фильтр определяют, какие апдейты попадут в эту функцию.

---

## 14. FSM — конечный автомат для многошаговых диалогов

Когда у тебя «введи имя → выбери план → введи email», нужно где-то хранить промежуточные данные между сообщениями. Это и есть FSM.

[`bot/fsm/add_subscription.py`](../bot/fsm/add_subscription.py):

```python
class AddSubscription(StatesGroup):
    provider = State()
    account_name = State()
    plan = State()
```

Это просто маркеры состояний. Использование:

```python
@router.callback_query(F.data == "sub:add")
async def start_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddSubscription.provider)
    await callback.message.edit_text("Выбери провайдера:", reply_markup=provider_keyboard())

@router.callback_query(AddSubscription.provider, F.data.startswith("add:provider:"))
async def set_provider(callback: CallbackQuery, state: FSMContext):
    provider = callback.data.rsplit(":", 1)[-1]
    await state.update_data(provider=provider)        # сохранили в FSM-data
    await state.set_state(AddSubscription.account_name)
    await callback.message.edit_text("Введи название аккаунта:")

@router.message(AddSubscription.account_name)
async def set_name(message: Message, state: FSMContext):
    await state.update_data(account_name=message.text)
    await state.set_state(AddSubscription.plan)
    ...
```

Фильтр `AddSubscription.provider` означает «эта функция вызовется, только если текущее состояние юзера = provider». Так одно и то же нажатие кнопки в разных контекстах роутится в разные функции.

В конце:

```python
data = await state.get_data()    # {"provider": "Claude", "account_name": "...", ...}
await subscription_service.create(**data)
await state.clear()
```

### Где хранится FSM

В нашем `main.py`:

```python
dp = Dispatcher(storage=MemoryStorage())
```

`MemoryStorage` хранит состояния в RAM. При рестарте бота они теряются. Для MVP это ок: пользователь не успеет «зависнуть» в середине диалога между рестартами. Если беспокоит — есть `RedisStorage` или `MongoStorage`.

---

## 15. Планировщик: APScheduler с persistent jobstore

Когда пользователь нажимает «cooldown 5 часов», нам нужно через 5 часов послать ему сообщение. Это работа для **scheduler'а**.

[`scheduler/setup.py`](../scheduler/setup.py):

```python
def create_scheduler(sync_database_url: str) -> AsyncIOScheduler:
    return AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=sync_database_url)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        timezone="UTC",
    )
```

Разберём аргументы:

- **`AsyncIOScheduler`** — крутится в том же asyncio-loop, что и бот. Не нужен отдельный поток.
- **`SQLAlchemyJobStore`** — сохраняет задачи в БД. **Без этого после рестарта Docker все таймеры теряются**, и пользователи не получат уведомление о сбросе cooldown. Это ключевое требование MVP.
- **Sync URL для jobstore** — APScheduler использует синхронную SQLAlchemy. Поэтому в `config.py` есть property `sync_database_url`, которая делает `sqlite+aiosqlite://` → `sqlite://`.
- **`coalesce=True`** — если бот был выключен и пропустил несколько срабатываний одной задачи, выполнить её один раз, а не серию.
- **`max_instances=1`** — не запускать параллельно копии одной задачи.
- **`misfire_grace_time=3600`** — если задача опоздала меньше чем на час, всё равно выполнить.

### Задача = функция верхнего уровня

[`scheduler/jobs.py`](../scheduler/jobs.py):

```python
async def cooldown_finished_job(subscription_id: int) -> None:
    runtime = _get_runtime()
    bot = runtime.bot
    session_factory = runtime.session_factory

    async with session_factory() as session:
        subscription = await session.get(SubscriptionAccount, subscription_id)
        if subscription is None:
            return
        subscription.current_status = "available"
        subscription.cooldown_until = None
        await session.commit()

        user = await UserRepository(session).get_by_id(subscription.owner_id)
        if user is None:
            return
        await NotificationService(bot).notify_cooldown_finished(user, subscription)
```

Важный нюанс: **в jobstore сохраняются функция и её аргументы — не объекты**. Поэтому в args мы передаём только `subscription_id` (число), а внутри задачи лезем в БД свежей сессией. Если бы мы передали сам объект `Bot` — APScheduler не смог бы его сериализовать.

### Runtime singleton

[`scheduler/runtime.py`](../scheduler/runtime.py):

```python
_runtime: Runtime | None = None

def set_runtime(bot, session_factory):
    global _runtime
    _runtime = Runtime(bot=bot, session_factory=session_factory)
```

После рестарта APScheduler восстанавливает задачи из БД и хочет их выполнить. Им нужны `bot` и `session_factory`, но они не сохранены — это singletons процесса. Поэтому в `main.py` мы сначала зовём `set_runtime(...)`, а задачи через `get_runtime()` берут текущий живой экземпляр.

Это паттерн **«service locator»** — иногда его ругают, но для шедулера это самый чистый способ дать задачам доступ к внешним ресурсам без сериализации.

### Регистрация задачи

```python
self.scheduler.add_job(
    cooldown_finished_job,
    trigger="date",
    run_date=cooldown_until,
    args=[subscription_id],
    id=cooldown_job_id(subscription_id),       # детерминированный id
    replace_existing=True,                     # перезаписывает старую задачу
)
```

`replace_existing=True` критично. Если пользователь поставил cooldown на 5 часов, а через час — заново на 3 часа, мы хотим **переписать** старую задачу, а не добавить вторую.

`id=f"cooldown_{subscription_id}"` — детерминированный ID. Когда пользователь удалит подписку, мы зовём `scheduler.remove_job("cooldown_42")` и не паримся, как его найти.

---

## 16. Сборка приложения: `main.py`

Точка сборки — самый важный файл, чтобы понять как «всё связано».

[`main.py`](../main.py):

```python
async def main():
    setup_logging(settings.LOG_LEVEL)
    await init_db()                                          # 1

    bot = Bot(token=settings.BOT_TOKEN, default=...)         # 2
    set_runtime(bot=bot, session_factory=async_session_factory)  # 3

    apscheduler = create_scheduler(settings.sync_database_url)
    scheduler = SchedulerWrapper(apscheduler)                # 4
    scheduler.bind(bot=bot, session_factory=async_session_factory)

    notification_service = NotificationService(bot)

    dp = Dispatcher(storage=MemoryStorage())                 # 5
    dp.update.outer_middleware(DIMiddleware(...))            # 6
    dp.update.outer_middleware(UserMiddleware())

    dp.include_router(start_router)                          # 7
    dp.include_router(subscriptions_router)
    ...

    scheduler.start()                                        # 8
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)                          # 9
    finally:
        scheduler.shutdown()                                 # 10
        await bot.session.close()
```

Порядок:

1. Создаём схему БД.
2. Создаём бота с токеном и HTML-парсингом по умолчанию.
3. Регистрируем bot и session_factory в runtime singleton, чтобы шедулер-задачи могли их найти.
4. Создаём шедулер, оборачиваем в `SchedulerWrapper` (наш фасад).
5. Создаём диспетчер с in-memory хранилищем для FSM.
6. Подключаем middleware (порядок важен).
7. Подключаем роутеры.
8. Запускаем шедулер.
9. `delete_webhook(drop_pending_updates=True)` — на случай если webhook был включён раньше; ещё это сбрасывает накопленную очередь апдейтов. Дальше — long polling.
10. На `Ctrl+C` или сигнал контейнеру: остановить шедулер, закрыть HTTP-сессию бота. **Graceful shutdown** — даёт текущим хендлерам дописать в БД.

---

## 17. Деплой через Docker

[`Dockerfile`](../Dockerfile):

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ...

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/data

CMD ["python", "-u", "main.py"]
```

Микро-комментарии:

- **`python:3.12-slim`** — без лишних 200 МБ debian-полной поставки. Достаточно для нашего кейса.
- **`PYTHONUNBUFFERED=1`** — без буферизации stdout, чтобы `docker logs` показывал свежие строки сразу.
- **`tzdata`** — иначе `ZoneInfo("Europe/Moscow")` упадёт, потому что в slim-образе нет базы таймзон.
- **Отдельный `COPY requirements.txt` + `pip install` ДО `COPY . .`** — это **layer caching**. Зависимости пересобираются только если поменялся requirements.txt, а не при каждом изменении кода. Существенно ускоряет пересборку.
- **`-u` в CMD** — то же самое, что `PYTHONUNBUFFERED=1`, дополнительная страховка.

[`docker-compose.yml`](../docker-compose.yml):

```yaml
services:
  bot:
    build: .
    container_name: aiquotaflow_bot
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/aiquotaflow.db
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

- **`restart: unless-stopped`** — упал? перезапускаем. Сам остановил? не трогаем.
- **`env_file: .env`** — compose читает .env с хоста и инжектит переменные **в окружение контейнера**.
- **`volumes: - ./data:/app/data`** — bind mount. SQLite-файл живёт на хосте, переживает `docker-compose down/up --build`. Бэкап = `cp -r data data.bak`.
- **`logging`** — иначе docker может разрастить логи до десятков ГБ за месяцы. С таким конфигом — максимум 30 МБ суммарно.

[`.dockerignore`](../.dockerignore) — список того, что **не** надо копировать в образ при `COPY . .`. Главное — `.env` и `data/`. Иначе старый .env запекался бы в образ и затирал свежий с хоста (а data/ раздувал бы образ).

### Базовые команды деплоя

```bash
docker-compose up -d --build          # собрать и запустить в фоне
docker-compose logs -f bot            # стрим логов
docker-compose restart bot            # рестарт без пересборки
docker-compose down                   # остановить и снести контейнеры
docker-compose pull && docker-compose up -d --build    # при apt-обновлениях
```

---

## 18. Типичные ошибки и как их ловил я

### `MissingGreenlet: greenlet_spawn has not been called`

Случается, когда ты в async-сессии триггеришь **ленивую загрузку relationship** или **доступ к expired атрибуту**. Решения:

1. `expire_on_commit=False` в session-factory.
2. `lazy="selectin"` на relationship.
3. Перед `subscription.purposes = new_list` сделать `await session.refresh(subscription, attribute_names=["purposes"])`.

Конкретно с этим я столкнулся при первом запуске replace_purposes — пришлось добавить refresh перед перезаписью коллекции.

### `ValidationError: BOT_TOKEN ... Field required`

Pydantic не нашёл BOT_TOKEN. Причины:

- .env не в правильном формате (пробелы вокруг `=`, кавычки).
- .env лежит не там, где его ищет `pydantic-settings` (рабочая директория != директория с .env).
- В Docker — .env запечён в образ через `COPY` и затирает свежий.

Самопроверка:

```bash
docker exec aiquotaflow_bot env | grep BOT_TOKEN
docker exec aiquotaflow_bot cat /app/.env 2>/dev/null
```

### `TelegramBadRequest: message is not modified`

Случается, когда ты пытаешься `edit_text` на сообщение, текст которого уже такой же. Простое решение — оборачивать в try/except `TelegramBadRequest`, или менять хотя бы один символ (например, добавлять «обновлено в HH:MM»).

### `TelegramRetryAfter` (флуд-контроль)

Telegram имеет лимиты (~30 сообщений в секунду глобально, 1 в секунду в один чат). Когда ловишь — нужно делать `await asyncio.sleep(exc.retry_after)`. aiogram частично умеет это сам через middleware `flood_control`, но в нашем масштабе это не проблема.

### Бот «работает», но не отвечает

В 99% случаев — запущено два экземпляра одновременно. Telegram дисциплинирует и отдаёт апдейты только одному за раз. Случайно поднял бота локально, потом ещё в Docker — оба будут «работать», но юзер ничего не увидит.

Решение: один процесс = один бот.

### `docker-compose` v1 кидает Exception про `watch_events`

Это известный баг docker-compose v1 c Docker 29. На работу контейнера не влияет — это падает потоковый просмотр событий в самом compose, не бот. Можно мигрировать на `docker compose` v2 (плагин), или просто использовать `docker logs -f <name>` вместо `docker-compose logs -f`.

---

## 19. Как развивать проект дальше

В порядке «от простого к более продвинутому»:

1. **Тесты.** Начни с unit-тестов на `StatusService` (он чистый). Дальше — интеграционные на сервисы с in-memory SQLite. Поверх — e2e через [`aiogram-tests`](https://github.com/OCSimonm/aiogram-tests).

2. **Миграции через Alembic.** Сейчас `Base.metadata.create_all` делает только initial-схему. Для эволюции БД нужны миграции:

   ```bash
   alembic init alembic
   alembic revision --autogenerate -m "add field X"
   alembic upgrade head
   ```

3. **Логи и мониторинг.** Сейчас всё пишется в stdout. Для прода добавь structlog для JSON-логов и Sentry для алертов на исключения.

4. **PostgreSQL.** Меняешь `DATABASE_URL`, ставишь `asyncpg`, поднимаешь postgres в compose рядом. Бизнес-код не меняется.

5. **Web-дашборд.** FastAPI + те же сервисы. Бот и сайт делят `core/`.

6. **CI/CD.** GitHub Actions: lint (ruff) + tests + build docker → push в registry → deploy на VPS через ssh.

7. **Webhook вместо polling.** Поставь Caddy/Nginx с auto-TLS, прокинь POST `/webhook/<secret>` в бота. Меньше задержка, больше throughput.

8. **i18n.** aiogram-i18n или fluent для русский/english интерфейса.

9. **Шаринг подписок.** Тогда нужна вторая many-to-many через `subscription_members`. Архитектура к этому готова — поле `owner_id` заменится на полноценную membership-таблицу.

---

## 20. Дополнительная литература

### По Telegram-ботам и aiogram

- [Telegram Bot API — официальная документация](https://core.telegram.org/bots/api). Истина в последней инстанции. Любая Python-обёртка — это только маппинг сюда.
- [aiogram 3 docs](https://docs.aiogram.dev/en/latest/). Особенно разделы Dispatcher, Routers, Middlewares, FSM.
- [Mastering aiogram 3 — Groosha](https://mastering-aiogram-3.readthedocs.io/). Самая внятная книга на русском, ведут пошагово.
- [Awesome aiogram](https://github.com/aiogram/awesome-aiogram). Шаблоны, примеры, плагины.

### По асинхронному Python

- [PEP 492 — Coroutines with async and await](https://peps.python.org/pep-0492/). Скучно, но даёт понимание основ.
- [Real Python — Async IO in Python: A Complete Walkthrough](https://realpython.com/async-io-python/). Лучшее объяснение event loop с картинками.
- [Trio — concurrency for humans](https://trio.readthedocs.io/). Не для прода нашего бота, но архитектурно крайне поучительно — после Trio лучше понимаешь, что не так с asyncio.

### По SQLAlchemy

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/). Огромная, но раздел [«Async ORM»](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) маленький и ключевой.
- [Mike Bayer — SQLAlchemy: The Most Powerful Python ORM (talks)](https://www.youtube.com/results?search_query=mike+bayer+sqlalchemy). Автор объясняет дизайн решения, понимаешь почему ORM работает так, а не иначе.
- [Alembic Documentation](https://alembic.sqlalchemy.org/). Когда дойдёшь до миграций.

### По архитектуре приложений

- **«Architecture Patterns with Python» — Harry Percival, Bob Gregory.** Бесплатная онлайн. Repository, Service Layer, Unit of Work — на примере Python. Маст-рид после того как ты сам что-то собрал и почувствовал, что «каша».
- **«Domain-Driven Design Distilled» — Vaughn Vernon.** Тонкая книга, объясняет ключевые DDD-идеи без воды.
- **Clean Architecture — Robert Martin.** Старый принцип «дёргаешь UI/БД/фреймворк — бизнес-логика стоит на месте». В нашем проекте именно это — `core/` независимо от `bot/`.

### По Docker и деплою

- [Docker Curriculum](https://docker-curriculum.com/). Лучший практический туториал.
- [12 Factor App](https://12factor.net/). Маленький, но фундаментальный текст. Всё, что мы делаем с .env и логами — оттуда.
- [Awesome Compose](https://github.com/docker/awesome-compose). Готовые compose-файлы для разных стэков, копируй и адаптируй.

### По APScheduler и фоновым задачам

- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html). Краткая, всё по делу.
- Когда APScheduler станет тесно — посмотри **Celery** или **arq**. Целевая аудитория: распределённые workers, retry-политики, очереди.

### По разработке в целом

- **«The Pragmatic Programmer» — David Thomas, Andrew Hunt.** Класcика. Многие практики, которые я применял в этом проекте (DRY, ортогональность, явное лучше неявного), описаны там в проблема→решение виде.
- **«Refactoring» — Martin Fowler.** Когда захочется почистить уже написанное. Учит видеть «code smells» и применять механические преобразования.
- **Talks с PyCon / EuroPython.** Бесплатно на YouTube. Лучший способ узнать, как пишут production-код в больших компаниях.

### Если интересно «как этот код можно было бы написать ещё лучше»

- [FastStream](https://faststream.airt.ai/) или [aio-pika](https://aio-pika.readthedocs.io/) — для очередей сообщений между ботом и worker'ами.
- [dishka](https://github.com/reagento/dishka) или [punq](https://github.com/bobthemighty/punq) — настоящий DI-контейнер вместо «middleware кладёт в data». Полезно при росте проекта.
- [Pydantic AI](https://ai.pydantic.dev/) — если захочешь добавить LLM-агента в этого же бота.

---

## Финальный совет

Не пытайся понять всё сразу. Возьми один слой — например, `core/services/status_service.py` — и **полностью** разберись, что он делает и почему так. Дальше переходи к следующему.

Перепиши какой-нибудь сервис своими словами — без подглядывания. Получится — значит понял. Не получится — это и есть карта того, что нужно изучить.

Удачи. Если что — issue в репе.
