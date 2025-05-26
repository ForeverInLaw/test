# your_bot/handlers/fsm/product_add_fsm.py
# FSM диалог для добавления нового товара

import logging
import math
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Union
from decimal import Decimal # Импорт Decimal для цены

# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK, generate_pagination_keyboard, PAGINATION_CALLBACK_PREFIX, SKIP_INPUT_MARKER

# Префиксы для колбэков пагинации и выбора в ADD FSM
PRODUCT_CATEGORY_PAGE_CALLBACK_PREFIX_ADD = "add_prod_cat_page:"
SELECT_PRODUCT_CATEGORY_CALLBACK_PREFIX_ADD = "add_prod_cat_sel:"
PRODUCT_MANUFACTURER_PAGE_CALLBACK_PREFIX_ADD = "add_prod_man_page:"
SELECT_PRODUCT_MANUFACTURER_CALLBACK_PREFIX_ADD = "add_prod_man_sel:"

# Размер страницы для пагинации
PRODUCT_PAGE_SIZE_ADD = 10

# --- FSM States ---
class ProductAddFSM(StatesGroup):
    """Состояния для диалога добавления товара."""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category_selection = State()
    waiting_for_manufacturer_selection = State()
    confirm_add = State()

# --- Handlers ---
async def start_product_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог добавления товара."""
    await callback_query.answer()
    # Сбрасываем FSM перед началом нового диалога
    await state.clear()
    await state.set_state(ProductAddFSM.waiting_for_name)
    await callback_query.message.edit_text( # Редактируем сообщение, откуда пришел колбэк
        "📝 **Добавление Товара**\n\n"
        "Введите название нового товара или нажмите 'Отмена'."
    )

async def process_product_name(message: types.Message, state: FSMContext):
    """Обрабатывает введенное название товара."""
    product_name = message.text.strip()
    if not product_name:
        await message.answer("Название товара не может быть пустым. Введите название или 'Отмена'.")
        return

    await state.update_data(name=product_name)
    await state.set_state(ProductAddFSM.waiting_for_description)
    await message.answer("Введите описание товара (можно пропустить, отправив `-`).")

async def process_product_description(message: types.Message, state: FSMContext):
    """Обрабатывает введенное описание товара."""
    description = message.text.strip()
    # Обрабатываем случай пропуска (если пользователь отправил '-')
    if description == SKIP_INPUT_MARKER:
        description = None
        await message.answer("Описание пропущено (установлено в Нет).")
    elif not description: # Пустое сообщение тоже считаем пропуском
         description = None
         await message.answer("Описание сброшено (установлено в Нет).")
    # else: description уже содержит введенный текст

    await state.update_data(description=description)
    await state.set_state(ProductAddFSM.waiting_for_price)
    await message.answer("Введите цену товара (например, `123.45`).")


async def process_product_price(message: types.Message, state: FSMContext):
    """Обрабатывает введенную цену товара."""
    price_str = message.text.strip()
    try:
        # Пытаемся преобразовать в число с плавающей точкой
        price = float(price_str)
        if price < 0:
            await message.answer("Цена не может быть отрицательной. Введите корректную цену или 'Отмена'.")
            return
        # SQLAlchemy DECIMAL(10, 2) может потребовать округления
        price = Decimal(round(price, 2)) # Сохраняем как Decimal для точности
        await state.update_data(price=price)
        await message.answer(f"Цена принята: `{price:.2f}` руб.", parse_mode="MarkdownV2")
    except ValueError:
        await message.answer("Некорректный формат цены. Введите число (например, `123` или `123.45`) или 'Отмена'.")
        return

    # Переходим к выбору категории
    all_categories = db.get_all_categories()
    if not all_categories:
        await state.clear() # Сбрасываем FSM, т.к. товар нельзя добавить без категории
        await message.answer(
            "❌ Невозможно добавить товар без категории.\n"
            "Пожалуйста, сначала добавьте хотя бы одну категорию через раздел 'Управление категориями'."
        )
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(message, state)
        return

    await state.update_data(available_categories_add=all_categories, category_page_add=0)
    await state.set_state(ProductAddFSM.waiting_for_category_selection)
    await show_product_category_selection_add(message, state) # Отправляем новое сообщение


async def show_product_category_selection_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список категорий для выбора товара с пагинацией (ADD FSM)."""
    user_data = await state.get_data()
    categories = user_data.get("available_categories_add", [])
    current_page = user_data.get("category_page_add", 0)

    if not categories: # Должно быть проверено ранее, но на всякий случай
         await state.clear()
         text = "❌ Невозможно добавить товар без категории.\nПожалуйста, сначала добавьте хотя бы одну категорию."
         if isinstance(target, types.CallbackQuery):
             await target.message.edit_text(text)
             from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
             await show_admin_main_menu_aiogram(target, state)
         else:
              await target.answer(text)
         return

    def format_category_button_text(category: db.Category) -> str:
        return f"📂 {category.name}"

    reply_markup = generate_pagination_keyboard(
        items=categories,
        current_page=current_page,
        page_size=PRODUCT_PAGE_SIZE_ADD,
        select_callback_prefix=SELECT_PRODUCT_CATEGORY_CALLBACK_PREFIX_ADD,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{PRODUCT_CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':')}:",
        item_text_func=format_category_button_text,
        item_id_func=lambda c: c.id
    )

    text = f"Выберите категорию для товара (страница {current_page + 1}):"

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def process_product_category_selection_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор категории для товара (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "add_prod_cat_sel:123"
    try:
        action, category_id_str = data.split(":")
        category_id = int(category_id_str)
    except ValueError:
        logging.error(f"Некорректный формат callback_data для выбора категории товара в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе категории.")
        await show_product_category_selection_add(callback_query, state) # Показать список заново
        return


    selected_category = db.get_category_by_id(category_id)
    if not selected_category:
        await callback_query.message.answer("Выбранная категория не найдена. Попробуйте еще раз.")
        await show_product_category_selection_add(callback_query, state) # Показать список заново
        return

    await state.update_data(category_id=category_id, category_name=selected_category.name)
    await callback_query.message.edit_text(f"Выбрана категория: `{types.utils.markdown.text_decorations.escape_markdown(selected_category.name)}`.", parse_mode="MarkdownV2")


    # Переходим к выбору производителя
    await state.set_state(ProductAddFSM.waiting_for_manufacturer_selection)
    all_manufacturers = db.get_all_manufacturers()
    if not all_manufacturers:
         await state.clear() # Сбрасываем FSM, т.к. товар нельзя добавить без производителя
         await callback_query.message.answer(
            "❌ Невозможно добавить товар без производителя.\n"
            "Пожалуйста, сначала добавьте хотя бы одного производителя через раздел 'Управление производителями'."
         )
         from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
         await show_admin_main_menu_aiogram(callback_query, state)
         return

    await state.update_data(available_manufacturers_add=all_manufacturers, manufacturer_page_add=0)
    await show_product_manufacturer_selection_add(callback_query, state) # Отправляем/редактируем сообщение


async def process_product_category_pagination_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора категории (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:add_prod_cat:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != PRODUCT_CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':'):
        logging.error(f"Некорректный формат callback_data для пагинации категории товара в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_product_category_selection_add(callback_query, state) # Показать текущий список снова
        return

    new_page = int(parts[2])

    user_data = await state.get_data()
    categories = user_data.get("available_categories_add", [])
    total_pages = math.ceil(len(categories) / PRODUCT_PAGE_SIZE_ADD)

    if 0 <= new_page < total_pages:
        await state.update_data(category_page_add=new_page)
        await show_product_category_selection_add(callback_query, state)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def show_product_manufacturer_selection_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список производителей для выбора товара с пагинацией (ADD FSM)."""
    user_data = await state.get_data()
    manufacturers = user_data.get("available_manufacturers_add", [])
    current_page = user_data.get("manufacturer_page_add", 0)

    if not manufacturers: # Должно произойти, т.к. проверено в предыдущем шаге
        text = "❌ Невозможно добавить товар без производителя.\nПожалуйста, сначала добавьте хотя бы одного производителя."
        await state.clear()
        if isinstance(target, types.CallbackQuery): await target.message.edit_text(text)
        else: await target.answer(text)
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(target, state)
        return

    def format_manufacturer_button_text(manufacturer: db.Manufacturer) -> str:
        return f"🏭 {manufacturer.name}"

    reply_markup = generate_pagination_keyboard(
        items=manufacturers,
        current_page=current_page,
        page_size=PRODUCT_PAGE_SIZE_ADD,
        select_callback_prefix=SELECT_PRODUCT_MANUFACTURER_CALLBACK_PREFIX_ADD,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{PRODUCT_MANUFACTURER_PAGE_CALLBACK_PREFIX_ADD.strip(':')}:",
        item_text_func=format_manufacturer_button_text,
        item_id_func=lambda m: m.id
    )

    text = f"Выберите производителя для товара (страница {current_page + 1}):"

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)


async def process_product_manufacturer_selection_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор производителя для товара (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "add_prod_man_sel:123"
    try:
        action, manufacturer_id_str = data.split(":")
        manufacturer_id = int(manufacturer_id_str)
    except ValueError:
        logging.error(f"Некорректный формат callback_data для выбора производителя товара в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе производителя.")
        await show_product_manufacturer_selection_add(callback_query, state) # Показать список заново
        return

    selected_manufacturer = db.get_manufacturer_by_id(manufacturer_id)
    if not selected_manufacturer:
        await callback_query.message.answer("Выбранный производитель не найден. Попробуйте еще раз.")
        await show_product_manufacturer_selection_add(callback_query, state) # Показать список заново
        return

    await state.update_data(manufacturer_id=manufacturer_id, manufacturer_name=selected_manufacturer.name)
    await callback_query.message.edit_text(f"Выбран производитель: `{types.utils.markdown.text_decorations.escape_markdown(selected_manufacturer.name)}`.", parse_mode="MarkdownV2")


    # Переходим к подтверждению
    await show_product_confirm_add(callback_query, state)


async def process_product_manufacturer_pagination_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора производителя (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:add_prod_man:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != PRODUCT_MANUFACTURER_PAGE_CALLBACK_PREFIX_ADD.strip(':'):
        logging.error(f"Некорректный формат callback_data для пагинации производителя товара в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_product_manufacturer_selection_add(callback_query, state)
        return


    new_page = int(parts[2])

    user_data = await state.get_data()
    manufacturers = user_data.get("available_manufacturers_add", [])
    total_pages = math.ceil(len(manufacturers) / PRODUCT_PAGE_SIZE_ADD)

    if 0 <= new_page < total_pages:
        await state.update_data(manufacturer_page_add=new_page)
        await show_product_manufacturer_selection_add(callback_query, state)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def show_product_confirm_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает данные для подтверждения добавления товара (ADD FSM)."""
    user_data = await state.get_data()
    name = user_data.get("name")
    description = user_data.get("description")
    price = user_data.get("price") # Это уже Decimal
    category_name = user_data.get("category_name")
    manufacturer_name = user_data.get("manufacturer_name")

    text = (
        "✨ **Подтверждение добавления Товара** ✨\n\n"
        f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(name)}`\n"
    )
    if description:
        text += f"**Описание:** `{types.utils.markdown.text_decorations.escape_markdown(description)}`\n"
    text += (
        f"**Цена:** `{types.utils.markdown.text_decorations.escape_markdown(f'{price:.2f}')} руб.`\n" # Форматируем цену
        f"**Категория:** `{types.utils.markdown.text_decorations.escape_markdown(category_name)}`\n"
        f"**Производитель:** `{types.utils.markdown.text_decorations.escape_markdown(manufacturer_name)}`\n\n"
        "Все верно? Подтвердите или отмените."
    )


    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    if isinstance(target, types.CallbackQuery):
         await target.message.edit_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    else:
         await target.answer(text, reply_markup=reply_markup, parse_mode="MarkdownV2") # unlikely to happen here

    await state.set_state(ProductAddFSM.confirm_add)


async def process_product_confirm_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение добавления товара (ADD FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    name = user_data.get("name")
    description = user_data.get("description")
    price = user_data.get("price") # Это уже Decimal
    category_id = user_data.get("category_id")
    manufacturer_id = user_data.get("manufacturer_id")

    # Вызываем функцию добавления из utils/db.py
    new_product = db.add_product(
        name=name,
        description=description,
        price=float(price), # db expects float or Decimal? db.py uses DECIMAL(10,2), should pass Decimal
        category_id=category_id,
        manufacturer_id=manufacturer_id
    )

    if new_product:
        await callback_query.message.edit_text(
            "🎉 **Товар успешно добавлен!** 🎉\n"
            f"**ID:** `{new_product.id}`\n"
            f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(new_product.name)}`"
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Ошибка при добавлении товара.**\n"
            "Проверьте, существуют ли выбранные категория и производитель, или произошла другая ошибка." # TODO: Более детальная ошибка?
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# --- Router Registration ---
def register_product_add_handlers(router: Router):
    # ENTRY POINT
    router.callback_query.register(start_product_add, F.data == "product_add_action") # Начало FSM

    # Handlers for text/numeric inputs
    router.message.register(process_product_name, ProductAddFSM.waiting_for_name)
    router.message.register(process_product_description, ProductAddFSM.waiting_for_description)
    router.message.register(process_product_price, ProductAddFSM.waiting_for_price)

    # Handlers for category selection/pagination
    router.callback_query.register(
        process_product_category_selection_add,
        ProductAddFSM.waiting_for_category_selection,
        F.data.startswith(SELECT_PRODUCT_CATEGORY_CALLBACK_PREFIX_ADD) # Выбор категории
    )
    router.callback_query.register(
        process_product_category_pagination_add,
        ProductAddFSM.waiting_for_category_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{PRODUCT_CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':')}") # Пагинация
    )

    # Handlers for manufacturer selection/pagination
    router.callback_query.register(
        process_product_manufacturer_selection_add,
        ProductAddFSM.waiting_for_manufacturer_selection,
        F.data.startswith(SELECT_PRODUCT_MANUFACTURER_CALLBACK_PREFIX_ADD) # Выбор производителя
    )
    router.callback_query.register(
        process_product_manufacturer_pagination_add,
        ProductAddFSM.waiting_for_manufacturer_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{PRODUCT_MANUFACTURER_PAGE_CALLBACK_PREFIX_ADD.strip(':')}") # Пагинация
    )

    # Confirmation handler
    router.callback_query.register(process_product_confirm_add, ProductAddFSM.confirm_add, F.data == CONFIRM_ACTION_CALLBACK)

    # Общий хэндлер отмены регистрируется отдельно
