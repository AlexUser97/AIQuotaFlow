# AIQuotaFlow

Личный планировщик AI-аккаунтов в виде Telegram-бота.
Ты вручную отмечаешь «упёрся в лимит на этом аккаунте» — бот считает время cooldown и присылает уведомление, когда квота восстановилась.

Бот **не** логинится в твои аккаунты, не хранит пароли/токены/cookies и не проверяет лимиты автоматически. Это ручной трекер.

---

## Возможности

- Список аккаунтов с цветными статусами 🟢 / 🟡 / 🔴.
- Cooldown быстрыми кнопками `1ч / 3ч / 5ч⭐ / 6ч / 12ч / 24ч` или произвольно (`2ч 30м`, `90` мин).
- Уведомление при сбросе cooldown — статус автоматически становится 🟢.
- Workspaces (цели): один аккаунт может относиться к нескольким, на экране «Статусы» доступен фильтр.
- Настройки: таймзона IANA, напоминание за N минут, формат времени 12/24ч, сортировка.
- APScheduler сохраняет таймеры в SQLite — переживают рестарт контейнера.
- Multi-user из коробки: каждый видит только свои данные.

---

## Стек

`Python 3.12 · aiogram 3 · SQLAlchemy async · aiosqlite · APScheduler · pydantic-settings · Docker`

---

## Быстрый запуск через Docker

1. Создай Telegram-бота через [@BotFather](https://t.me/BotFather), скопируй токен.
2. Склонируй репозиторий и перейди в директорию:

   ```bash
   git clone git@github.com:AlexUser97/AIQuotaFlow.git
   cd AIQuotaFlow
   ```

3. Создай `.env` на основе шаблона:

   ```bash
   cp .env.example .env
   ```

   И пропиши свой токен. **Важно:** без пробелов вокруг `=` и без кавычек:

   ```env
   BOT_TOKEN=1234567890:AAA-your-token-here
   DATABASE_URL=sqlite+aiosqlite:///data/aiquotaflow.db
   LOG_LEVEL=INFO
   ```

4. Собери и запусти:

   ```bash
   docker-compose up -d --build
   ```

5. Проверь, что polling пошёл:

   ```bash
   docker logs -f aiquotaflow_bot
   ```

   Должна появиться строка вида `Run polling for bot @your_bot_name`.

6. Открой бота в Telegram и напиши `/start`.

### Управление

```bash
docker-compose ps                    # статус
docker logs -f aiquotaflow_bot       # стрим логов
docker-compose restart               # рестарт
docker-compose down                  # остановить и удалить контейнер
docker-compose up -d --build         # пересобрать и поднять
```

База лежит в `./data/aiquotaflow.db` — этот каталог монтируется в контейнер, переживает пересборку, бэкап = копия файла.

---

## Локальный запуск без Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # положи туда свой BOT_TOKEN

python main.py
```

---

## Команды бота

| Команда     | Действие                          |
|-------------|-----------------------------------|
| `/start`    | главное меню                       |
| `/add`      | добавить аккаунт                   |
| `/status`   | быстрый дашборд по всем подпискам  |
| `/settings` | настройки                          |
| `/help`     | справка                            |

---

## Структура проекта

```
aiquotaflow/
├── bot/           # aiogram-слой: handlers, FSM, keyboards, middlewares
├── core/          # доменный слой: models, repositories, services
├── db/            # SQLAlchemy async engine + declarative base
├── scheduler/     # APScheduler + persistent jobstore
├── config.py      # Pydantic Settings (читает .env)
├── main.py        # точка входа: сборка бота, диспетчера, шедулера
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

Подробное описание каждого слоя и пояснение почему сделано именно так — в [`docs/DEVELOPER.md`](docs/DEVELOPER.md).

---

## Лицензия

MIT (если не указано иное).
