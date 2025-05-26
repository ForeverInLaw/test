# your_bot/handlers/fsm/location_update_fsm.py
# FSM диалог для обновления существующего местоположения

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
from ..admin_constants_aiogram import LOCATION_UPDATE_INIT_CALLBACK_PREFIX

# Импорт хелпера для отправки/редактирования сообщений из admin_list_detail_handlers_aiogram
# Импортируем здесь, чтобы избежать циклического импорта на уровне модуля
from ..admin_list_detail_handlers_aiogram import _send_or_edit_message


# Настройка логирования
logger = logging.getLogger(__name__)


# --- FSM States ---
class LocationUpdateFSM(StatesGroup):
    """Состояния для диалога обновления местоположения."""
    waiting_for_name = State()
    # Note: Ignoring 'address' as per provided DB schema
    confirm_update = State()

# --- Handlers ---
async def start_location_update(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог обновления местоположения."""
    await callback_query.answer()

    # Парсим ID местоположения из callback_data
    try:
        # Ожидается формат callback_data: {префикс_инициации_обновления}{id}
        location_id_str = callback_query.data.replace(LOCATION_UPDATE_INIT_CALLBACK_PREFIX, "")
        location_id = int(location_id_str)
    except ValueError:
        logger.error(f"Некорректный ID местоположения в колбэке обновления: {callback_query.data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Некорректный ID местоположения для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Получаем текущие данные местоположения из БД
    location = db.get_location_by_id(location_id)
    if not location:
        logger.error(f"Местоположение с ID {location_id} не найдено для обновления.")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Местоположение не найдено для обновления.")
        await state.clear()
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Сбрасываем FSM перед началом нового диалога (если не был сброшен ранее)
    await state.clear() # Сброс в начале FSM диалога обновления


    # Сохраняем текущие данные и ID в контексте FSM
    await state.update_data(
        updating_location_id=location.id,
        original_name=location.name
    )

    # Переходим к первому шагу: запрос нового названия
    await state.set_state(LocationUpdateFSM.waiting_for_name)
    # Редактируем сообщение, откуда пришел колбэк (детали)
    # Экранируем текущее название для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(location.name)

    await _send_or_edit_message(
        callback_query,
        f"📝 **Обновление Местоположения** (ID: `{location.id}`)\n\n"
        f"Текущее название: `{original_name_esc}`\n\n"
        f"Введите новое название местоположения или пропустите, отправив `{SKIP_INPUT_MARKER}`.",
        parse_mode="MarkdownV2"
    )

async def process_location_name_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое название местоположения (UPDATE FSM)."""
    user_data = await state.get_data()
    original_name = user_data.get("original_name")
    new_name = message.text.strip()

    if new_name == SKIP_INPUT_MARKER:
        new_name = original_name # Пропускаем - оставляем старое значение
        # Экранируем оригинальное название для MarkdownV2
        original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
        await message.answer(f"Название оставлено без изменений: `{original_name_esc}`.", parse_mode="MarkdownV2")
    elif not new_name:
         await message.answer("Название местоположения не может быть пустым. Введите новое название, отправьте `-` для пропуска или 'Отмена'.")
         # Остаемся в текущем состоянии
         return
    else:
        # Экранируем новое название для MarkdownV2
        new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
        await message.answer(f"Новое название: `{new_name_esc}`", parse_mode="MarkdownV2")

    # Сохраняем новое название (или старое, если пропущено)
    await state.update_data(new_name=new_name)

    # Переходим к подтверждению
    await show_location_update_confirm(message, state) # Отправляем новое сообщение с подтверждением


async def show_location_update_confirm(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения обновления местоположения (UPDATE FSM)."""
    user_data = await state.get_data()
    location_id = user_data.get("updating_location_id")
    original_name = user_data.get("original_name")
    new_name = user_data.get("new_name") # Получено из FSM state

    text = f"✨ **Подтверждение обновления Местоположения** (ID: `{location_id}`) ✨\n\n"

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
    await state.set_state(LocationUpdateFSM.confirm_update)


async def process_location_update_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение обновления местоположения (UPDATE FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    location_id = user_data.get("updating_location_id")
    new_name = user_data.get("new_name") # Получено из FSM state

    # Формируем словарь с данными для обновления
    update_data = {"name": new_name}

    # Вызываем функцию обновления из utils/db.py
    updated_location = db.update_location(location_id, update_data)

    if updated_location:
        # Экранируем новое название для MarkdownV2
        updated_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_location.name)
        await callback_query.message.edit_text(
            f"🎉 **Местоположение (ID: `{location_id}`) успешно обновлено!** 🎉"
            f"\nНовое название: `{updated_name_esc}`",
            parse_mode="MarkdownV2"
        )
    else:
        # TODO: Добавить более конкретную ошибку из db.update_location, если возможно (IntegrityError)
        await callback_query.message.edit_text(
            f"❌ **Ошибка при обновлении местоположения (ID: `{location_id}`).**\n"
            "Возможно, местоположение с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# Примечание: Отдельный хэндлер cancel_update_location не нужен,
# если используется общий cancel_fsm_handler, зарегистрированный на State("*")


# --- Router Registration ---
# Создаем роутер специально для FSM обновления местоположения
location_update_fsm_router = Router(name="location_update_fsm_router")

def register_location_update_handlers(router: Router):
    """Регистрирует обработчики FSM обновления местоположения."""

    # ENTRY POINT: Запуск FSM по колбэку "Редактировать" из детального просмотра местоположения
    # Используем F.data.startswith для фильтрации по префиксу инициации обновления местоположения
    router.callback_query.register(
        start_location_update,
        F.data.startswith(LOCATION_UPDATE_INIT_CALLBACK_PREFIX)
        # Без фильтра состояний, т.к. это вход в FSM
    )

    # Обработчик ввода названия (ожидает текстовый ввод с определенным состоянием)
    router.message.register(process_location_name_update, LocationUpdateFSM.waiting_for_name)

    # Хэндлер подтверждения (ожидает колбэк с определенным состоянием и колбэком подтверждения)
    router.callback_query.register(
        process_location_update_confirm,
        LocationUpdateFSM.confirm_update,
        F.data == CONFIRM_ACTION_CALLBACK
    )

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера
    # Например, на родительском admin_router или главном dp с фильтром State("*") и Text(CANCEL_FSM_CALLBACK).
    # router.callback_query.register(cancel_fsm_handler, Text(CANCEL_FSM_CALLBACK), State("*"))

# Вызываем функцию регистрации для этого роутера
register_location_update_handlers(location_update_fsm_router)

# Роутер location_update_fsm_router теперь содержит все обработчики и готов к включению в основной диспатчер/роутер.
