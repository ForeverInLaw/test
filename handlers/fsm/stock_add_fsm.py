# your_bot/handlers/fsm/stock_add_fsm.py
# FSM диалог для добавления новой записи остатка (связи товар-локация)

import logging
import math
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Union

# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK, generate_pagination_keyboard, PAGINATION_CALLBACK_PREFIX

# Префиксы для колбэков пагинации и выбора в ADD FSM
STOCK_PRODUCT_PAGE_CALLBACK_PREFIX_ADD = "add_stock_prod_page:"
SELECT_STOCK_PRODUCT_CALLBACK_PREFIX_ADD = "add_stock_prod_sel:"
STOCK_LOCATION_PAGE_CALLBACK_PREFIX_ADD = "add_stock_loc_page:"
SELECT_STOCK_LOCATION_CALLBACK_PREFIX_ADD = "add_stock_loc_sel:"

# Размер страницы для пагинации
STOCK_PAGE_SIZE_ADD = 10

# --- FSM States ---
class StockAddFSM(StatesGroup):
    """Состояния для диалога добавления остатка."""
    waiting_for_product_selection = State()
    waiting_for_location_selection = State()
    waiting_for_quantity = State()
    confirm_add = State()

# --- Handlers ---
async def start_stock_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог добавления остатка."""
    await callback_query.answer()
    # Сбрасываем FSM перед началом нового диалога
    await state.clear()

    # Переходим к выбору товара
    all_products = db.get_all_products()
    if not all_products:
        await state.clear() # Сбрасываем FSM, т.к. остаток не добавить без товара
        await callback_query.message.edit_text( # Редактируем сообщение, откуда пришел колбэк
            "❌ Невозможно добавить остаток без товара.\n"
            "Пожалуйста, сначала добавьте хотя бы один товар через раздел 'Управление товарами'."
        )
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    await state.update_data(available_products_add=all_products, product_page_add=0)
    await state.set_state(StockAddFSM.waiting_for_product_selection)
    await show_stock_product_selection_add(callback_query, state)


async def show_stock_product_selection_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список товаров для выбора остатка с пагинацией (ADD FSM)."""
    user_data = await state.get_data()
    products = user_data.get("available_products_add", [])
    current_page = user_data.get("product_page_add", 0)

    if not products: # Должно быть проверено ранее
         await state.clear()
         text = "❌ Невозможно добавить остаток без товара.\nПожалуйста, сначала добавьте хотя бы один товар."
         if isinstance(target, types.CallbackQuery):
             await target.message.edit_text(text)
             from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
             await show_admin_main_menu_aiogram(target, state)
         else:
              await target.answer(text)
         return

    def format_product_button_text(product: db.Product) -> str:
         # Экранируем имя товара для MarkdownV2
         name_esc = types.utils.markdown.text_decorations.escape_markdown(product.name)
         return f"📚 {name_esc} (ID: {product.id})"

    reply_markup = generate_pagination_keyboard(
        items=products,
        current_page=current_page,
        page_size=STOCK_PAGE_SIZE_ADD,
        select_callback_prefix=SELECT_STOCK_PRODUCT_CALLBACK_PREFIX_ADD,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{STOCK_PRODUCT_PAGE_CALLBACK_PREFIX_ADD.strip(':')}:",
        item_text_func=format_product_button_text,
        item_id_func=lambda p: p.id
    )

    text = f"Выберите товар для добавления остатка (страница {current_page + 1}):"

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def process_stock_product_selection_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор товара для остатка (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "add_stock_prod_sel:123"
    try:
        action, product_id_str = data.split(":")
        product_id = int(product_id_str)
    except ValueError:
        logging.error(f"Некорректный формат callback_data для выбора товара в add stock FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе товара.")
        await show_stock_product_selection_add(callback_query, state) # Показать список заново
        return


    selected_product = db.get_product_by_id(product_id)
    if not selected_product:
        await callback_query.message.answer("Выбранный товар не найден. Попробуйте еще раз.")
        await show_stock_product_selection_add(callback_query, state) # Показать список заново
        return

    await state.update_data(product_id=product_id, product_name=selected_product.name)
    await callback_query.message.edit_text(f"Выбран товар: `{types.utils.markdown.text_decorations.escape_markdown(selected_product.name)}`.", parse_mode="MarkdownV2")


    # Переходим к выбору местоположения
    await state.set_state(StockAddFSM.waiting_for_location_selection)
    all_locations = db.get_all_locations()
    if not all_locations:
         await state.clear() # Сбрасываем FSM
         await callback_query.message.answer(
            "❌ Невозможно добавить остаток без местоположения.\n"
            "Пожалуйста, сначала добавьте хотя бы одно местоположение через раздел 'Управление местоположениями'."
         )
         from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
         await show_admin_main_menu_aiogram(callback_query, state)
         return

    await state.update_data(available_locations_add=all_locations, location_page_add=0)
    await show_stock_location_selection_add(callback_query, state)


async def process_stock_product_pagination_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора товара (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:add_stock_prod:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != STOCK_PRODUCT_PAGE_CALLBACK_PREFIX_ADD.strip(':'):
        logging.error(f"Некорректный формат callback_data для пагинации товара в add stock FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_stock_product_selection_add(callback_query, state) # Показать текущий список снова
        return


    new_page = int(parts[2])

    user_data = await state.get_data()
    products = user_data.get("available_products_add", [])
    total_pages = math.ceil(len(products) / STOCK_PAGE_SIZE_ADD)

    if 0 <= new_page < total_pages:
        await state.update_data(product_page_add=new_page)
        await show_stock_product_selection_add(callback_query, state)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def show_stock_location_selection_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список местоположений для выбора остатка с пагинацией (ADD FSM)."""
    user_data = await state.get_data()
    locations = user_data.get("available_locations_add", [])
    current_page = user_data.get("location_page_add", 0)

    if not locations: # Должно быть проверено ранее
         await state.clear()
         text = "❌ Невозможно добавить остаток без местоположения.\nПожалуйста, сначала добавьте хотя бы одно местоположение."
         if isinstance(target, types.CallbackQuery):
             await target.message.edit_text(text)
             from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
             await show_admin_main_menu_aiogram(target, state)
         else:
              await target.answer(text)
         return

    def format_location_button_text(location: db.Location) -> str:
         # Экранируем имя локации для MarkdownV2
         name_esc = types.utils.markdown.text_decorations.escape_markdown(location.name)
         return f"📍 {name_esc} (ID: {location.id})"


    reply_markup = generate_pagination_keyboard(
        items=locations,
        current_page=current_page,
        page_size=STOCK_PAGE_SIZE_ADD,
        select_callback_prefix=SELECT_STOCK_LOCATION_CALLBACK_PREFIX_ADD,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{STOCK_LOCATION_PAGE_CALLBACK_PREFIX_ADD.strip(':')}:",
        item_text_func=format_location_button_text,
        item_id_func=lambda l: l.id
    )

    text = f"Выберите местоположение для остатка (страница {current_page + 1}):"

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def process_stock_location_selection_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор местоположения для остатка (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "add_stock_loc_sel:123"
    try:
        action, location_id_str = data.split(":")
        location_id = int(location_id_str)
    except ValueError:
        logging.error(f"Некорректный формат callback_data для выбора локации в add stock FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе местоположения.")
        await show_stock_location_selection_add(callback_query, state) # Показать список заново
        return

    selected_location = db.get_location_by_id(location_id)
    if not selected_location:
        await callback_query.message.answer("Выбранное местоположение не найдено. Попробуйте еще раз.")
        await show_stock_location_selection_add(callback_query, state) # Показать список заново
        return

    await state.update_data(location_id=location_id, location_name=selected_location.name)

    # Переходим к запросу количества
    await state.set_state(StockAddFSM.waiting_for_quantity)
    # Экранируем имена для MarkdownV2
    prod_name_esc = types.utils.markdown.text_decorations.escape_markdown(await state.get_data("product_name"))
    loc_name_esc = types.utils.markdown.text_decorations.escape_markdown(await state.get_data("location_name"))

    await callback_query.message.edit_text(
        f"Введите количество для товара `{prod_name_esc}` на локации `{loc_name_esc}`:",
        parse_mode="MarkdownV2"
    )

async def process_stock_location_pagination_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора местоположения (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:add_stock_loc:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != STOCK_LOCATION_PAGE_CALLBACK_PREFIX_ADD.strip(':'):
        logging.error(f"Некорректный формат callback_data для пагинации локации в add stock FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_stock_location_selection_add(callback_query, state) # Показать текущий список снова
        return

    new_page = int(parts[2])

    user_data = await state.get_data()
    locations = user_data.get("available_locations_add", [])
    total_pages = math.ceil(len(locations) / STOCK_PAGE_SIZE_ADD)

    if 0 <= new_page < total_pages:
        await state.update_data(location_page_add=new_page)
        await show_stock_location_selection_add(callback_query, state)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def process_stock_quantity(message: types.Message, state: FSMContext):
    """Обрабатывает введенное количество остатка (ADD FSM)."""
    quantity_str = message.text.strip()
    user_data = await state.get_data()
    prod_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get("product_name", "N/A"))
    loc_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get("location_name", "N/A"))

    try:
        quantity = int(quantity_str)
        if quantity < 0:
            await message.answer("Количество не может быть отрицательным. Введите целое неотрицательное число или 'Отмена'.")
            # Остаемся в текущем состоянии StockAddFSM.waiting_for_quantity
            return
    except ValueError:
        await message.answer("Некорректный формат количества. Введите целое неотрицательное число или 'Отмена'.")
        # Остаемся в текущем состоянии StockAddFSM.waiting_for_quantity
        return

    await state.update_data(quantity=quantity)
    await message.answer(f"Количество принято: `{quantity}` шт.", parse_mode="MarkdownV2")

    # Переходим к подтверждению
    await show_stock_confirm_add(message, state)


async def show_stock_confirm_add(target: types.Message, state: FSMContext):
    """Показывает данные для подтверждения добавления остатка (ADD FSM)."""
    user_data = await state.get_data()
    product_name = user_data.get("product_name")
    location_name = user_data.get("location_name")
    quantity = user_data.get("quantity")

    # Экранируем для MarkdownV2
    prod_name_esc = types.utils.markdown.text_decorations.escape_markdown(product_name)
    loc_name_esc = types.utils.markdown.text_decorations.escape_markdown(location_name)
    quantity_esc = types.utils.markdown.text_decorations.escape_markdown(str(quantity))


    text = (
        "✨ **Подтверждение добавления Остатка** ✨\n\n"
        f"**Товар:** `{prod_name_esc}`\n"
        f"**Местоположение:** `{loc_name_esc}`\n"
        f"**Количество:** `{quantity_esc}` шт.\n\n"
        "Все верно? Подтвердите или отмените."
    )

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Используем target.answer, т.к. предыдущий шаг был message.register
    await target.answer(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    await state.set_state(StockAddFSM.confirm_add)


async def process_stock_confirm_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение добавления остатка (ADD FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    product_id = user_data.get("product_id")
    location_id = user_data.get("location_id")
    quantity = user_data.get("quantity")

    # Вызываем функцию добавления из utils/db.py
    # Функция add_stock вернет None, если запись уже существует
    new_stock_item = db.add_stock(
        product_id=product_id,
        location_id=location_id,
        quantity=quantity
    )

    if new_stock_item:
        await callback_query.message.edit_text(
            "🎉 **Запись остатка успешно добавлена!** 🎉\n"
            f"**Товар ID:** `{new_stock_item.product_id}`\n"
            f"**Локация ID:** `{new_stock_item.location_id}`\n"
            f"**Количество:** `{new_stock_item.quantity}` шт."
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Ошибка при добавлении остатка.**\n"
            "Возможно, остаток для этого товара на этой локации уже существует.\n"
            "Используйте функцию редактирования остатков (будет реализована позже)." # TODO: Ссылка на редактирование
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)


# --- Router Registration ---
def register_stock_add_handlers(router: Router):
    # ENTRY POINT
    router.callback_query.register(start_stock_add, F.data == "stock_add_action") # Начало FSM

    # Handlers for product selection/pagination
    router.callback_query.register(
        process_stock_product_selection_add,
        StockAddFSM.waiting_for_product_selection,
        F.data.startswith(SELECT_STOCK_PRODUCT_CALLBACK_PREFIX_ADD)
    )
    router.callback_query.register(
        process_stock_product_pagination_add,
        StockAddFSM.waiting_for_product_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{STOCK_PRODUCT_PAGE_CALLBACK_PREFIX_ADD.strip(':')}")
    )

    # Handlers for location selection/pagination
    router.callback_query.register(
        process_stock_location_selection_add,
        StockAddFSM.waiting_for_location_selection,
        F.data.startswith(SELECT_STOCK_LOCATION_CALLBACK_PREFIX_ADD)
    )
    router.callback_query.register(
        process_stock_location_pagination_add,
        StockAddFSM.waiting_for_location_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{STOCK_LOCATION_PAGE_CALLBACK_PREFIX_ADD.strip(':')}")
    )

    # Handler for quantity input
    router.message.register(process_stock_quantity, StockAddFSM.waiting_for_quantity)

    # Confirmation handler
    router.callback_query.register(process_stock_confirm_add, StockAddFSM.confirm_add, F.data == CONFIRM_ACTION_CALLBACK)

    # Общий хэндлер отмены регистрируется отдельно
