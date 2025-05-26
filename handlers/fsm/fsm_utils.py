# your_bot/handlers/fsm/fsm_utils.py
# Общие утилиты и хелперы для FSM диалогов

import math
import logging
from typing import List, Any, Callable, Union, Optional # Добавляем Optional
from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State # Импортируем State для State("*")

# Импортируем константы главного адmin-меню для возврата (для cancel_fsm_handler)
# Используем относительный импорт
from ..admin_constants_aiogram import ADMIN_BACK_MAIN

# Константа для отмены FSM
CANCEL_FSM_CALLBACK = "cancel_fsm"
# Константа для подтверждения в FSM
CONFIRM_ACTION_CALLBACK = "confirm_action"

# Специальный маркер для пропуска ввода текстового поля в FSM
SKIP_INPUT_MARKER = "-"

# Базовый префикс для колбэков выбора в FSM (нужно добавлять специфичный префикс сущности)
SELECT_ITEM_CALLBACK_PREFIX = "select_item:" # В новых FSM будем использовать более специфичные префиксы
PAGINATION_CALLBACK_PREFIX = "page:"


def generate_pagination_keyboard(
    items: List[Any],
    current_page: int,
    page_size: int,
    select_callback_prefix: str, # Префикс для колбэка выбора (например, 'select_category:')
    pagination_callback_prefix: str, # Префикс для колбэка пагинации (например, 'category_page:')
    item_text_func: Callable[[Any], str], # Функция, возвращающая текст кнопки для элемента
    item_id_func: Callable[[Any], Union[int, str]], # Функция, возвращающая ID элемента
    extra_buttons: Optional[List[List[types.InlineKeyboardButton]]] = None, # Дополнительные кнопки (например, "Пропустить")
    cancel_callback: str = CANCEL_FSM_CALLBACK # Колбэк для кнопки отмены
) -> types.InlineKeyboardMarkup:
    """
    Генерирует Inline-клавиатуру с пагинацией и кнопками выбора элементов.
    Добавлен аргумент extra_buttons для добавления кнопок вроде "Пропустить".
    """
    keyboard_buttons = []
    total_items = len(items)
    total_pages = math.ceil(total_items / page_size)
    start_index = current_page * page_size
    end_index = min(start_index + page_size, total_items)

    # Добавляем кнопки для элементов текущей страницы
    if items: # Только если есть элементы для отображения
        for item in items[start_index:end_index]:
            button_text = item_text_func(item)
            # Убедимся, что item_id_func возвращает строку или int, и конвертируем в строку для колбэка
            button_callback = f"{select_callback_prefix}{str(item_id_func(item))}"
            keyboard_buttons.append([types.InlineKeyboardButton(text=button_text, callback_data=button_callback)])
    else:
        # Если нет элементов, добавляем информационную кнопку (опционально)
        keyboard_buttons.append([types.InlineKeyboardButton(text="Нет доступных элементов", callback_data="ignore")])


    # Добавляем кнопки пагинации
    pagination_row = []
    # Кнопки пагинации показываем только если страниц больше одной или если есть элементы
    if total_pages > 1:
        if current_page > 0:
            pagination_row.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{pagination_callback_prefix}{current_page - 1}"))
        # Показываем текущую страницу и общее количество страниц
        pagination_row.append(types.InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="ignore")) # Кнопка-заглушка
        if current_page < total_pages - 1:
            pagination_row.append(types.InlineKeyboardButton(text="➡️ Вперед", callback_data=f"{pagination_callback_prefix}{current_page + 1}"))
    # Добавляем строку пагинации, только если она не пустая
    if pagination_row:
        keyboard_buttons.append(pagination_row)

    # Добавляем дополнительные кнопки (например, "Пропустить выбор")
    if extra_buttons:
        keyboard_buttons.extend(extra_buttons)

    # Кнопка отмены
    # Если cancel_callback = "ignore", то кнопку отмены не добавляем
    if cancel_callback != "ignore":
        keyboard_buttons.append([types.InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)])


    return types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# Общий хэндлер отмены (может быть зарегистрирован на State("*") и Text(CANCEL_FSM_CALLBACK))
async def cancel_fsm_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Общий обработчик для отмены любого FSM-диалога.
    """
    await callback_query.answer("Отменено", show_alert=True)
    current_state = await state.get_state()
    if current_state is None:
        logging.warning(f"Отмена запрошена без активного FSM для пользователя {callback_query.from_user.id}. Callback data: {callback_query.data}")
        # Возможно, нужно просто удалить сообщение или обновить его
        try:
             await callback_query.message.edit_text("❌ **Действие уже было отменено или завершено.**")
        except: pass # Игнорируем ошибку, если сообщение не удалось отредактировать
        # Отправляем главное меню в любом случае
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return # Нет активного состояния FSM


    logging.info(f"FSM dialogue cancelled by user {callback_query.from_user.id} in state {current_state}")

    await state.clear() # Сбрасываем состояние и данные FSM
    try:
        await callback_query.message.edit_text("❌ **Действие отменено.**")
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения после отмены FSM: {e}")
        await callback_query.message.answer("❌ **Действие отменено.**")

    # Отправляем сообщение с главным меню
    # Импортируем здесь, чтобы избежать циклического импорта на уровне модулей
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state) # Передаем callback_query для редактирования/ответа

