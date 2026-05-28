from bot.handlers.help import router as help_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.status import router as status_router
from bot.handlers.subscriptions import router as subscriptions_router

__all__ = [
    "start_router",
    "subscriptions_router",
    "status_router",
    "settings_router",
    "help_router",
]
