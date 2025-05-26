# your_bot/handlers/fsm/category_update_fsm.py
# FSM диалог для обновления существующей категории

import logging
import math
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from typing import Optional, Union, List

# Импорт функций работы с БД
# Используем относительный импорт
from utils import db

# Импорт общих FSM утилит и констант
from .fsm_utils import (
    CANCEL_FSM_CALLBACK, CONFIRM_ACTION_CALLBACK, generate_pagination_keyboard,
    PAGINATION_CALLBACK_PREFIX, SKIP_INPUT_MARKER
)
# Импорт админских констант
from ..admin_constants_aiogram import (
    CATEGORY_UPDATE_INIT_CALLBACK_PREFIX, UPDATE_CAT_PARENT_PAGE_PREFIX,
    UPDATE_CAT_PARENT_SEL_PREFIX, KEEP_CURRENT_PARENT_CALLBACK
)

# Импорт хелпера для отправки/редактирования сообщений из admin_list_detail_handlers_aiogram
# Импортируем здесь, чтобы избежать циклического импорта на уровне модуля
from ..admin_list_detail_handlers_aiogram import _send_or_edit_message

# Настройка логирования
logger = logging.getLogger(__name__)

# Размер страницы для пагинации категорий при выборе родителя
CATEGORY_PAGE_SIZE_UPDATE = 10 # Может отличаться от ADD/LIST


# --- FSM States ---
class CategoryUpdateFSM(StatesGroup):
    """Состояния для диалога обновления категории."""
    waiting_for_name = State()
    # Note: Ignoring 'waiting_for_description' as per provided DB schema
    waiting_for_parent_decision = State() # Ждем решения: обновить, удалить, оставить родителя
    waiting_for_parent_selection = State() # Ждем выбора новой родительской категории
    confirm_update = State()

