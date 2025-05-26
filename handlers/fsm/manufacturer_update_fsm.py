# your_bot/handlers/fsm/manufacturer_update_fsm.py
# FSM диалог для обновления существующего производителя

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Union

# Импорт функций работы с БД
# Используем относительный импорт
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK, SKIP_INPUT_MARKER
# Импорт админских констант
from ..admin_constants_aiogram import MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX

# Импорт хелпера для отправки/редактирования сообщений из admin_list_detail_handlers_aiogram
# Импортируем здесь, чтобы избежать циклического импорта на уровне модуля
from ..admin_list_detail_handlers_aiogram import _send_or_edit_message

# Настройка логирования
logger = logging.getLogger(__name__)


# --- FSM States ---
class ManufacturerUpdateFSM(StatesGroup):
    """Состояния для диалога обновления производителя."""
    waiting_for_name = State()
    # Note: Ignoring 'contact_info' as per provided DB schema
    confirm_update = State()

# --- Handlers ---
async def start_manufacturer_update(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог обновления производителя."""
    await callback_query.answer()

    # Парсим ID производителя из callback_data
    try:
        # Ожидается формат callback_data: {префикс_инициации_обновления}{id}
        manufacturer_id_str = callback_query.data.replace(MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX, "")
        manufacturer_id = int(manufacturer_id_str)
    except ValueError:
        logger.error(f"Некорректный ID производителя в колбэке обновления: {callback_query.data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Некорректный ID производителя для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Получаем текущие данные производителя из БД
    manufacturer = db.get_manufacturer_by_id(manufacturer_id)
    if not manufacturer:
        logger.error(f"Производитель с ID {manufacturer_id} не найден для обновления.")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Производитель не найден для обновления.")
        await state.clear()
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Сбрасываем FSM перед началом нового диалога (если не был сброшен ранее)
    await state.clear() # Сброс в начале FSM диалога обновления


    # Сохраняем текущие данные и ID в контексте FSM
    await state.update_data(
        updating_manufacturer_id=manufacturer.id,
        original_name=manufacturer.name
    )

    # Переходим к первому шагу: запрос нового названия
    await state.set_state(ManufacturerUpdateFSM.waiting_for_name)
    # Редактируем сообщение, откуда пришел колбэк (детали)
    # Экранируем текущее название для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(manufacturer.name)

    await _send_or_edit_message(
        callback_query,
        f"📝 **Обновление Производителя** (ID: `{manufacturer.id}`)\n\n"
        f"Текущее название: `{original_name_esc}`\n\n"
        f"Введите новое название производителя или пропустите, отправив `{SKIP_INPUT_MARKER}`.",
        parse_mode="MarkdownV2"
    )

async def process_manufacturer_name_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое название производителя (UPDATE FSM)."""
    user_data = await state.get_data()
    original_name = user_data.get("original_name")
    new_name = message.text.strip()

    if new_name == SKIP_INPUT_MARKER:
        new_name = original_name # Пропускаем - оставляем старое значение
        # Экранируем оригинальное название для MarkdownV2
        original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
        await message.answer(f"Название оставлено без изменений: `{original_name_esc}`.", parse_mode="MarkdownV2")
    elif not new_name:
         await message.answer("Название производителя не может быть пустым. Введите новое название, отправьте `-` для пропуска или 'Отмена'.")
         # Остаемся в текущем состоянии
         return
    else:
        # Экранируем новое название для MarkdownV2
        new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
        await message.answer(f"Новое название: `{new_name_esc}`", parse_mode="MarkdownV2")


    # Сохраняем новое название (или старое, если пропущено)
    await state.update_data(new_name=new_name)

    # Переходим к подтверждению
    await show_manufacturer_update_confirm(message, state) # Отправляем новое сообщение с подтверждением


async def show_manufacturer_update_confirm(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения обновления производителя (UPDATE FSM)."""
    user_data = await state.get_data()
    manufacturer_id = user_data.get("updating_manufacturer_id")
    original_name = user_data.get("original_name")
    new_name = user_data.get("new_name") # Получено из FSM state

    text = f"✨ **Подтверждение обновления Производителя** (ID: `{manufacturer_id}`) ✨\n\n"

    # Показываем изменения, экранируя для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
    new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
    if new_name != original_name:
        text += f"**Название:** ~~`{original_name_esc}`~~ → `{new_name_esc}`\n"
    else:
        text += f"**Название:** `{original_name_esc}` (без изменений)\n"

    text += "\nВсе верно? Подтвердите или отмените."

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить обновление", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Используем target.answer, т.к. предыдущий шаг был message.register
    await target.answer(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    await state.set_state(ManufacturerUpdateFSM.confirm_update)


async def process_manufacturer_update_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение обновления производителя (UPDATE FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    manufacturer_id = user_data.get("updating_manufacturer_id")
    new_name = user_data.get("new_name") # Получено из FSM state

    # Формируем словарь с данными для обновления
    update_data = {"name": new_name}

    # Вызываем функцию обновления из utils/db.py
    updated_manufacturer = db.update_manufacturer(manufacturer_id, update_data)

    if updated_manufacturer:
        # Экранируем новое название для MarkdownV2
        updated_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_manufacturer.name)
        await callback_query.message.edit_text(
            f"🎉 **Производитель (ID: `{manufacturer_id}`) успешно обновлен!** 🎉"
            f"\nНовое название: `{updated_name_esc}`",
            parse_mode="MarkdownV2"
        )
    else:
        # TODO: Добавить более конкретную ошибку из db.update_manufacturer, если возможно (IntegrityError)
        await callback_query.message.edit_text(
            f"❌ **Ошибка при обновлении производителя (ID: `{manufacturer_id}`).**\n"
            "Возможно, производитель с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# Примечание: Отдельный хэндлер cancel_update_manufacturer не нужен,
# если используется общий cancel_fsm_handler, зарегистрированный на State("*")


# --- Router Registration ---
# Создаем роутер специально для FSM обновления производителя
manufacturer_update_fsm_router = Router(name="manufacturer_update_fsm_router")

def register_manufacturer_update_handlers(router: Router):
    """Регистрирует обработчики FSM обновления производителя."""

    # ENTRY POINT: Запуск FSM по колбэку "Редактировать" из детального просмотра производителя
    # Используем F.data.startswith для фильтрации по префиксу инициации обновления производителя
    router.callback_query.register(
        start_manufacturer_update,
        F.data.startswith(MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX)
        # Без фильтра состояний, т.к. это вход в FSM
    )

    # Обработчик ввода названия (ожидает текстовый ввод с определенным состоянием)
    router.message.register(process_manufacturer_name_update, ManufacturerUpdateFSM.waiting_for_name)

    # Хэндлер подтверждения (ожидает колбэк с определенным состоянием и колбэком подтверждения)
    router.callback_query.register(
        process_manufacturer_update_confirm,
        ManufacturerUpdateFSM.confirm_update,
        F.data == CONFIRM_ACTION_CALLBACK
    )

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера
    # Например, на родительском admin_router или главном dp с фильтром State("*") и Text(CANCEL_FSM_CALLBACK).
    # router.callback_query.register(cancel_fsm_handler, Text(CANCEL_FSM_CALLBACK), State("*"))

# Вызываем функцию регистрации для этого роутера
register_manufacturer_update_handlers(manufacturer_update_fsm_router)

# Роутер manufacturer_update_fsm_router теперь содержит все обработчики и готов к включению в основной диспатчер/роутер.
