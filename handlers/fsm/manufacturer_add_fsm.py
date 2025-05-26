# your_bot/handlers/fsm/manufacturer_add_fsm.py
# FSM диалог для добавления нового производителя

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK

# --- FSM States ---
class ManufacturerAddFSM(StatesGroup):
    """Состояния для диалога добавления производителя."""
    waiting_for_name = State()
    confirm_add = State()

# --- Handlers ---
async def start_manufacturer_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог добавления производителя."""
    await callback_query.answer()
    # Сбрасываем FSM перед началом нового диалога
    await state.clear()
    await state.set_state(ManufacturerAddFSM.waiting_for_name)
    await callback_query.message.edit_text( # Редактируем сообщение, откуда пришел колбэк
        "📝 **Добавление Производителя**\n\n"
        "Введите название нового производителя или нажмите ' Отмена'."
    )

async def process_manufacturer_name(message: types.Message, state: FSMContext):
    """Обрабатывает введенное название производителя."""
    manufacturer_name = message.text.strip()
    if not manufacturer_name:
        await message.answer("Название производителя не может быть пустым. Введите название или 'Отмена'.")
        return

    await state.update_data(name=manufacturer_name)

    # Переходим к подтверждению
    await show_manufacturer_confirm_add(message, state) # Отправляем новое сообщение


async def show_manufacturer_confirm_add(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения добавления производителя (ADD FSM)."""
    user_data = await state.get_data()
    name = user_data.get("name")

    text = (
        "✨ **Подтверждение добавления Производителя** ✨\n\n"
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
    await state.set_state(ManufacturerAddFSM.confirm_add)


async def process_manufacturer_confirm_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение добавления производителя (ADD FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    name = user_data.get("name")

    # Вызываем функцию добавления из utils/db.py
    new_manufacturer = db.add_manufacturer(name=name)

    if new_manufacturer:
        await callback_query.message.edit_text(
            "🎉 **Производитель успешно добавлен!** 🎉\n"
            f"**ID:** `{new_manufacturer.id}`\n"
            f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(new_manufacturer.name)}`"
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Ошибка при добавлении производителя.**\n"
            "Возможно, производитель с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# --- Router Registration ---
def register_manufacturer_add_handlers(router: Router):
    # ENTRY POINT
    router.callback_query.register(start_manufacturer_add, F.data == "manufacturer_add_action") # Начало FSM

    # Handlers
    router.message.register(process_manufacturer_name, ManufacturerAddFSM.waiting_for_name)
    router.callback_query.register(process_manufacturer_confirm_add, ManufacturerAddFSM.confirm_add, F.data == CONFIRM_ACTION_CALLBACK)

    # Общий хэндлер отмены регистрируется отдельно