# --- Handlers ---
async def start_category_update(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог обновления категории."""
    await callback_query.answer()

    # Парсим ID категории из callback_data
    try:
        # Ожидается формат callback_data: {префикс_инициации_обновления}{id}
        category_id_str = callback_query.data.replace(CATEGORY_UPDATE_INIT_CALLBACK_PREFIX, "")
        category_id = int(category_id_str)
    except ValueError:
        logger.error(f"Некорректный ID категории в колбэке обновления: {callback_query.data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Некорректный ID категории для обновления.")
        await state.clear() # Сбрасываем FSM
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return # Прерываем выполнение хэндлера

    # Получаем текущие данные категории из БД
    # Важно загрузить родителя, если он есть, для отображения текущего значения
    # db.get_category_by_id должен позволять lazy loading parent
    category = db.get_category_by_id(category_id)
    if not category:
        logger.error(f"Категория с ID {category_id} не найдена для обновления.")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Категория не найдена для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Сбрасываем FSM перед началом нового диалога (если не был сброшен ранее)
    await state.clear() # Сброс в начале FSM диалога обновления

    # Сохраняем текущие данные и ID в контексте FSM
    await state.update_data(
        updating_category_id=category.id,
        original_name=category.name,
        original_parent_id=category.parent_id,
        original_parent_name=category.parent.name if category.parent else "Нет"
    )

    # Переходим к первому шагу: запрос нового названия
    await state.set_state(CategoryUpdateFSM.waiting_for_name)
    # Редактируем сообщение, откуда пришел колбэк (детали)
    # Экранируем текущее название для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(category.name)

    await _send_or_edit_message(
        callback_query,
        f"📝 **Обновление Категории** (ID: `{category.id}`)\n\n"
        f"Текущее название: `{original_name_esc}`\n\n"
        f"Введите новое название категории или пропустите, отправив `{SKIP_INPUT_MARKER}`.",
        parse_mode="MarkdownV2"
    )

async def process_category_name_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое название категории (UPDATE FSM)."""
    user_data = await state.get_data()
    original_name = user_data.get("original_name")
    new_name = message.text.strip()

    if new_name == SKIP_INPUT_MARKER:
        new_name = original_name # Пропускаем - оставляем старое значение
        # Экранируем оригинальное название для MarkdownV2
        original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
        await message.answer(f"Название оставлено без изменений: `{original_name_esc}`.", parse_mode="MarkdownV2")
    elif not new_name:
         await message.answer("Название категории не может быть пустым. Введите новое название, отправьте `-` для пропуска или 'Отмена'.")
         # Остаемся в текущем состоянии
         return
    else:
        # Экранируем новое название для MarkdownV2
        new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
        await message.answer(f"Новое название: `{new_name_esc}`", parse_mode="MarkdownV2")


    # Сохраняем новое название (или старое, если пропущено)
    await state.update_data(new_name=new_name)


    # Переходим к следующему шагу: решение по родительской категории
    keyboard = [
        [types.InlineKeyboardButton(text="✅ Изменить / Удалить", callback_data="update_cat_parent_decision_yes")], # Уникальный колбэк
        [types.InlineKeyboardButton(text="🚫 Оставить текущую", callback_data=KEEP_CURRENT_PARENT_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await state.set_state(CategoryUpdateFSM.waiting_for_parent_decision)
    # Отправляем новое сообщение для следующего шага FSM
    # Экранируем текущее имя родителя для MarkdownV2
    original_parent_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get('original_parent_name', 'Нет'))
    await message.answer(
        f"Текущая родительская категория: `{original_parent_name_esc}`\n\n"
        "Хотите изменить родительскую категорию?",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )


async def process_parent_update_decision(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает решение об обновлении родительской категории (UPDATE FSM)."""
    await callback_query.answer()
    decision = callback_query.data
    user_data = await state.get_data()
    updating_category_id = user_data.get("updating_category_id")

    if decision == KEEP_CURRENT_PARENT_CALLBACK:
        # Оставляем текущую родительскую категорию
        # new_parent_id уже None или original_parent_id, если не был изменен
        await state.update_data(
            new_parent_id=user_data.get("original_parent_id"),
            new_parent_name=user_data.get("original_parent_name")
        )
        await show_category_update_confirm(callback_query, state) # Переходим к подтверждению
    elif decision == "update_cat_parent_decision_yes": # Нажата "Изменить / Удалить"
        # Предлагаем выбрать новую или удалить
        all_categories = db.get_all_categories()
        # TODO: Фильтровать текущую категорию и ее детей из списка выбора, чтобы избежать циклов.
        # Пока фильтруем только саму категорию из списка доступных для выбора родителем.
        # В реальной иерархии может потребоваться более сложная логика фильтрации.
        available_categories = [c for c in all_categories if c.id != updating_category_id]

        # Кнопки для удаления родителя и отмены
        extra_buttons = [
            [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")], # Уникальный колбэк
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]

        if available_categories:
            # Храним список категорий и текущую страницу в контексте для пагинации
            await state.update_data(available_parent_categories_update=available_categories, parent_page_update=0)

            await state.set_state(CategoryUpdateFSM.waiting_for_parent_selection)
            # Отправляем/редактируем сообщение для показа списка
            await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons) # Передаем target и state
        else:
             # Нет других категорий для выбора, кроме самой себя (которую исключили)
             await state.update_data(new_parent_id=None, new_parent_name="Нет (нет доступных категорий)")
             await callback_query.message.edit_text(
                "ℹ️ В системе нет других категорий для выбора в качестве родительской, кроме текущей.\n"
                "Категория будет добавлена без родителя." # Убрал "Вы можете либо удалить...", т.к. кнопки удаления нет на этом шаге
             )
             # Переходим к подтверждению
             await show_category_update_confirm(callback_query, state)

    elif decision == "update_cat_remove_parent": # Обработка уникального колбэка "Удалить родительскую" (приходит из waiting_for_parent_selection или waiting_for_parent_decision)
         # Удаляем родительскую категорию
         await state.update_data(new_parent_id=None, new_parent_name="Нет")
         await show_category_update_confirm(callback_query, state) # Переходим к подтверждению
    else:
        await callback_query.message.answer("Неизвестное решение. Выберите опцию с клавиатуры.")
        # Остаемся в текущем состоянии, можно повторно отправить сообщение с кнопками решения
        user_data = await state.get_data()
        keyboard = [
            [types.InlineKeyboardButton(text="✅ Изменить / Удалить", callback_data="update_cat_parent_decision_yes")],
            [types.InlineKeyboardButton(text="🚫 Оставить текущую", callback_data=KEEP_CURRENT_PARENT_CALLBACK)],
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        # Экранируем имя родителя
        original_parent_name_esc = types.utils.markdown.text_decorations.escape_markdown(user_data.get('original_parent_name', 'Нет'))
        await callback_query.message.edit_text(
             f"Текущая родительская категория: `{original_parent_name_esc}`\n\n"
             "Хотите изменить родительскую категорию?\n*Пожалуйста, используйте кнопки.*",
             reply_markup=reply_markup,
             parse_mode="MarkdownV2"
        )


async def show_parent_category_update_selection(target: Union[types.Message, types.CallbackQuery], state: FSMContext, extra_buttons: Optional[List[List[types.InlineKeyboardButton]]] = None):
    """Показывает список категорий для выбора новой родительской с пагинацией (UPDATE FSM)."""
    user_data = await state.get_data()
    # Получаем актуальный список категорий из state (обновляется в process_parent_category_update_pagination)
    categories = user_data.get("available_parent_categories_update", [])
    current_page = user_data.get("parent_page_update", 0)

    if not categories:
         # Этот случай должен быть обработан до вызова этой функции, но для надежности
         text = "ℹ️ Нет доступных категорий для выбора."
         # Кнопка "Продолжить" (без родителя)
         keyboard = [[types.InlineKeyboardButton(text="✅ Продолжить без родителя", callback_data="update_cat_continue_no_parent")]] # Уникальный колбэк
         # Добавляем кнопки удаления родителя и отмены, если они были переданы
         if extra_buttons:
              keyboard.extend(extra_buttons)
         reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

         # Перейти в состояние подтверждения с parent_id=None?
         await state.update_data(new_parent_id=None, new_parent_name="Нет (нет доступных категорий)")
         await state.set_state(CategoryUpdateFSM.confirm_update) # Переходим к подтверждению

         await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")
         return

    # Helper function to format item text for the button
    def format_category_button_text(category: db.Category) -> str:
         # Экранируем имя категории
         return f"📂 {types.utils.markdown.text_decorations.escape_markdown(category.name)}"

    reply_markup = generate_pagination_keyboard(
        items=categories,
        current_page=current_page,
        page_size=CATEGORY_PAGE_SIZE_UPDATE,
        select_callback_prefix=UPDATE_CAT_PARENT_SEL_PREFIX,
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_CAT_PARENT_PAGE_PREFIX.strip(':')}:",
        item_text_func=format_category_button_text,
        item_id_func=lambda c: c.id,
        extra_buttons=extra_buttons, # Передаем кнопки "Удалить родительскую" и "Отмена"
        cancel_callback=CANCEL_FSM_CALLBACK # Указываем колбэк отмены
    )

    text = f"Выберите новую родительскую категорию (страница {current_page + 1}):"

    await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")


async def process_parent_category_update_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор новой родительской категории (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: {prefix}{id} -> "upd_cat_par_sel:123"
    try:
        action, category_id_str = data.split(":")
        category_id = int(category_id_str)
        # Проверка, что callback data соответствует префиксу выбора родительской категории
        if not data.startswith(UPDATE_CAT_PARENT_SEL_PREFIX):
            raise ValueError("Invalid callback prefix")
    except ValueError:
        logger.error(f"Некорректный формат callback_data для выбора родительской категории в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе категории.")
        # Показать список заново с кнопками удаления/отмены
        extra_buttons = [
             [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")],
             [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons)
        return


    selected_category = db.get_category_by_id(category_id)
    if not selected_category:
        await callback_query.message.answer("Выбранная категория не найдена. Попробуйте еще раз.")
        extra_buttons = [
             [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")],
             [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons) # Показать список заново
        return

    await state.update_data(new_parent_id=category_id, new_parent_name=selected_category.name)
    # Экранируем имя категории
    selected_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(selected_category.name)
    await callback_query.message.edit_text(f"Выбрана новая родительская категория: `{selected_category_name_esc}`.", parse_mode="MarkdownV2")

    # Переходим к подтверждению
    await show_category_update_confirm(callback_query, state)


async def process_parent_category_update_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора родительской категории (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:upd_cat_par:{page_number}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != UPDATE_CAT_PARENT_PAGE_PREFIX.strip(':'):
        logger.error(f"Некорректный формат callback_data для пагинации родителя категории в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        # Показать текущий список снова
        extra_buttons = [
             [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")],
             [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons)
        return

    try:
        new_page = int(parts[2])
    except ValueError:
        logger.error(f"Некорректный номер страницы в callback_data для пагинации родителя категории в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации (некорректный номер страницы).")
        # Показываем текущий список снова
        extra_buttons = [
             [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")],
             [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons)
        return


    user_data = await state.get_data()
    # Получаем актуальный список категорий из БД на этом шаге, чтобы обновить state.available_parent_categories_update
    all_categories = db.get_all_categories()
    updating_category_id = user_data.get("updating_category_id")
    categories = [c for c in all_categories if c.id != updating_category_id] # Фильтруем текущую

    total_pages = math.ceil(len(categories) / CATEGORY_PAGE_SIZE_UPDATE)

    if 0 <= new_page < total_pages:
        await state.update_data(available_parent_categories_update=categories, parent_page_update=new_page) # Обновляем список и страницу
        extra_buttons = [
             [types.InlineKeyboardButton(text="🚫 Удалить родительскую", callback_data="update_cat_remove_parent")],
             [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
        ]
        await show_parent_category_update_selection(callback_query, state, extra_buttons=extra_buttons)
    else:
        await callback_query.answer("Некорректный номер страницы.")


async def show_category_update_confirm(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает данные для подтверждения обновления категории (UPDATE FSM)."""
    user_data = await state.get_data()
    category_id = user_data.get("updating_category_id")
    original_name = user_data.get("original_name")
    original_parent_name = user_data.get("original_parent_name", "Нет")

    new_name = user_data.get("new_name") # Получено из FSM state
    new_parent_name = user_data.get("new_parent_name", "Нет") # Получено из FSM state


    text = f"✨ **Подтверждение обновления Категории** (ID: `{category_id}`) ✨\n\n"

    # Показываем изменения, экранируя для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
    new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
    if new_name != original_name:
        text += f"**Название:** ~~`{original_name_esc}`~~ → `{new_name_esc}`\n"
    else:
        text += f"**Название:** `{original_name_esc}` (без изменений)\n"

    original_parent_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_parent_name)
    new_parent_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_parent_name)
    if new_parent_name != original_parent_name:
        text += f"**Родительская категория:** ~~`{original_parent_name_esc}`~~ → `{new_parent_name_esc}`\n"
    else:
        text += f"**Родительская категория:** `{original_parent_name_esc}` (без изменений)\n"


    text += "\nВсе верно? Подтвердите или отмените."

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить обновление", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")

    await state.set_state(CategoryUpdateFSM.confirm_update)


async def process_category_update_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение обновления категории (UPDATE FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    category_id = user_data.get("updating_category_id")
    new_name = user_data.get("new_name")
    new_parent_id = user_data.get("new_parent_id") # Получено из FSM state

    # Формируем словарь с данными для обновления
    update_data = {
        "name": new_name,
        "parent_id": new_parent_id
    }

    # Вызываем функцию обновления из utils/db.py
    updated_category = db.update_category(category_id, update_data)

    if updated_category:
        # Получаем имя родителя для результата
        updated_parent_name = updated_category.parent.name if updated_category.parent else 'Нет'
        # Экранируем имена для MarkdownV2
        updated_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_category.name)
        updated_parent_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_parent_name)

        await callback_query.message.edit_text(
            f"🎉 **Категория (ID: `{category_id}`) успешно обновлена!** 🎉"
            f"\nНовое название: `{updated_name_esc}`"
            f"\nНовая родительская категория: `{updated_parent_name_esc}`",
            parse_mode="MarkdownV2"
        )
    else:
        # TODO: Добавить более конкретную ошибку из db.update_category, если возможно (IntegrityError)
        await callback_query.message.edit_text(
            f"❌ **Ошибка при обновлении категории (ID: `{category_id}`).**\n"
            "Возможно, категория с таким названием уже существует или произошла другая ошибка."
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)

