# your_bot/handlers/fsm/stock_update_fsm.py
# FSM диалог для обновления существующей записи остатка

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Union

# Импорт функций работы с БД
# Используем относительный импорт
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK
# Импорт админских констант
from ..admin_constants_aiogram import STOCK_UPDATE_INIT_CALLBACK_PREFIX

# Импорт хелпера для отправки/редактирования сообщений из admin_list_detail_handlers_aiogram
# Импортируем здесь, чтобы избежать циклического импорта на уровне модуля
from ..admin_list_detail_handlers_aiogram import _send_or_edit_message

# Настройка логирования
logger = logging.getLogger(__name__)


# --- FSM States ---
class StockUpdateFSM(StatesGroup):
    """Состояния для диалога обновления остатка."""
    waiting_for_quantity = State()
    confirm_update = State()

# --- Handlers ---
async def start_stock_update(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог обновления остатка."""
    await callback_query.answer()

    # Парсим product_id и location_id из callback_data (составной ключ)
    try:
        # Ожидается формат callback_data: {префикс_инициации_обновления}{product_id}:{location_id}
        ids_str = callback_query.data.replace(STOCK_UPDATE_INIT_CALLBACK_PREFIX, "")
        product_id_str, location_id_str = ids_str.split(':')
        product_id = int(product_id_str)
        location_id = int(location_id_str)
    except ValueError:
        logger.error(f"Некорректный ID остатка в колбэке обновления: {callback_query.data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Некорректный ID остатка для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Получаем текущие данные остатка из БД
    # Важно загрузить связанные Product и Location для отображения имен в сообщении
    # db.get_stock_by_ids возвращает Stock объект, связи должны быть доступны через lazy loading
    stock_item = db.get_stock_by_ids(product_id, location_id)
    if not stock_item:
        logger.error(f"Запись остатка для product_id={product_id}, location_id={location_id} не найдена для обновления.")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Запись остатка не найдена для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Получаем названия товара и локации для удобства отображения в подтверждении
    # Полагаемся на lazy loading или то, что get_stock_by_ids мог загрузить связи
    product_name = stock_item.product.name if hasattr(stock_item, 'product') and stock_item.product else "Неизвестный товар"
    location_name = stock_item.location.name if hasattr(stock_item, 'location') and stock_item.location else "Неизвестная локация"

    # Сбрасываем FSM перед началом нового диалога (если не был сброшен ранее)
    await state.clear() # Сброс в начале FSM диалога обновления

    # Сохраняем текущие данные и ID в контексте FSM
    await state.update_data(
        updating_product_id=product_id,
        updating_location_id=location_id,
        original_quantity=stock_item.quantity,
        product_name=product_name, # Сохраняем имена для подтверждения
        location_name=location_name
    )

    # Остаток имеет только одно поле для обновления: quantity
    await state.set_state(StockUpdateFSM.waiting_for_quantity)
    # Редактируем сообщение, откуда пришел колбэк (детали)
    # Экранируем имена для MarkdownV2
    product_name_esc = types.utils.markdown.text_decorations.escape_markdown(product_name)
    location_name_esc = types.utils.markdown.text_decorations.escape_markdown(location_name)
    quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(stock_item.quantity))

    await _send_or_edit_message(
        callback_query,
        f"📝 **Обновление Остатка**\n"
        f"Товар: `{product_name_esc}` (ID: `{product_id}`)\n"
        f"Локация: `{location_name_esc}` (ID: `{location_id}`)\n\n"
        f"Текущее количество: `{quantity_esc}`\n\n"
        f"Введите новое количество (целое неотрицательное число) или нажмите 'Отмена'.",
        parse_mode="MarkdownV2"
    )

async def process_stock_quantity_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое количество остатка (UPDATE FSM)."""
    quantity_str = message.text.strip()
    user_data = await state.get_data()
    product_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get("product_name", "N/A"))
    location_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get("location_name", "N/A"))


    try:
        new_quantity = int(quantity_str)
        if new_quantity < 0:
            await message.answer("Количество не может быть отрицательным. Введите целое неотрицательное число или 'Отмена'.")
            # Остаемся в текущем состоянии StockUpdateFSM.waiting_for_quantity
            return
    except ValueError:
        await message.answer("Некорректный формат количества. Введите целое неотрицательное число или 'Отмена'.")
        # Остаемся в текущем состоянии StockUpdateFSM.waiting_for_quantity
        return

    await state.update_data(new_quantity=new_quantity)
    # Экранируем новое количество для MarkdownV2
    new_quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(new_quantity))
    await message.answer(f"Новое количество: `{new_quantity_esc}` шт.", parse_mode="MarkdownV2")


    # Переходим к подтверждению
    await show_stock_update_confirm(message, state) # Отправляем новое сообщение с подтверждением


