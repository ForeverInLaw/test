# your_bot/handlers/fsm/category_add_fsm.py
# FSM диалог для добавления новой категории

import logging
import math
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Optional, Union

# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит
from .fsm_utils import CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK, generate_pagination_keyboard, PAGINATION_CALLBACK_PREFIX

# Префиксы для колбэков пагинации и выбора категории
# Используем PAGINATION_CALLBACK_PREFIX из fsm_utils + уникальный префикс для пагинации
CATEGORY_PAGE_CALLBACK_PREFIX_ADD = "add_cat_page:" # Уникальный префикс пагинации для ADD FSM
SELECT_PARENT_CATEGORY_CALLBACK_PREFIX_ADD = "add_cat_parent_sel:" # Уникальный префикс выбора для ADD FSM

# Размер страницы для пагинации категорий
CATEGORY_PAGE_SIZE_ADD = 10 # Может отличаться от Update/List


# --- FSM States ---
class CategoryAddFSM(StatesGroup):
    """Состояния для диалога добавления категории."""
    waiting_for_name = State()
    waiting_for_parent_decision = State() # Ждем ответа, нужна ли родительская категория
    waiting_for_parent_selection = State() # Ждем выбора родительской категории из списка
    confirm_add = State()

# --- Handlers ---
async def start_category_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог добавления категории."""
    await callback_query.answer()
    # Сбрасываем FSM перед началом нового диалога
    await state.clear()
    await state.set_state(CategoryAddFSM.waiting_for_name)
    await callback_query.message.edit_text( # Редактируем сообщение, откуда пришел колбэк
        "📝 **Добавление Категории**\n\n"
        "Введите название новой категории или нажмите 'Отмена'."
    )

async def process_category_name(message: types.Message, state: FSMContext):
    """Обрабатывает введенное название категории."""
    category_name = message.text.strip()
    if not category_name:
        await message.answer("Название категории не может быть пустым. Введите название или 'Отмена'.")
        return
    # Добавить проверку на 'Отмена' текст? Нет, отмена только по кнопке CANCEL_FSM_CALLBACK

    # TODO: Добавить проверку на уникальность имени перед сохранением (можно и на шаге подтверждения/сохранения)

    await state.update_data(name=category_name)

    # Спрашиваем про родительскую категорию
    keyboard = [
        [types.InlineKeyboardButton(text="✅ Да", callback_data="add_cat_parent_yes")],
        [types.InlineKeyboardButton(text="🚫 Нет", callback_data="add_cat_parent_no")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await state.set_state(CategoryAddFSM.waiting_for_parent_decision)
    # Отправляем новое сообщение для следующего шага FSM
    await message.answer(
        f"Название: `{types.utils.markdown.text_decorations.escape_markdown(category_name)}`\n\n"
        "Хотите указать родительскую категорию?",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def process_parent_decision_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает решение о наличии родительской категории."""
    await callback_query.answer()
    decision = callback_query.data

    if decision == "add_cat_parent_no":
        await state.update_data(parent_id=None, parent_name="Нет")
        await show_category_confirm_add(callback_query, state) # Переходим сразу к подтверждению
    elif decision == "add_cat_parent_yes":
        # Получаем список всех категорий для выбора
        all_categories = db.get_all_categories()
        if not all_categories:
            # Если категорий нет, нельзя выбрать родительскую
            await state.update_data(parent_id=None, parent_name="Нет (нет доступных категорий)")
            await callback_query.message.edit_text(
                "ℹ️ В системе еще нет других категорий, чтобы выбрать родительскую.\n"
                "Категория будет добавлена без родителя."
            )
            await show_category_confirm_add(callback_query, state)
            return

        # Храним список категорий и текущую страницу в контексте для пагинации
        await state.update_data(available_categories_add=all_categories, parent_page_add=0)

        await state.set_state(CategoryAddFSM.waiting_for_parent_selection)
        # Отправляем/редактируем сообщение для показа списка
        await show_parent_category_selection_add(callback_query, state)
    else:
        await callback_query.message.answer("Неизвестное решение. Выберите 'Да', 'Нет' или 'Отмена'.")
        # Остаемся в текущем состоянии
        # Можно повторно отправить клавиатуру решения
        user_data = await state.get_data()
        keyboard = [
            [types.InlineKeyboardButton(text="✅ Да", callback_data="add_cat_parent_yes")],
            [types.InlineKeyboardButton(text="🚫 Нет", callback_data="add_cat_parent_no")],
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback_query.message.edit_text(
             f"Название: `{types.utils.markdown.text_decorations.escape_markdown(user_data.get('name', 'N/A'))}`\n\n"
             "Хотите указать родительскую категорию?\n*Выберите 'Да' или 'Нет'.*",
             reply_markup=reply_markup,
             parse_mode="MarkdownV2"
        )


async def show_parent_category_selection_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список категорий для выбора родительской с пагинацией (ADD FSM)."""
    user_data = await state.get_data()
    categories = user_data.get("available_categories_add", [])
    current_page = user_data.get("parent_page_add", 0)

    if not categories:
        # Этого не должно произойти после проверки в process_parent_decision_add, но на всякий случай
         await state.update_data(parent_id=None, parent_name="Нет (нет доступных категорий)")
         text = "ℹ️ В системе нет доступных категорий для выбора в качестве родительской.\nКатегория будет добавлена без родителя."
         keyboard = [[types.InlineKeyboardButton(text="✅ Продолжить", callback_data="add_cat_continue_without_parent")]] # Уникальный колбэк
         reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
         if isinstance(target, types.CallbackQuery):
             await target.message.edit_text(text, reply_markup=reply_markup)
         else: # Не должен вызываться с Message, но для надежности
              await target.answer(text, reply_markup=reply_markup)
         await state.set_state(CategoryAddFSM.confirm_add) # Перейти к подтверждению
         return

    # Helper function to format item text for the button
    def format_category_button_text(category: db.Category) -> str:
        return f"📂 {category.name}"

    reply_markup = generate_pagination_keyboard(
        items=categories,
        current_page=current_page,
        page_size=CATEGORY_PAGE_SIZE_ADD,
        select_callback_prefix=SELECT_PARENT_CATEGORY_CALLBACK_PREFIX_ADD,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':')}:",
        item_text_func=format_category_button_text,
        item_id_func=lambda c: c.id
    )

    text = f"Выберите родительскую категорию (страница {current_page + 1}):"

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup)
    else:
        await target.answer(text, reply_markup=reply_markup)

async def process_parent_category_selection_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор родительской категории (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "add_cat_parent_sel:123"
    try:
        action, category_id_str = data.split(":")
        category_id = int(category_id_str)
    except ValueError:
        logging.error(f"Некорректный формат callback_data для выбора родительской категории в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе категории.")
        # Показать список заново
        await show_parent_category_selection_add(callback_query, state)
        return


    selected_category = db.get_category_by_id(category_id)
    if not selected_category:
        await callback_query.message.answer("Выбранная категория не найдена. Попробуйте еще раз.")
        await show_parent_category_selection_add(callback_query, state) # Показать список заново
        return

    await state.update_data(parent_id=category_id, parent_name=selected_category.name)

    # Переходим к подтверждению
    await show_category_confirm_add(callback_query, state)


async def process_parent_category_pagination_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора родительской категории (ADD FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:add_cat_par:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':'):
        logging.error(f"Некорректный формат callback_data для пагинации родителя категории в add FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_parent_category_selection_add(callback_query, state) # Показать текущий список снова
        return


    new_page = int(parts[2])

    user_data = await state.get_data()
    categories = user_data.get("available_categories_add", [])
    total_pages = math.ceil(len(categories) / CATEGORY_PAGE_SIZE_ADD)

    if 0 <= new_page < total_pages:
        await state.update_data(parent_page_add=new_page)
        await show_parent_category_selection_add(callback_query, state)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def show_category_confirm_add(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает данные для подтверждения добавления категории (ADD FSM)."""
    user_data = await state.get_data()
    name = user_data.get("name")
    parent_name = user_data.get("parent_name", "Нет") # Используем имя для отображения

    text = (
        "✨ **Подтверждение добавления Категории** ✨\n\n"
        f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(name)}`\n"
        f"**Родительская категория:** `{types.utils.markdown.text_decorations.escape_markdown(parent_name)}`\n\n"
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

    await state.set_state(CategoryAddFSM.confirm_add)


async def process_category_confirm_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение добавления категории (ADD FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    name = user_data.get("name")
    parent_id = user_data.get("parent_id") # Используем ID для сохранения

    # Вызываем функцию добавления из utils/db.py
    new_category = db.add_category(name=name, parent_id=parent_id)

    if new_category:
        await callback_query.message.edit_text(
            "🎉 **Категория успешно добавлена!** 🎉\n"
            f"**ID:** `{new_category.id}`\n"
            f"**Название:** `{types.utils.markdown.text_decorations.escape_markdown(new_category.name)}`"
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Ошибка при добавлении категории.**\n"
            "Возможно, категория с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)


# --- Router Registration ---
# Создаем роутер специально для FSM добавления категории
def register_category_add_handlers(router: Router):
    # ENTRY POINT: Запуск FSM по колбэку "Добавить Категорию" из меню сущности
    router.callback_query.register(start_category_add, F.callback_data == "category_add_action")

    # Обработчики шагов FSM
    router.message.register(process_category_name, CategoryAddFSM.waiting_for_name)
    router.callback_query.register(process_parent_decision_add, CategoryAddFSM.waiting_for_parent_decision)

    # Хэндлеры выбора и пагинации родительской категории
    router.callback_query.register(
        process_parent_category_selection_add,
        CategoryAddFSM.waiting_for_parent_selection,
        F.data.startswith(SELECT_PARENT_CATEGORY_CALLBACK_PREFIX_ADD) # Выбор
    )
    router.callback_query.register(
        process_parent_category_pagination_add,
        CategoryAddFSM.waiting_for_parent_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{CATEGORY_PAGE_CALLBACK_PREFIX_ADD.strip(':')}") # Пагинация
    )
     # Обработчик для случая, если категорий для выбора родителя не нашлось и есть кнопка "Продолжить"
    router.callback_query.register(show_category_confirm_add, CategoryAddFSM.waiting_for_parent_selection, F.callback_data == "add_cat_continue_without_parent")


    # Хэндлер подтверждения
    router.callback_query.register(process_category_confirm_add, CategoryAddFSM.confirm_add, F.callback_data == CONFIRM_ACTION_CALLBACK)

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера
    # router.callback_query.register(cancel_fsm_handler, Text(CANCEL_FSM_CALLBACK), State("*"))