# Примечание: Отдельный хэндлер cancel_update_category не нужен,
# если используется общий cancel_fsm_handler, зарегистрированный на State("*")


# --- Router Registration ---
# Создаем роутер специально для FSM обновления категории
category_update_fsm_router = Router(name="category_update_fsm_router")

def register_category_update_handlers(router: Router):
    """Регистрирует обработчики FSM обновления категории."""

    # ENTRY POINT: Запуск FSM по колбэку "Редактировать" из детального просмотра категории
    # Используем F.data.startswith для фильтрации по префиксу инициации обновления категории
    router.callback_query.register(
        start_category_update,
        F.data.startswith(CATEGORY_UPDATE_INIT_CALLBACK_PREFIX)
        # Без фильтра состояний, т.к. это вход в FSM
    )

    # Обработчики шагов FSM
    router.message.register(process_category_name_update, CategoryUpdateFSM.waiting_for_name)

    # Обработчик решения по родительской категории (кнопки "Изменить/Удалить", "Оставить текущую")
    router.callback_query.register(
        process_parent_update_decision,
        CategoryUpdateFSM.waiting_for_parent_decision,
        F.data.in_(["update_cat_parent_decision_yes", KEEP_CURRENT_PARENT_CALLBACK])
    )
    # Обработчик кнопки "Удалить родительскую" (может быть как на шаге решения, так и на шаге выбора)
    router.callback_query.register(
        process_parent_update_decision, # Повторно используем обработчик решения
        StateFilter(CategoryUpdateFSM.waiting_for_parent_decision, CategoryUpdateFSM.waiting_for_parent_selection),
        F.data == "update_cat_remove_parent"
    )
     # Обработчик кнопки "Продолжить без родителя" при отсутствии категорий для выбора
    router.callback_query.register(
         show_category_update_confirm, # Переходим сразу к подтверждению
         CategoryUpdateFSM.waiting_for_parent_selection,
         F.data == "update_cat_continue_no_parent"
    )

    # Хэндлеры выбора и пагинации родительской категории (ожидают колбэк с определенным состоянием и префиксом)
    router.callback_query.register(
        process_parent_category_update_selection,
        CategoryUpdateFSM.waiting_for_parent_selection,
        F.data.startswith(UPDATE_CAT_PARENT_SEL_PREFIX) # Выбор родительской категории
    )
    router.callback_query.register(
        process_parent_category_update_pagination,
        CategoryUpdateFSM.waiting_for_parent_selection,
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_CAT_PARENT_PAGE_PREFIX.strip(':')}:") # Пагинация списка родительских категорий
    )

    # Хэндлер подтверждения (ожидает колбэк с определенным состоянием и колбэком подтверждения)
    router.callback_query.register(
        process_category_update_confirm,
        CategoryUpdateFSM.confirm_update,
        F.data == CONFIRM_ACTION_CALLBACK
    )

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера
    # Например, на родительском admin_router или главном dp с фильтром State("*") и Text(CANCEL_FSM_CALLBACK).
    # router.callback_query.register(cancel_fsm_handler, Text(CANCEL_FSM_CALLBACK), State("*"))

# Вызываем функцию регистрации для этого роутера
register_category_update_handlers(category_update_fsm_router)

# Роутер category_update_fsm_router теперь содержит все обработчики и готов к включению в основной диспатчер/роутер.