async def show_stock_update_confirm(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения обновления остатка (UPDATE FSM)."""
    user_data = await state.get_data()
    product_id = user_data.get("updating_product_id")
    location_id = user_data.get("updating_location_id")
    product_name = user_data.get("product_name")
    location_name = user_data.get("location_name")
    original_quantity = user_data.get("original_quantity")
    new_quantity = user_data.get("new_quantity") # Получено из FSM state

    # Экранируем все для MarkdownV2
    product_name_esc = types.utils.markdown.text_decorations.escape_markdown(product_name)
    location_name_esc = types.utils.markdown.text_decorations.escape_markdown(location_name)
    original_quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(original_quantity))
    new_quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(new_quantity))


    text = f"✨ **Подтверждение обновления Остатка** ✨\n\n"
    text += f"**Товар:** `{product_name_esc}` (ID: `{product_id}`)\n"
    text += f"**Местоположение:** `{location_name_esc}` (ID: `{location_id}`)\n"

    # Показываем изменения количества
    if new_quantity != original_quantity:
        text += f"**Количество:** ~~`{original_quantity_esc}`~~ → `{new_quantity_esc}` шт.\n"
    else:
        text += f"**Количество:** `{original_quantity_esc}` шт. (без изменений)\n"

    text += "\nВсе верно? Подтвердите или отмените."

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить обновление", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Используем target.answer, т.к. предыдущий шаг был message.register
    await target.answer(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    await state.set_state(StockUpdateFSM.confirm_update)


async def process_stock_update_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение обновления остатка (UPDATE FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    product_id = user_data.get("updating_product_id")
    location_id = user_data.get("updating_location_id")
    new_quantity = user_data.get("new_quantity") # Получено из FSM state

    # Вызываем функцию обновления из utils/db.py
    # db.update_stock_quantity вернет None только если запись не найдена (что не должно случиться)
    updated_stock_item = db.update_stock_quantity(product_id, location_id, new_quantity)

    if updated_stock_item:
         # Экранируем новое количество для MarkdownV2
        updated_quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(updated_stock_item.quantity))
        await callback_query.message.edit_text(
            f"🎉 **Остаток (Товар ID: `{product_id}`, Локация ID: `{location_id}`) успешно обновлен!** 🎉"
            f"\nНовое количество: `{updated_quantity_esc}`",
            parse_mode="MarkdownV2"
        )
    else:
        # update_stock_quantity вернет None только если запись не найдена
        # что не должно случиться, т.к. мы ее нашли в start_stock_update
        await callback_query.message.edit_text(
            f"❌ **Ошибка при обновлении остатка (Товар ID: `{product_id}`, Локация ID: `{location_id}`).**\n"
            "Запись не найдена или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# Примечание: Отдельный хэндлер cancel_update_stock не нужен,
# если используется общий cancel_fsm_handler, зарегистрированный на State("*")


# --- Router Registration ---
# Создаем роутер специально для FSM обновления остатка
stock_update_fsm_router = Router(name="stock_update_fsm_router")

def register_stock_update_handlers(router: Router):
    """Регистрирует обработчики FSM обновления остатка."""

    # ENTRY POINT: Запуск FSM по колбэку "Редактировать" из детального просмотра остатка
    # Используем F.data.startswith для фильтрации по префиксу инициации обновления остатка
    router.callback_query.register(
        start_stock_update,
        F.data.startswith(STOCK_UPDATE_INIT_CALLBACK_PREFIX)
        # Без фильтра состояний, т.к. это вход в FSM
    )

    # Обработчик ввода количества (ожидает текстовый ввод с определенным состоянием)
    router.message.register(process_stock_quantity_update, StockUpdateFSM.waiting_for_quantity)

    # Хэндлер подтверждения (ожидает колбэк с определенным состоянием и колбэком подтверждения)
    router.callback_query.register(
        process_stock_update_confirm,
        StockUpdateFSM.confirm_update,
        F.data == CONFIRM_ACTION_CALLBACK
    )

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера
    # Например, на родительском admin_router или главном dp с фильтром State("*") и Text(CANCEL_FSM_CALLBACK).
    # router.callback_query.register(cancel_fsm_handler, Text(CANCEL_FSM_CALLBACK), State("*"))

# Вызываем функцию регистрации для этого роутера
register_stock_update_handlers(stock_update_fsm_router)

# Роутер stock_update_fsm_router теперь содержит все обработчики и готов к включению в основной диспатчер/роутер.
