#!/usr/bin/env python
# -*- coding: utf-8 -*-

# your_bot/handlers/fsm/product_update_fsm.py
# FSM диалог для обновления существующего товара

import logging
import math
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from typing import Union, Optional, List
from decimal import Decimal # Используем Decimal для точной работы с деньгами

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
    PRODUCT_UPDATE_INIT_CALLBACK_PREFIX, UPDATE_PROD_CAT_PAGE_PREFIX,
    UPDATE_PROD_CAT_SEL_PREFIX, KEEP_CURRENT_CATEGORY_CALLBACK,
    UPDATE_PROD_MAN_PAGE_PREFIX, UPDATE_PROD_MAN_SEL_PREFIX,
    KEEP_CURRENT_MANUFACTURER_CALLBACK
)

# Импорт хелпера для отправки/редактирования сообщений из admin_list_detail_handlers_aiogram
# Импортируем здесь, чтобы избежать циклического импорта на уровне модуля при инициализации
# Функция show_admin_main_menu_aiogram будет импортироваться внутри хэндлеров, где она нужна,
# чтобы избежать циклического импорта на уровне модуля
from ..admin_list_detail_handlers_aiogram import _send_or_edit_message


# Настройка логирования
logger = logging.getLogger(__name__)


# Размер страницы для пагинации выбора категории/производителя
PRODUCT_SELECT_PAGE_SIZE_UPDATE = 10


# --- FSM States ---
class ProductUpdateFSM(StatesGroup):
    """Состояния для диалога обновления товара."""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_category_selection = State()
    waiting_for_manufacturer_selection = State()
    confirm_update = State()

