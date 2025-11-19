from aiogram import Router
from .start_handler import router as start_router

router = Router(name=__name__)

router.include_routers(
    start_router
)