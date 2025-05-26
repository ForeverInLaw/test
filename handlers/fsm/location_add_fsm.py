# your_bot/handlers/fsm/location_add_fsm.py
# FSM диалог для добавления нового местоположения

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK

# --- FSM States ---
class LocationAddFSM(StatesGroup):
    """Состояния для диалога добавления местоположения."""
    waiting_for_name = State()
    confirm_add = State()

# --- Handlers ---
async def start_location_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог добавления местоположения."""
    await callback_query.answer()
    # Сбрасываем FSM перед началом нового диалога
    await state.clear()
    await state.set_state(LocationAddFSM.waiting_for_name)
    await callback_query.message.edit_text( # Редактируем сообщение, откуда пришел колбэк
        "📝 **Добавление Местоположения**\n\n"
        "Введите название нового местоположения или нажмите 'Отмена'."
    )

async def process_location_name(message: types.Message, state: FSMContext):
    """Обрабатывает введенное название местоположения."""
    location_name = message.text.strip()
    if not location_name:
        await message.answer("Название местоположения не может быть пустым. Введите название или 'Отмена'.")
        return

    await state.update_data(name=location_name)

    # Переходим к подтверждению
    await show_location_confirm_add(message, state) # Отправляем новое сообщение


async def show_location_confirm_add(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения добавления местоположения (ADD FSM)."""
    user_data = await state.get_data()
    name = user_data.get("name")

    text = (
        "✨ **Подтверждение добавления Местоположения** ✨\n\n"
        f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(name)}`\n\n"
        "Все верно? Подтвердите или отмените."
    )

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Используем target.answer, т.к. предыдущий шаг был message.register
    await target.answer(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    await state.set_state(LocationAddFSM.confirm_add)


async def process_location_confirm_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение добавления местоположения (ADD FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    name = user_data.get("name")

    # Вызываем функцию добавления из utils/db.py
    new_location = db.add_location(name=name)

    if new_location:
        await callback_query.message.edit_text(
            "🎉 **Местоположение успешно добавлено!** 🎉\n"
            f"**ID:** `{new_location.id}`\n"
            f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(new_location.name)}`"
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Ошибка при добавлении местоположения.**\n"
            "Возможно, местоположение с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# --- Router Registration ---
def register_location_add_handlers(router: Router):
    # ENTRY POINT
    router.callback_query.register(start_location_add, F.data == "location_add_action") # Начало FSM

    # Handlers
    router.message.register(process_location_name, LocationAddFSM.waiting_for_name)
    router.callback_query.register(process_location_confirm_add, LocationAddFSM.confirm_add, F.data == CONFIRM_ACTION_CALLBACK)

    # Общий хэндлер отмены регистрируется отдельно