# --- Handlers ---
async def start_product_update(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает диалог обновления товара."""
    await callback_query.answer()

    # Парсим ID товара из callback_data
    try:
        # Ожидается формат callback_data: {префикс_инициации_обновления}{id}
        product_id_str = callback_query.data.replace(PRODUCT_UPDATE_INIT_CALLBACK_PREFIX, "")
        product_id = int(product_id_str)
    except ValueError:
        logger.error(f"Некорректный ID товара в колбэке обновления: {callback_query.data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Некорректный ID товара для обновления.")
        await state.clear()
        # Возвращаемся в главное меню (предполагается, что эта функция доступна из других хэндлеров)
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Получаем текущие данные товара из БД
    # Для отображения названий категории/производителя в подтверждении,
    # лучше получить объект товара с загруженными связями.
    # Существующая get_product_by_id возвращает Product объект, связи могут быть загружены при первом обращении (lazy loading).
    product = db.get_product_by_id(product_id)
    if not product:
        logger.error(f"Товар с ID {product_id} не найден для обновления.")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Товар не найден для обновления.")
        await state.clear()
        # Возвращаемся в главное меню
        from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    # Сбрасываем FSM перед началом нового диалога
    await state.clear()

    # Сохраняем текущие данные и ID в контексте FSM
    await state.update_data(
        updating_product_id=product.id,
        original_name=product.name,
        original_description=product.description,
        original_price=product.price, # SQLAlchemy возвращает Decimal для поля DECIMAL
        original_category_id=product.category_id,
        original_category_name=product.category.name if product.category else "Неизвестно",
        original_manufacturer_id=product.manufacturer_id,
        original_manufacturer_name=product.manufacturer.name if product.manufacturer else "Неизвестно"
    )

    # Переходим к первому шагу: запрос нового названия
    await state.set_state(ProductUpdateFSM.waiting_for_name)
    # Редактируем сообщение, откуда пришел колбэк (детали)
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(product.name)

    await _send_or_edit_message(
        callback_query,
        f"📝 **Обновление Товара** (ID: `{product.id}`)\n\n"
        f"Текущее название: `{original_name_esc}`\n\n"
        f"Введите новое название товара или пропустите, отправив `{SKIP_INPUT_MARKER}`."
        f"\n*Для отмены в любой момент нажмите 'Отмена' или отправьте /cancel*", # Добавляем подсказку про отмену
        parse_mode="MarkdownV2"
    )

async def process_product_name_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое название товара (UPDATE FSM)."""
    user_data = await state.get_data()
    original_name = user_data.get("original_name")
    new_name = message.text.strip()

    if new_name == SKIP_INPUT_MARKER:
        new_name = original_name # Пропускаем - оставляем старое значение
        original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
        await message.answer(f"Название оставлено без изменений: `{original_name_esc}`.", parse_mode="MarkdownV2")
    elif not new_name:
         await message.answer("Название товара не может быть пустым. Введите новое название, отправьте `-` для пропуска или /cancel.")
         # Остаемся в текущем состоянии
         return
    else:
        new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
        await message.answer(f"Новое название: `{new_name_esc}`", parse_mode="MarkdownV2")

    await state.update_data(new_name=new_name)

    # Переходим к описанию
    await state.set_state(ProductUpdateFSM.waiting_for_description)
    original_description = user_data.get('original_description') or 'Нет'
    original_description_esc = types.utils.markdown.text_decorations.escape_markdown(original_description)

    await message.answer(
        f"Текущее описание: `{original_description_esc}`\n\n"
        f"Введите новое описание товара или пропустите, отправив `{SKIP_INPUT_MARKER}`."
        f"\n*Для отмены в любой момент нажмите 'Отмена' или отправьте /cancel*",
        parse_mode="MarkdownV2"
    )


async def process_product_description_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенное новое описание товара (UPDATE FSM)."""
    user_data = await state.get_data()
    original_description = user_data.get("original_description")
    new_description = message.text.strip()

    if new_description == SKIP_INPUT_MARKER:
        new_description = original_description # Пропускаем
        original_description_esc = types.utils.markdown.text_decorations.escape_markdown(original_description or 'Нет')
        await message.answer(f"Описание оставлено без изменений: `{original_description_esc}`.", parse_mode="MarkdownV2")
    elif not new_description: # Пустое сообщение тоже можно считать сбросом описания
        new_description = None
        await message.answer("Описание сброшено (установлено в Нет).")
    else:
        new_description_esc = types.utils.markdown.text_decorations.escape_markdown(new_description)
        await message.answer(f"Новое описание: `{new_description_esc}`", parse_mode="MarkdownV2")

    await state.update_data(new_description=new_description)

    # Переходим к цене
    await state.set_state(ProductUpdateFSM.waiting_for_price)
    original_price = user_data.get('original_price', Decimal(0))
    original_price_esc = types.utils.markdown.text_decorations.escape_markdown(f'{original_price:.2f}')

    await message.answer(
        f"Текущая цена: `{original_price_esc}` руб.\n\n"
        f"Введите новую цену товара (например, `123` или `123.45`) или пропустите, отправив `{SKIP_INPUT_MARKER}`."
        f"\n*Для отмены в любой момент нажмите 'Отмена' или отправьте /cancel*",
        parse_mode="MarkdownV2"
    )


async def process_product_price_update(message: types.Message, state: FSMContext):
    """Обрабатывает введенную новую цену товара (UPDATE FSM)."""
    user_data = await state.get_data()
    original_price = user_data.get("original_price") # Это Decimal из state
    price_str = message.text.strip()

    if price_str == SKIP_INPUT_MARKER:
        new_price = original_price # Пропускаем
        await state.update_data(new_price=new_price)
        original_price_esc = types.utils.markdown.text_decorations.escape_markdown(f'{original_price:.2f}')
        await message.answer(f"Цена оставлена без изменений: `{original_price_esc}` руб.", parse_mode="MarkdownV2")
        # Переходим к выбору категории
        await state.set_state(ProductUpdateFSM.waiting_for_category_selection)
        await show_product_category_update_selection(message, state)
    else:
        try:
            # Пытаемся преобразовать в Decimal
            # Заменяем запятую на точку для парсинга, если пользователь ввел 123,45
            new_price = Decimal(price_str.replace(',', '.'))
            if new_price < 0:
                await message.answer("Цена не может быть отрицательной. Введите корректную цену, отправьте `-` для пропуска или /cancel.")
                # Остаемся в текущем состоянии
                return
            # Округляем до 2 знаков после запятой для соответствия DECIMAL(10, 2)
            new_price = new_price.quantize(Decimal('0.01'))
            await state.update_data(new_price=new_price)
            new_price_esc = types.utils.markdown.text_decorations.escape_markdown(f'{new_price:.2f}')
            await message.answer(f"Новая цена: `{new_price_esc}` руб.", parse_mode="MarkdownV2")

            # Переходим к выбору категории
            await state.set_state(ProductUpdateFSM.waiting_for_category_selection)
            await show_product_category_update_selection(message, state)

        except ValueError:
            await message.answer("Некорректный формат цены. Введите число (например, `123` или `123.45`), отправьте `-` для пропуска или /cancel.")
            # Остаемся в текущем состоянии
            return


async def show_product_category_update_selection(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список категорий для выбора новой категории товара с пагинацией (UPDATE FSM)."""
    user_data = await state.get_data()
    # Получаем актуальный список категорий из БД на этом шаге
    all_categories = db.get_all_categories()
    categories = all_categories # Пока не фильтруем

    # Получаем текущую страницу из state, по умолчанию 0
    current_page = user_data.get("category_page_update", 0)

    original_category_name = user_data.get("original_category_name", "Неизвестно")
    original_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_category_name)

    if not categories:
        # Невозможно выбрать категорию, если их нет.
        # Сохраняем текущую категорию как новую, если список пуст (если она была).
        # Если текущей не было (что маловероятно для существующего товара с category_id NOT NULL),
        # это может быть проблемная ситуация. Пока просто сохраняем текущее состояние и переходим дальше.
        # В реальной системе нужно проверить, что original_category_id не None.
        await state.update_data(
            new_category_id=user_data.get("original_category_id"),
            new_category_name=user_data.get("original_category_name")
        )
        text = f"ℹ️ В системе нет доступных категорий для выбора.\nКатегория товара оставлена без изменений: `{original_category_name_esc}`."
        await _send_or_edit_message(target, text, parse_mode="MarkdownV2")

        # Переходим сразу к выбору производителя
        await state.set_state(ProductUpdateFSM.waiting_for_manufacturer_selection)
        # Вызываем функцию показа выбора производителя
        all_manufacturers = db.get_all_manufacturers()
        await state.update_data(available_manufacturers_update=all_manufacturers, manufacturer_page_update=0)
        await show_product_manufacturer_update_selection(target, state)
        return

    # Сохраняем актуальный список категорий и текущую страницу в контексте для пагинации
    await state.update_data(available_categories_update=categories, category_page_update=current_page)


    # Добавляем кнопку "Оставить текущую" и "Отмена"
    extra_buttons = [
        [types.InlineKeyboardButton(text=f"📦 Оставить текущую (`{original_category_name_esc}`)", callback_data=KEEP_CURRENT_CATEGORY_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]

    def format_category_button_text(category: db.Category) -> str:
         return f"📂 {types.utils.markdown.text_decorations.escape_markdown(category.name)}"

    reply_markup = generate_pagination_keyboard(
        items=categories,
        current_page=current_page,
        page_size=PRODUCT_SELECT_PAGE_SIZE_UPDATE,
        select_callback_prefix=UPDATE_PROD_CAT_SEL_PREFIX,
        # Формат pagination_callback_prefix должен включать ":" в конце, как в fsm_utils
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_PROD_CAT_PAGE_PREFIX.strip(':')}:",
        item_text_func=format_category_button_text,
        item_id_func=lambda c: c.id,
        extra_buttons=extra_buttons,
        cancel_callback=CANCEL_FSM_CALLBACK # Передаем колбэк отмены
    )

    text = f"Текущая категория: `{original_category_name_esc}`\nВыберите новую категорию для товара (страница {current_page + 1}):"

    await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")


async def process_product_category_update_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор новой категории для товара или нажатие "Оставить текущую" (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
    user_data = await state.get_data()

    if data == KEEP_CURRENT_CATEGORY_CALLBACK:
        # Пользователь решил оставить текущую категорию
        await state.update_data(
            new_category_id=user_data.get("original_category_id"),
            new_category_name=user_data.get("original_category_name")
        )
        original_category_name = user_data.get('original_category_name', 'Неизвестно')
        original_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_category_name)
        await callback_query.message.edit_text(f"Категория оставлена без изменений: `{original_category_name_esc}`.", parse_mode="MarkdownV2")

        # Переходим к выбору производителя
        await state.set_state(ProductUpdateFSM.waiting_for_manufacturer_selection)
        # Получаем список производителей
        all_manufacturers = db.get_all_manufacturers()
        await state.update_data(available_manufacturers_update=all_manufacturers, manufacturer_page_update=0)
        await show_product_manufacturer_update_selection(callback_query, state)
        return

    # Если это не "Оставить текущую", парсим ID категории
    try:
        # Ожидается формат: {prefix}{id} -> "upd_prod_cat_sel:123"
        prefix, category_id_str = data.split(":")
        category_id = int(category_id_str)
        # Проверка, что callback data соответствует префиксу выбора категории
        if f"{prefix}:" != UPDATE_PROD_CAT_SEL_PREFIX:
            raise ValueError("Invalid callback prefix")
    except ValueError:
        logger.error(f"Некорректный формат callback_data для выбора категории товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе категории.")
        # Показать список заново
        await show_product_category_update_selection(callback_query, state)
        return


    selected_category = db.get_category_by_id(category_id)
    if not selected_category:
        await callback_query.message.answer("Выбранная категория не найдена. Попробуйте еще раз.")
        await show_product_category_update_selection(callback_query, state) # Показать список заново
        return

    await state.update_data(new_category_id=category_id, new_category_name=selected_category.name)
    selected_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(selected_category.name)
    await callback_query.message.edit_text(f"Выбрана новая категория: `{selected_category_name_esc}`.", parse_mode="MarkdownV2")


    # Переходим к выбору производителя
    await state.set_state(ProductUpdateFSM.waiting_for_manufacturer_selection)
    # Получаем список производителей
    all_manufacturers = db.get_all_manufacturers()
    await state.update_data(available_manufacturers_update=all_manufacturers, manufacturer_page_update=0)
    await show_product_manufacturer_update_selection(callback_query, state)


async def process_product_category_update_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора категории (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
    # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:upd_prod_cat:{page_number}"
    parts = data.split(":")
    # parts[0] == 'page', parts[1] == entity_prefix, parts[2] == page_number
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != UPDATE_PROD_CAT_PAGE_PREFIX.strip(':'):
        logger.error(f"Некорректный формат callback_data для пагинации категории товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_product_category_update_selection(callback_query, state) # Показать список заново
        return

    try:
        new_page = int(parts[2])
    except ValueError:
        logger.error(f"Некорректный номер страницы в callback_data для пагинации категории товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации (некорректный номер страницы).")
        await show_product_category_update_selection(callback_query, state) # Показать список заново
        return

    user_data = await state.get_data()
    # Получаем актуальный список категорий из БД на этом шаге (или из state, если не нужно обновлять)
    # Если список большой и может меняться, лучше получать из БД. Если маленький - из state.
    # Для консистентности с generate_pagination_keyboard, которая работает со списком из items,
    # лучше обновить список в state перед вызовом show_product_category_update_selection.
    all_categories = db.get_all_categories()
    categories = all_categories # Пока не фильтруем
    await state.update_data(available_categories_update=categories, category_page_update=new_page) # Обновляем список и страницу

    total_pages = math.ceil(len(categories) / PRODUCT_SELECT_PAGE_SIZE_UPDATE)

    # Проверяем, что запрошенная страница корректна после получения актуального списка
    if new_page < 0 or new_page >= total_pages:
         logger.warning(f"Запрошена некорректная страница {new_page} (всего страниц {total_pages}) для пагинации категории товара в update FSM.")
         # Можно просто показать текущую страницу (0 или последнюю)
         new_page = max(0, min(new_page, total_pages - 1 if total_pages > 0 else 0))
         await state.update_data(category_page_update=new_page)
         await callback_query.answer("Некорректный номер страницы.") # Ответ на колбэк
         # Продолжаем показывать список, но с исправленным номером страницы
         # НЕ return, чтобы show_product_category_update_selection был вызван
         # Pass callback_query as target
         await show_product_category_update_selection(callback_query, state)
    else:
        # Страница корректна, показываем список на новой странице
        await show_product_category_update_selection(callback_query, state)


async def show_product_manufacturer_update_selection(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает список производителей для выбора нового производителя товара с пагинацией (UPDATE FSM)."""
    user_data = await state.get_data()
    # Получаем актуальный список производителей из БД на этом шаге
    all_manufacturers = db.get_all_manufacturers()
    manufacturers = all_manufacturers # Пока не фильтруем

    # Получаем текущую страницу из state, по умолчанию 0
    current_page = user_data.get("manufacturer_page_update", 0)

    original_manufacturer_name = user_data.get("original_manufacturer_name", "Неизвестно")
    original_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_manufacturer_name)


    if not manufacturers:
        # Невозможно выбрать производителя. Сохраняем текущего, если он был.
        # В реальной системе нужно проверить, что original_manufacturer_id не None.
        await state.update_data(
            new_manufacturer_id=user_data.get("original_manufacturer_id"),
            new_manufacturer_name=user_data.get("original_manufacturer_name")
        )
        text = f"ℹ️ В системе нет доступных производителей для выбора.\nПроизводитель товара оставлен без изменений: `{original_manufacturer_name_esc}`."
        await _send_or_edit_message(target, text, parse_mode="MarkdownV2")

        # Переходим к подтверждению
        await show_product_update_confirm(target, state)
        return

    # Сохраняем актуальный список производителей и текущую страницу в контексте для пагинации
    await state.update_data(available_manufacturers_update=manufacturers, manufacturer_page_update=current_page)


    # Добавляем кнопку "Оставить текущего" и "Отмена"
    extra_buttons = [
        [types.InlineKeyboardButton(text=f"🏭 Оставить текущего (`{original_manufacturer_name_esc}`)", callback_data=KEEP_CURRENT_MANUFACTURER_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]

    def format_manufacturer_button_text(manufacturer: db.Manufacturer) -> str:
        return f"🏭 {types.utils.markdown.text_decorations.escape_markdown(manufacturer.name)}"


    reply_markup = generate_pagination_keyboard(
        items=manufacturers,
        current_page=current_page,
        page_size=PRODUCT_SELECT_PAGE_SIZE_UPDATE,
        select_callback_prefix=UPDATE_PROD_MAN_SEL_PREFIX,
        # Формат pagination_callback_prefix должен включать ":" в конце
        pagination_callback_prefix=f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_PROD_MAN_PAGE_PREFIX.strip(':')}:",
        item_text_func=format_manufacturer_button_text,
        item_id_func=lambda m: m.id,
        extra_buttons=extra_buttons,
        cancel_callback=CANCEL_FSM_CALLBACK # Передаем колбэк отмены
    )

    text = f"Текущий производитель: `{original_manufacturer_name_esc}`\nВыберите нового производителя для товара (страница {current_page + 1}):"

    await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")


async def process_product_manufacturer_update_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор нового производителя для товара или нажатие "Оставить текущего" (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
    user_data = await state.get_data()

    if data == KEEP_CURRENT_MANUFACTURER_CALLBACK:
        # Пользователь решил оставить текущего производителя
        await state.update_data(
            new_manufacturer_id=user_data.get("original_manufacturer_id"),
            new_manufacturer_name=user_data.get("original_manufacturer_name")
        )
        original_manufacturer_name = user_data.get('original_manufacturer_name', 'Неизвестно')
        original_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_manufacturer_name)
        await callback_query.message.edit_text(f"Производитель оставлен без изменений: `{original_manufacturer_name_esc}`.", parse_mode="MarkdownV2")

        # Переходим к подтверждению
        await show_product_update_confirm(callback_query, state)
        return

    # Если это не "Оставить текущего", парсим ID производителя
    try:
        # Ожидается формат: {prefix}{id} -> "upd_prod_man_sel:123"
        prefix, manufacturer_id_str = data.split(":")
        manufacturer_id = int(manufacturer_id_str)
        # Проверка, что callback data соответствует префиксу выбора производителя
        if f"{prefix}:" != UPDATE_PROD_MAN_SEL_PREFIX:
             raise ValueError("Invalid callback prefix")
    except ValueError:
        logger.error(f"Некорректный формат callback_data для выбора производителя товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка при выборе производителя.")
        await show_product_manufacturer_update_selection(callback_query, state) # Показать список заново
        return


    selected_manufacturer = db.get_manufacturer_by_id(manufacturer_id)
    if not selected_manufacturer:
        await callback_query.message.answer("Выбранный производитель не найден. Попробуйте еще раз.")
        await show_product_manufacturer_update_selection(callback_query, state) # Показать список заново
        return

    await state.update_data(new_manufacturer_id=manufacturer_id, new_manufacturer_name=selected_manufacturer.name)
    selected_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(selected_manufacturer.name)
    await callback_query.message.edit_text(f"Выбран новый производитель: `{selected_manufacturer_name_esc}`.", parse_mode="MarkdownV2")

    # Переходим к подтверждению
    await show_product_update_confirm(callback_query, state)


async def process_product_manufacturer_update_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатия кнопок пагинации для выбора производителя (UPDATE FSM)."""
    await callback_query.answer()
    data = callback_query.data
     # Ожидаем формат: "page:{entity_prefix}:{page_number}" -> "page:upd_prod_man:{page_number}"
    parts = data.split(":")
    # parts[0] == 'page', parts[1] == entity_prefix, parts[2] == page_number
    if len(parts) != 3 or parts[0] != PAGINATION_CALLBACK_PREFIX.strip(':') or parts[1] != UPDATE_PROD_MAN_PAGE_PREFIX.strip(':'):
        logger.error(f"Некорректный формат callback_data для пагинации производителя товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации.")
        await show_product_manufacturer_update_selection(callback_query, state) # Показать текущий список заново
        return

    try:
        new_page = int(parts[2])
    except ValueError:
        logger.error(f"Некорректный номер страницы в callback_data для пагинации производителя товара в update FSM: {data}")
        await callback_query.message.answer("Произошла ошибка пагинации (некорректный номер страницы).")
        await show_product_manufacturer_update_selection(callback_query, state) # Показать текущий список заново
        return


    user_data = await state.get_data()
    # Получаем актуальный список производителей из БД на этом шаге
    all_manufacturers = db.get_all_manufacturers()
    manufacturers = all_manufacturers # Пока не фильтруем
    await state.update_data(available_manufacturers_update=manufacturers, manufacturer_page_update=new_page) # Обновляем список и страницу

    total_pages = math.ceil(len(manufacturers) / PRODUCT_SELECT_PAGE_SIZE_UPDATE)

    # Проверяем, что запрошенная страница корректна после получения актуального списка
    if new_page < 0 or new_page >= total_pages:
         logger.warning(f"Запрошена некорректная страница {new_page} (всего страниц {total_pages}) для пагинации производителя товара в update FSM.")
         # Можно просто показать текущую страницу (0 или последнюю)
         new_page = max(0, min(new_page, total_pages - 1 if total_pages > 0 else 0))
         await state.update_data(manufacturer_page_update=new_page)
         await callback_query.answer("Некорректный номер страницы.") # Ответ на колбэк
         # Продолжаем показывать список, но с исправленным номером страницы
         # НЕ return, чтобы show_product_manufacturer_update_selection был вызван
         # Pass callback_query as target
         await show_product_manufacturer_update_selection(callback_query, state)
    else:
        # Страница корректна, показываем список на новой странице
        await show_product_manufacturer_update_selection(callback_query, state)


async def show_product_update_confirm(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """Показывает данные для подтверждения обновления товара (UPDATE FSM)."""
    user_data = await state.get_data()
    product_id = user_data.get("updating_product_id")

    original_name = user_data.get("original_name")
    original_description = user_data.get("original_description")
    original_price = user_data.get("original_price") # Decimal
    original_category_name = user_data.get("original_category_name", "Неизвестно")
    original_manufacturer_name = user_data.get("original_manufacturer_name", "Неизвестно")

    new_name = user_data.get("new_name") # Получено из FSM state
    new_description = user_data.get("new_description") # Получено из FSM state
    new_price = user_data.get("new_price") # Получено из FSM state (Decimal)
    new_category_name = user_data.get("new_category_name", "Неизвестно") # Получено из FSM state
    new_manufacturer_name = user_data.get("new_manufacturer_name", "Неизвестно") # Получено из FSM state


    text = f"✨ **Подтверждение обновления Товара** (ID: `{product_id}`) ✨\n\n"

    # Показываем изменения по каждому полю, экранируя для MarkdownV2
    original_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_name)
    new_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_name)
    if new_name != original_name:
        text += f"**Название:** ~~`{original_name_esc}`~~ → `{new_name_esc}`\n"
    else:
        # Показываем новое значение, даже если оно не изменилось, т.к. оно уже сохранено в state как "новое"
        text += f"**Название:** `{new_name_esc}` (без изменений)\n"


    # Специальная логика для описания, учитывая None
    original_description_esc = types.utils.markdown.text_decorations.escape_markdown(original_description or 'Нет')
    new_description_esc = types.utils.markdown.text_decorations.escape_markdown(new_description or 'Нет')
    if (original_description is None or original_description == "") and (new_description is None or new_description == ""):
        text += "**Описание:** Нет (без изменений)\n"
    elif original_description != new_description:
         # Оригинальное описание могло быть None или пустой строкой
         old_desc_display = f"`{original_description_esc}`" if original_description else "~~(Нет)~~"
         # Новое описание могло стать None или пустой строкой
         new_desc_display = f"`{new_description_esc}`" if new_description else "Нет"
         text += f"**Описание:** {old_desc_display} → {new_desc_display}\n"
    else:
        # Показываем новое/текущее описание, даже если оно не изменилось
        text += f"**Описание:** `{new_description_esc}` (без изменений)\n"


    # Специальная логика для цены, учитывая формат Decimal
    # Убедимся, что original_price и new_price являются Decimal перед форматированием
    # Добавляем обработку None для original_price (хотя для существующего товара оно не должно быть None)
    original_price_formatted = f'{original_price:.2f}' if original_price is not None else 'Нет'
    new_price_formatted = f'{new_price:.2f}' if new_price is not None else 'Нет'

    original_price_esc = types.utils.markdown.text_decorations.escape_markdown(original_price_formatted)
    new_price_esc = types.utils.markdown.text_decorations.escape_markdown(new_price_formatted)

    # Сравниваем как Decimal для точности, учитывая возможное None
    # Если одно из значений None, считаем, что изменение есть (это маловероятно для цены существующего товара)
    if original_price is None or new_price is None or original_price != new_price: # Сравнение Decimal работает корректно
         text += f"**Цена:** ~~`{original_price_esc}`~~ → `{new_price_esc}` руб.\n"
    else:
         # Показываем новое/текущее значение, даже если оно не изменилось
         text += f"**Цена:** `{new_price_esc}` руб. (без изменений)\n"

    original_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_category_name)
    new_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_category_name)
    # Сравниваем ID, чтобы понять, была ли выбрана новая категория
    if user_data.get("new_category_id") != user_data.get("original_category_id"):
        text += f"**Категория:** ~~`{original_category_name_esc}`~~ → `{new_category_name_esc}`\n"
    else:
        # Показываем новое/текущее значение, даже если оно не изменилось
        text += f"**Категория:** `{new_category_name_esc}` (без изменений)\n"

    original_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(original_manufacturer_name)
    new_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(new_manufacturer_name)
    # Сравниваем ID, чтобы понять, был ли выбран новый производитель
    if user_data.get("new_manufacturer_id") != user_data.get("original_manufacturer_id"):
        text += f"**Производитель:** ~~`{original_manufacturer_name_esc}`~~ → `{new_manufacturer_name_esc}`\n"
    else:
        # Показываем новое/текущее значение, даже если оно не изменилось
        text += f"**Производитель:** `{new_manufacturer_name_esc}` (без изменений)\n"

    text += "\nВсе верно? Подтвердите или отмените."
    # Подсказка про отмену кнопкой "Отмена" уже есть в клавиатуре

    keyboard = [
        [types.InlineKeyboardButton(text="✅ Подтвердить обновление", callback_data=CONFIRM_ACTION_CALLBACK)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=CANCEL_FSM_CALLBACK)],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await _send_or_edit_message(target, text, reply_markup=reply_markup, parse_mode="MarkdownV2")

    await state.set_state(ProductUpdateFSM.confirm_update)


async def process_product_update_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение обновления товара (UPDATE FSM)."""
    await callback_query.answer()
    user_data = await state.get_data()
    product_id = user_data.get("updating_product_id")

    # Получаем новые значения (или старые, если были пропущены) из FSM state
    new_name = user_data.get("new_name")
    new_description = user_data.get("new_description")
    new_price = user_data.get("new_price") # Decimal
    new_category_id = user_data.get("new_category_id")
    new_manufacturer_id = user_data.get("new_manufacturer_id")

    # Формируем словарь с данными для обновления
    update_data = {
        "name": new_name,
        "description": new_description,
        "price": new_price, # Pass Decimal directly
        "category_id": new_category_id,
        "manufacturer_id": new_manufacturer_id
    }

    # Вызываем функцию обновления из utils/db.py
    updated_product = db.update_product(product_id, update_data)

    if updated_product:
        # Получаем обновленные имена связей для вывода.
        # Предполагаем, что db.update_product возвращает объект с загруженными связями
        # или lazy loading работает корректно.
        updated_category_name = updated_product.category.name if updated_product.category else 'Неизвестно'
        updated_manufacturer_name = updated_product.manufacturer.name if updated_product.manufacturer else 'Неизвестно'

        # Экранируем все для MarkdownV2
        updated_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_product.name)
        updated_price_esc = types.utils.markdown.text_decorations.escape_markdown(f'{updated_product.price:.2f}')
        updated_category_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_category_name)
        updated_manufacturer_name_esc = types.utils.markdown.text_decorations.escape_markdown(updated_manufacturer_name)

        await callback_query.message.edit_text(
            f"🎉 **Товар (ID: `{product_id}`) успешно обновлен!** 🎉\n"
            f"Новое название: `{updated_name_esc}`\n"
            f"Новая цена: `{updated_price_esc}` руб.\n"
            f"Новая категория: `{updated_category_name_esc}`\n"
            f"Новый производитель: `{updated_manufacturer_name_esc}`",
            parse_mode="MarkdownV2"
        )
    else:
        # TODO: Добавить более конкретную ошибку из db.update_product, если возможно (IntegrityError)
        # Например, попытка установить несуществующую категорию/производителя, или имя товара уже занято (если бы имя было unique)
        # В текущей схеме Product.name не unique, IntegrityError может быть из-за category_id или manufacturer_id
        await callback_query.message.edit_text(
            f"❌ **Ошибка при обновлении товара (ID: `{product_id}`).**\n"
            "Проверьте корректность введенных данных или связей (например, несуществующие ID категории/производителя).",
             parse_mode="MarkdownV2"
        )

    await state.clear() # Завершаем FSM
    # Возвращаемся в главное админ-меню (предполагается, что эта функция доступна)
    from ..admin_handlers_aiogram import show_admin_main_menu_aiogram
    await show_admin_main_menu_aiogram(callback_query, state)


# --- Router Registration ---
# Создаем роутер специально для FSM обновления товара
product_update_fsm_router = Router(name="product_update_fsm_router")

def register_product_update_handlers(router: Router):
    """Регистрирует обработчики для FSM обновления товара."""

    # ENTRY POINT: Запуск FSM по колбэку "Редактировать" из детального просмотра товара
    # Используем F.data.startswith для фильтрации
    router.callback_query.register(
        start_product_update,
        F.data.startswith(PRODUCT_UPDATE_INIT_CALLBACK_PREFIX)
        # Без фильтра состояний, т.к. это вход в FSM
    )

    # Обработчики шагов FSM (ожидают текстовый ввод с определенным состоянием)
    # Используем фильтр F.text, чтобы пропускать другие типы сообщений (фото, стикеры и т.п.)
    router.message.register(process_product_name_update, ProductUpdateFSM.waiting_for_name, F.text)
    router.message.register(process_product_description_update, ProductUpdateFSM.waiting_for_description, F.text)
    router.message.register(process_product_price_update, ProductUpdateFSM.waiting_for_price, F.text)

    # Хэндлеры выбора и пагинации категории (ожидают колбэк с определенным состоянием)
    router.callback_query.register(
        process_product_category_update_selection,
        ProductUpdateFSM.waiting_for_category_selection,
        # Ловит либо выбор категории по ID (startswith), либо кнопку "Оставить текущую" (Text)
        F.data.startswith(UPDATE_PROD_CAT_SEL_PREFIX) | (F.data == KEEP_CURRENT_CATEGORY_CALLBACK)
    )
    router.callback_query.register(
        process_product_category_update_pagination,
        ProductUpdateFSM.waiting_for_category_selection,
        # Ловит колбэки пагинации с соответствующим префиксом
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_PROD_CAT_PAGE_PREFIX.strip(':')}:")
    )

    # Хэндлеры выбора и пагинации производителя (ожидают колбэк с определенным состоянием)
    router.callback_query.register(
        process_product_manufacturer_update_selection,
        ProductUpdateFSM.waiting_for_manufacturer_selection,
         # Ловит либо выбор производителя по ID, либо кнопку "Оставить текущего"
        F.data.startswith(UPDATE_PROD_MAN_SEL_PREFIX) | (F.data == KEEP_CURRENT_MANUFACTURER_CALLBACK)
    )
    router.callback_query.register(
        process_product_manufacturer_update_pagination,
        ProductUpdateFSM.waiting_for_manufacturer_selection,
        # Ловит колбэки пагинации с соответствующим префиксом
        F.data.startswith(f"{PAGINATION_CALLBACK_PREFIX}{UPDATE_PROD_MAN_PAGE_PREFIX.strip(':')}:")
    )

    # Хэндлер подтверждения (ожидает колбэк с определенным состоянием и колбэком подтверждения)
    router.callback_query.register(
        process_product_update_confirm,
        ProductUpdateFSM.confirm_update,
        F.data == CONFIRM_ACTION_CALLBACK
    )

    # Общий хэндлер отмены должен быть зарегистрирован отдельно, на более высоком уровне роутера или диспатчера.
    # Его следует регистрировать для всех состояний State("*") с фильтром Text(CANCEL_FSM_CALLBACK)
    # или F.text == "/cancel". Это делается в bot.py или admin_router.


# Вызываем функцию регистрации для этого роутера
register_product_update_handlers(product_update_fsm_router)

# Роутер product_update_fsm_router теперь содержит все обработчики и готов к включению в основной диспатчер/роутер.
