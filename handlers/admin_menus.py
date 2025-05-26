# your_bot/handlers/admin_menus.py
# Обработчики и функции для административного меню (обновлен для LIST, DETAIL, PAGINATION, DELETE entry points)

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from math import ceil # Для расчета общего количества страниц

# Импортируем константы, включая новые DETAIL, DELETE колбэки и префиксы
from .admin_constants import *
# Импортируем функции базы данных
from utils import db

logger = logging.getLogger(__name__)

# Список ID пользователей-администраторов (ЗАГЛУШКА - заменить на реальные ID или получение из конфига)
# В реальном проекте лучше вынести в файл конфигурации или получать из БД.
ADMIN_USER_IDS = [6669548787, 67890] # <-- ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ID ВАШИХ АДМИНИСТРАТОРОВ

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_USER_IDS

# --- Вспомогательная функция для парсинга callback_data ---
def parse_admin_callback(data: str) -> tuple[str | None, str | None, list[str]]:
    """
    Парсит callback_data админ-меню в формате 'admin_entity_action(_subaction)?(_id1)?(_id2)?'.
    Возвращает (entity, action, ids).
    Пример: 'admin_products_detail_123' -> ('products', 'detail', ['123'])
    Пример: 'admin_stock_detail_456_789' -> ('stock', 'detail', ['456', '789'])
    Пример: 'admin_products_list_page_2' -> ('products', 'list', ['page', '2'])
    Пример: 'admin_products_detail_123_edit_123' -> ('products', 'detail', ['123', 'edit', '123'])
    """
    parts = data.split('_')
    if len(parts) < 2 or parts[0] != 'admin':
        return None, None, [] # Неверный формат или не админский колбэк

    entity = parts[1] # products, stock, categories, manufacturers, locations
    action = parts[2] # list, add, find, update, detail, delete_confirm, delete_execute, back, main

    # Идентификаторы и субдействия начинаются после entity и action
    ids_or_subaction = parts[3:]

    # Проверяем наличие субдействий типа _page_, _detail_, _edit_, _delete_confirm_, _delete_execute_
    # Action в callback_data может быть составным, например, admin_products_detail_123
    # handle_admin_callback будет вызван для pattern='^admin_', parse_admin_callback получит 'admin_products_detail_123'
    # entity='products', action='detail', ids_or_subaction=['123']
    # callback_data для кнопки "Детали" будет admin_products_detail_{id} -> action='detail', ids=['id']
    # callback_data для кнопки пагинации будет admin_products_list_page_{num} -> action='list', ids=['page', 'num']
    # callback_data для кнопки "Редактировать" на деталях будет admin_entity_detail_ID(s)_edit_ID(s)
    # callback_data для кнопки "Удалить" на деталях будет admin_entity_detail_ID(s)_delete_confirm_ID(s)
    # CallbackHandler для этих кнопок будет иметь специфичный pattern и вызывать соответствующий ConvHandler entry_point
    # Поэтому в parse_admin_callback нам достаточно выделить entity, action и оставшиеся части как potential_ids
    # handle_admin_callback сам будет маршрутизировать на основе полного callback_data или его начала.

    # Если action - это list, detail, delete_confirm, update (из меню), add (из меню), find (из меню)
    # то entity - это products, stock и т.д.
    # Если action - это back или main, то entity - это products, main и т.д.

    # Проверяем специальные префиксы в конце колбэка для определения реального действия
    # Например, admin_products_detail_123_edit_123
    # parse_admin_callback получит data='admin_products_detail_123_edit_123'
    # entity = 'products', action = 'detail', ids_or_subaction = ['123', 'edit', '123']
    # В этом случае реальное действие не 'detail', а 'edit' с ID '123'.
    # Это усложняет parse_admin_callback, лучше парсить в хэндлерах.
    # handle_admin_callback будет маршрутизировать по полному data (через pattern).

    # Возвращаем entity, action и оставшиеся части как потенциальные ID.
    # Оставшиеся части могут содержать subaction_prefix + ids.
    return entity, action, parts[3:]


# --- Функции построения клавиатур ---
# (Без изменений)
def build_admin_main_keyboard():
    """Строит клавиатуру основного админского меню."""
    keyboard = [
        [InlineKeyboardButton("Управление товарами", callback_data=ADMIN_PRODUCTS_CALLBACK)],
        [InlineKeyboardButton("Управление остатками", callback_data=ADMIN_STOCK_CALLBACK)],
        [InlineKeyboardButton("Управление категориями", callback_data=ADMIN_CATEGORIES_CALLBACK)],
        [InlineKeyboardButton("Управление производителями", callback_data=ADMIN_MANUFACTURERS_CALLBACK)],
        [InlineKeyboardButton("Управление местоположениями", callback_data=ADMIN_LOCATIONS_CALLBACK)],
        # Добавить другие кнопки основного меню при необходимости
    ]
    return InlineKeyboardMarkup(keyboard)

def build_products_menu_keyboard():
    """Строит клавиатуру меню управления товарами."""
    keyboard = [
        [InlineKeyboardButton("Список товаров", callback_data=ADMIN_PRODUCTS_LIST)],
        [InlineKeyboardButton("Добавить товар", callback_data=ADMIN_PRODUCTS_ADD)],
        [InlineKeyboardButton("Найти товар", callback_data=ADMIN_PRODUCTS_FIND)],
        [InlineKeyboardButton("Обновить товар по ID", callback_data=ADMIN_PRODUCTS_UPDATE)], # Добавлено
        # Кнопка удаления по ID может быть в DETAIL или отдельным диалогом
        [InlineKeyboardButton("<< Назад", callback_data=ADMIN_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_stock_menu_keyboard():
    """Строит клавиатуру меню управления остатками."""
    keyboard = [
        [InlineKeyboardButton("Список остатков", callback_data=ADMIN_STOCK_LIST)],
        [InlineKeyboardButton("Добавить/Изменить остаток", callback_data=ADMIN_STOCK_ADD)], # Инициирует диалог ввода product_id, location_id, quantity
        [InlineKeyboardButton("Найти остаток по товару/локации", callback_data=ADMIN_STOCK_FIND)],
        # Удаление остатка по product_id/location_id может быть отдельным диалогом или частью find/detail results
        [InlineKeyboardButton("<< Назад", callback_data=ADMIN_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_categories_menu_keyboard():
    """Строит клавиатуру меню управления категориями."""
    keyboard = [
        [InlineKeyboardButton("Список категорий", callback_data=ADMIN_CATEGORIES_LIST)],
        [InlineKeyboardButton("Добавить категорию", callback_data=ADMIN_CATEGORIES_ADD)],
        [InlineKeyboardButton("Найти категорию", callback_data=ADMIN_CATEGORIES_FIND)],
        [InlineKeyboardButton("Обновить категорию по ID", callback_data=ADMIN_CATEGORIES_UPDATE)], # Добавлено
         # Кнопка удаления по ID может быть в DETAIL или отдельным диалогом
        [InlineKeyboardButton("<< Назад", callback_data=ADMIN_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_manufacturers_menu_keyboard():
    """Строит клавиатуру меню управления производителями."""
    keyboard = [
        [InlineKeyboardButton("Список производителей", callback_data=ADMIN_MANUFACTURERS_LIST)],
        [InlineKeyboardButton("Добавить производителя", callback_data=ADMIN_MANUFACTURERS_ADD)],
        [InlineKeyboardButton("Найти производителя", callback_data=ADMIN_MANUFACTURERS_FIND)],
        [InlineKeyboardButton("Обновить производителя по ID", callback_data=ADMIN_MANUFACTURERS_UPDATE)], # Добавлено
        # Кнопка удаления по ID может быть в DETAIL или отдельным диалогом
        [InlineKeyboardButton("<< Назад", callback_data=ADMIN_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_locations_menu_keyboard():
    """Строит клавиатуру меню управления местоположениями."""
    keyboard = [
        [InlineKeyboardButton("Список местоположений", callback_data=ADMIN_LOCATIONS_LIST)],
        [InlineKeyboardButton("Добавить местоположение", callback_data=ADMIN_LOCATIONS_ADD)],
        [InlineKeyboardButton("Найти местоположение", callback_data=ADMIN_LOCATIONS_FIND)],
        [InlineKeyboardButton("Обновить местоположение по ID", callback_data=ADMIN_LOCATIONS_UPDATE)], # Добавлено
        # Кнопка удаления по ID может быть в DETAIL или отдельным диалогом
        [InlineKeyboardButton("<< Назад", callback_data=ADMIN_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Функции отображения меню ---
# Эти функции вызываются из handle_admin_callback или fallbacks ConversationHandler'ов
# и отвечают за отображение соответствующего меню.

async def show_admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает основное админское меню."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        logger.warning(f"Попытка доступа к админке от не-админа: {user_id}")
        if update.callback_query:
            await update.callback_query.answer("У вас нет прав администратора\\.", show_alert=True)
        elif update.message:
            await update.message.reply_text("У вас нет прав администратора\\.")
        return

    query = update.callback_query
    keyboard = build_admin_main_keyboard()

    if query:
        # Если это колбэк, пытаемся отредактировать сообщение
        try:
            await query.edit_message_text("Выберите раздел администрирования:", reply_markup=keyboard)
        except Exception:
            # Если сообщение не найдено или отредактировано другим хэндлером, отправляем новое
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Выберите раздел администрирования:", reply_markup=keyboard)

    elif update.message:
        # Если вызвана не из колбэка (например, командой /admin)
        await update.message.reply_text("Выберите раздел администрирования:", reply_markup=keyboard)


async def show_products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления товарами."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    keyboard = build_products_menu_keyboard()
    text = "Управление товарами:"

    if query:
        # Если это колбэк, пытаемся отредактировать сообщение
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
             # Если сообщение не найдено или отредактировано другим хэндлером, отправляем новое
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
    elif update.message:
         # Если вызвана из MessageHandler (например, из ConversationHandler fallback)
         await update.message.reply_text(text, reply_markup=keyboard)

async def show_stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления остатками."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    keyboard = build_stock_menu_keyboard()
    text = "Управление остатками:"

    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
    elif update.message:
         await update.message.reply_text(text, reply_markup=keyboard)


async def show_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления категориями."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    keyboard = build_categories_menu_keyboard()
    text = "Управление категориями:"

    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
    elif update.message:
         await update.message.reply_text(text, reply_markup=keyboard)


async def show_manufacturers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления производителями."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    keyboard = build_manufacturers_menu_keyboard()
    text = "Управление производителями:"

    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
    elif update.message:
         await update.message.reply_text(text, reply_markup=keyboard)


async def show_locations_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления местоположениями."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    keyboard = build_locations_menu_keyboard()
    text = "Управление местоположениями:"

    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
             await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)
    elif update.message:
         await update.message.reply_text(text, reply_markup=keyboard)


# --- Функции для построения клавиатуры пагинации ---

def build_pagination_keyboard(current_page: int, total_pages: int, base_callback: str) -> InlineKeyboardMarkup:
    """Строит клавиатуру для пагинации."""
    keyboard = []
    row = []

    # Кнопка "Пред."
    if current_page > 1:
        row.append(InlineKeyboardButton("« Пред.", callback_data=f"{base_callback}{ADMIN_LIST_PAGE_PREFIX}{current_page - 1}"))
    else:
         row.append(InlineKeyboardButton(" ", callback_data="ignore")) # Пустая кнопка для выравнивания

    # Кнопка текущей страницы (без действия)
    row.append(InlineKeyboardButton(f"Стр. {current_page}/{total_pages}", callback_data="ignore")) # Кнопка без действия

    # Кнопка "След."
    if current_page < total_pages:
        row.append(InlineKeyboardButton("След. »", callback_data=f"{base_callback}{ADMIN_LIST_PAGE_PREFIX}{current_page + 1}"))
    else:
         row.append(InlineKeyboardButton(" ", callback_data="ignore")) # Пустая кнопка для выравнивания


    keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


# --- Функции обработчиков: LIST с пагинацией ---
# Эти функции вызываются из handle_admin_callback или специфичных CallbackQueryHandler'ов для пагинации
# Они отвечают за получение данных и форматирование сообщения списка с кнопками деталей и пагинацией.

async def handle_entity_list(update: Update, context: ContextTypes.DEFAULT_TYPE, entity_name: str, get_all_func, detail_callback_prefix: str, back_callback: str) -> None:
    """
    Универсальный обработчик для отображения списков сущностей с пагинацией.
    entity_name: 'products', 'categories', etc. (для использования в db.get_entity_count и db.get_all_paginated)
    get_all_func: функция из db для получения всех сущностей (по сути, не используется напрямую, т.к. пагинация реализована через db.get_all_paginated)
    detail_callback_prefix: префикс для колбэка детального просмотра (например, ADMIN_PRODUCTS_DETAIL)
    back_callback: колбэк для кнопки "Назад"
    """
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # answer() уже вызван в handle_admin_callback

    # Определяем текущую страницу
    current_page = 1
    # Проверяем, пришел ли запрос от кнопки пагинации
    if ADMIN_LIST_PAGE_PREFIX in query.data:
        try:
             # Парсим номер страницы из callback_data: admin_entity_list_page_X
             parts = query.data.split(ADMIN_LIST_PAGE_PREFIX)
             current_page = int(parts[-1])
             if current_page < 1: current_page = 1 # Минимальная страница 1
             logger.debug(f"Пагинация для {entity_name}: запрошена страница {current_page}")
        except (ValueError, IndexError):
             logger.error(f"Не удалось распарсить номер страницы из callback: {query.data}", exc_info=True)
             current_page = 1 # Если ошибка парсинга, возвращаемся на первую страницу
    else:
         # Если это первый вызов списка (кнопка "Список сущностей"), страница 1
         logger.debug(f"Запрошен первый список для {entity_name}. Страница 1.")


    offset = (current_page - 1) * PAGE_SIZE

    try:
        # Получаем общее количество элементов для расчета страниц
        total_count = db.get_entity_count(entity_name)
        total_pages = ceil(total_count / PAGE_SIZE) if total_count > 0 else 1

        # Получаем элементы для текущей страницы
        items = db.get_all_paginated(entity_name, offset, PAGE_SIZE)

    except Exception as e:
         logger.error(f"Ошибка при получении списка {entity_name} с пагинацией: {e}", exc_info=True)
         await query.edit_message_text(f"❌ Произошла ошибка при загрузке списка {entity_name}.")
         # Возвращаемся в меню сущности (вызов через handle_admin_callback или напрямую)
         if back_callback == ADMIN_BACK_PRODUCTS_MENU: await show_products_menu(update, context)
         elif back_callback == ADMIN_BACK_STOCK_MENU: await show_stock_menu(update, context)
         elif back_callback == ADMIN_BACK_CATEGORIES_MENU: await show_categories_menu(update, context)
         elif back_callback == ADMIN_BACK_MANUFACTURERS_MENU: await show_manufacturers_menu(update, context)
         elif back_callback == ADMIN_BACK_LOCATIONS_MENU: await show_locations_menu(update, context)
         else: await show_admin_main_menu(update, context) # Fallback на главное меню
         return


    response_text = f"Список {entity_name.capitalize()} (Стр. {current_page}/{total_pages}, всего: {total_count}):\n\n"
    item_buttons = [] # Кнопки для детального просмотра/действий по каждому элементу

    if items:
        for item in items:
            item_id_str = "" # Строковое представление ID(s) для колбэков
            item_display = ""
            detail_data_prefix = "" # Базовый колбэк для деталей (entity_detail)

            if entity_name == 'products':
                item_id_str = str(item.id)
                item_display = f"📦 ID: `{item.id}` - *{item.name}*"
                detail_data_prefix = ADMIN_PRODUCTS_DETAIL
            elif entity_name == 'stock':
                # Stock имеет составной ключ product_id, location_id
                item_id_prod = item.product_id
                item_id_loc = item.location_id
                item_id_str = f"{item_id_prod}_{item_id_loc}"

                # Для отображения названий нужно подгрузить связанные объекты
                session = db.SessionLocal()
                try:
                    product_name = session.query(db.Product.name).filter_by(id=item_id_prod).scalar() or 'Неизвестный товар'
                    location_name = session.query(db.Location.name).filter_by(id=item_id_loc).scalar() or 'Неизвестное местоположение'
                    session.close()
                except Exception:
                    product_name = 'Ошибка загрузки товара'
                    location_name = 'Ошибка загрузки локации'
                    if 'session' in locals() and session: session.close()


                item_display = f"📦📍 Товар ID `{item_id_prod}` (*{product_name}*) @ Местоположение ID `{item_id_loc}` (*{location_name}*) - Кол-во: `{item.quantity}`"
                detail_data_prefix = ADMIN_STOCK_DETAIL

            elif entity_name == 'categories':
                item_id_str = str(item.id)
                parent_info = f" (Родитель: ID `{item.parent_id}`)" if item.parent_id else ""
                item_display = f"📁 ID: `{item.id}` - *{item.name}*{parent_info}"
                detail_data_prefix = ADMIN_CATEGORIES_DETAIL
            elif entity_name == 'manufacturers':
                item_id_str = str(item.id)
                item_display = f"🏭 ID: `{item.id}` - *{item.name}*"
                detail_data_prefix = ADMIN_MANUFACTURERS_DETAIL
            elif entity_name == 'locations':
                item_id_str = str(item.id)
                item_display = f"📍 ID: `{item.id}` - *{item.name}*"
                detail_data_prefix = ADMIN_LOCATIONS_DETAIL

            response_text += f"{item_display}\n\n"
            # Callback для детали: admin_entity_detail_ID(s)
            item_buttons.append([InlineKeyboardButton(f"Детали {item_id_str}", callback_data=f"admin_{entity_name}{ADMIN_DETAIL_PREFIX}{item_id_str}")])

    else:
        response_text += f"Список {entity_name} пуст."

    # Клавиатура пагинации
    # Базовый колбэк для пагинации - это просто 'admin_entity_list'
    base_list_callback = f"admin_{entity_name}_list"
    pagination_keyboard = build_pagination_keyboard(current_page, total_pages, base_list_callback)

    # Объединяем кнопки элементов и кнопки пагинации
    full_keyboard = item_buttons + pagination_keyboard.inline_keyboard
    full_keyboard.append([InlineKeyboardButton("<< Назад", callback_data=back_callback)]) # Кнопка "Назад" внизу

    await query.edit_message_text(response_text, reply_markup=InlineKeyboardMarkup(full_keyboard), parse_mode='Markdown')


# Реализация конкретных обработчиков списка, вызывающих универсальный
# Эти хэндлеры вызываются из handle_admin_callback для первой страницы или из специфичных
# CallbackQueryHandler'ов для пагинации, зарегистрированных в main.py
async def handle_products_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на список товаров (первая страница или пагинация)."""
    await handle_entity_list(update, context, 'products', db.get_all_products, ADMIN_PRODUCTS_DETAIL, ADMIN_BACK_PRODUCTS_MENU)

async def handle_stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на список остатков (первая страница или пагинация)."""
    await handle_entity_list(update, context, 'stock', db.get_all_stock, ADMIN_STOCK_DETAIL, ADMIN_BACK_STOCK_MENU)

async def handle_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на список категорий (первая страница или пагинация)."""
    await handle_entity_list(update, context, 'categories', db.get_all_categories, ADMIN_CATEGORIES_DETAIL, ADMIN_BACK_CATEGORIES_MENU)

async def handle_manufacturers_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на список производителей (первая страница или пагинация)."""
    await handle_entity_list(update, context, 'manufacturers', db.get_all_manufacturers, ADMIN_MANUFACTURERS_DETAIL, ADMIN_BACK_MANUFACTURERS_MENU)

async def handle_locations_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на список местоположений (первая страница или пагинация)."""
    await handle_entity_list(update, context, 'locations', db.get_all_locations, ADMIN_LOCATIONS_DETAIL, ADMIN_BACK_LOCATIONS_MENU)


# --- Функции обработчиков: DETAIL ---
# Эти функции вызываются из специфичных CallbackQueryHandler'ов для деталей, зарегистрированных в main.py
# Они отвечают за получение данных по ID и форматирование сообщения деталей с кнопками действий.

async def handle_entity_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, entity_name: str, get_by_id_func, back_to_list_callback: str, edit_callback_prefix: str, delete_confirm_callback_prefix: str, entity_ids_str_list: list[str]) -> None:
    """
    Универсальный обработчик для отображения детальной информации о сущности.
    entity_name: 'products', 'categories', etc.
    get_by_id_func: функция из db для получения сущности по ID (или IDs)
    back_to_list_callback: колбэк для возврата к списку
    edit_callback_prefix: префикс для колбэка редактирования (например, ADMIN_PRODUCTS_UPDATE)
    delete_confirm_callback_prefix: префикс для колбэка подтверждения удаления (например, ADMIN_PRODUCTS_DELETE_CONFIRM)
    entity_ids_str_list: список строковых ID, полученных из callback_data (после префикса DETAIL)
    """
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # answer() уже вызван в main.py специфичным CallbackQueryHandler'ом

    item = None
    item_id_str = '_'.join(entity_ids_str_list) # Строковое представление ID(s) для колбэков

    try:
        if entity_name == 'stock':
            # Stock requires product_id and location_id as integer
            if len(entity_ids_str_list) == 2:
                product_id = int(entity_ids_str_list[0])
                location_id = int(entity_ids_str_list[1])
                item = get_by_id_func(product_id, location_id) # db.get_stock_by_ids
            else:
                logger.error(f"Неверное количество ID для остатка: {entity_ids_str_list}")
                await query.edit_message_text(f"❌ Ошибка: Неверный формат ID для остатка.")
                await handle_stock_list(update, context) # Вернуться к списку
                return
        else:
            # Other entities use a single integer ID
            if len(entity_ids_str_list) == 1:
                item_id = int(entity_ids_str_list[0])
                item = get_by_id_func(item_id) # db.get_*_by_id
            else:
                logger.error(f"Неверное количество ID для {entity_name}: {entity_ids_str_list}")
                await query.edit_message_text(f"❌ Ошибка: Неверный формат ID для {entity_name}.")
                # Вернуться к списку соответствующей сущности
                if back_to_list_callback == ADMIN_BACK_PRODUCTS_MENU: await handle_products_list(update, context)
                elif back_to_list_callback == ADMIN_BACK_STOCK_MENU: await handle_stock_list(update, context)
                elif back_to_list_callback == ADMIN_BACK_CATEGORIES_MENU: await handle_categories_list(update, context)
                elif back_to_list_callback == ADMIN_BACK_MANUFACTURERS_MENU: await handle_manufacturers_list(update, context)
                elif back_to_list_callback == ADMIN_BACK_LOCATIONS_MENU: await handle_locations_list(update, context)
                return

    except ValueError:
        logger.error(f"Неверный формат ID (не целое число) для {entity_name}: {entity_ids_str_list}", exc_info=True)
        await query.edit_message_text(f"❌ Ошибка: Неверный формат ID для {entity_name}.")
        # Вернуться к списку соответствующей сущности
        if back_to_list_callback == ADMIN_BACK_PRODUCTS_MENU: await handle_products_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_STOCK_MENU: await handle_stock_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_CATEGORIES_MENU: await handle_categories_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_MANUFACTURERS_MENU: await handle_manufacturers_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_LOCATIONS_MENU: await handle_locations_list(update, context)
        return
    except Exception as e:
        logger.error(f"Ошибка при получении деталей для {entity_name} с ID {item_id_str}: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Произошла ошибка при загрузке деталей для {entity_name}.")
        # Вернуться к списку соответствующей сущности
        if back_to_list_callback == ADMIN_BACK_PRODUCTS_MENU: await handle_products_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_STOCK_MENU: await handle_stock_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_CATEGORIES_MENU: await handle_categories_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_MANUFACTURERS_MENU: await handle_manufacturers_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_LOCATIONS_MENU: await handle_locations_list(update, context)
        return


    if not item:
        await query.edit_message_text(f"🔍 {entity_name.capitalize()} с ID {item_id_str} не найден.")
        # Возвращаемся к списку сущности
        if back_to_list_callback == ADMIN_BACK_PRODUCTS_MENU: await handle_products_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_STOCK_MENU: await handle_stock_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_CATEGORIES_MENU: await handle_categories_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_MANUFACTURERS_MENU: await handle_manufacturers_list(update, context)
        elif back_to_list_callback == ADMIN_BACK_LOCATIONS_MENU: await handle_locations_list(update, context)
        return

    # Формируем сообщение с деталями
    detail_text = f"📊 Детали {entity_name.capitalize()}:\n\n"
    if entity_name == 'products':
        # Подгружаем названия категории и производителя
        session = db.SessionLocal()
        try:
            category_name = session.query(db.Category.name).filter_by(id=item.category_id).scalar() or 'Неизвестная категория'
            manufacturer_name = session.query(db.Manufacturer.name).filter_by(id=item.manufacturer_id).scalar() or 'Неизвестный производитель'
        except Exception as e:
             logger.error(f"Ошибка при загрузке связанных данных (категория/производитель) для товара ID {item.id}: {e}", exc_info=True)
             category_name = 'Ошибка загрузки категории'
             manufacturer_name = 'Ошибка загрузки производителя'
        finally:
             session.close()

        detail_text += f"📦 ID: `{item.id}`\n" \
                       f"Название: *{item.name}*\n" \
                       f"Описание: {item.description or 'Нет описания'}\n" \
                       f"Цена: {item.price} руб.\n" \
                       f"Категория: `{item.category_id}` (*{category_name}*)\n" \
                       f"Производитель: `{item.manufacturer_id}` (*{manufacturer_name}*)\n"
    elif entity_name == 'stock':
         session = db.SessionLocal()
         try:
             product_name = session.query(db.Product.name).filter_by(id=item.product_id).scalar() or 'Неизвестный товар'
             location_name = session.query(db.Location.name).filter_by(id=item.location_id).scalar() or 'Неизвестное местоположение'
         except Exception as e:
              logger.error(f"Ошибка при загрузке связанных данных (товар/локация) для остатка prodID={item.product_id}, locID={item.location_id}: {e}", exc_info=True)
              product_name = 'Ошибка загрузки товара'
              location_name = 'Ошибка загрузки локации'
         finally:
              session.close()

         detail_text += f"📦 Товар ID: `{item.product_id}` (*{product_name}*)\n" \
                        f"📍 Местоположение ID: `{item.location_id}` (*{location_name}*)\n" \
                        f"🔢 Количество: `{item.quantity}`\n"
    elif entity_name == 'categories':
        parent_info = f"Родитель: ID `{item.parent_id}`" if item.parent_id is not None else "Родитель: Нет"
        # Можно добавить загрузку имени родительской категории при желании
        detail_text += f"📁 ID: `{item.id}`\n" \
                       f"Название: *{item.name}*\n" \
                       f"{parent_info}\n"
    elif entity_name == 'manufacturers':
        detail_text += f"🏭 ID: `{item.id}`\n" \
                       f"Название: *{item.name}*\n"
    elif entity_name == 'locations':
        detail_text += f"📍 ID: `{item.id}`\n" \
                       f"Название: *{item.name}*\n"

    # Кнопки действий (Редактировать, Удалить)
    action_buttons = []
    # Кнопка "Редактировать"
    # Редактирование инициирует ConversationHandler. Callback: admin_entity_detail_ID(s)_edit_ID(s)
    # Передаем ID(s) дважды: один раз для идентификации деталей, второй - для entry point ConvHandler
    # ConvHandler Update будет парсить ID из части после ADMIN_EDIT_PREFIX
    edit_callback_data = f"admin_{entity_name}{ADMIN_DETAIL_PREFIX}{item_id_str}{ADMIN_EDIT_PREFIX}{item_id_str}"
    action_buttons.append(InlineKeyboardButton("✏️ Редактировать", callback_data=edit_callback_data))

    # Кнопка "Удалить"
    # Удаление инициирует ConversationHandler для подтверждения. Callback: admin_entity_detail_ID(s)_delete_confirm_ID(s)
    # Аналогично, передаем ID(s) дважды. ConvHandler Delete будет парсить ID из части после ADMIN_DELETE_CONFIRM_PREFIX
    delete_callback_data = f"admin_{entity_name}{ADMIN_DETAIL_PREFIX}{item_id_str}{ADMIN_DELETE_CONFIRM_PREFIX}{item_id_str}"
    action_buttons.append(InlineKeyboardButton("🗑️ Удалить", callback_data=delete_callback_data))

    # Клавиатура с кнопками действий и "Назад"
    keyboard = InlineKeyboardMarkup([
        action_buttons,
        [InlineKeyboardButton("« К списку", callback_data=back_to_list_callback)] # Возврат к списку сущности
    ])

    await query.edit_message_text(detail_text, reply_markup=keyboard, parse_mode='Markdown')

# Реализация конкретных обработчиков деталей, вызывающих универсальный
# Эти хэндлеры вызываются из main.py специфичными CallbackQueryHandler'ами
async def handle_products_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # Парсим ID из callback_data формата admin_products_detail_ID
    # parts = query.data.split(ADMIN_PRODUCTS_DETAIL) # Этот сплит неверен, если префикс DETAIL общий
    # Используем парсер, но берем только часть с ID
    parts_after_detail_prefix = query.data.split(ADMIN_DETAIL_PREFIX)[1].split('_') # Получаем список строковых ID

    await handle_entity_detail(update, context, 'products', db.get_product_by_id, ADMIN_PRODUCTS_LIST, ADMIN_PRODUCTS_UPDATE, ADMIN_PRODUCTS_DELETE_CONFIRM, parts_after_detail_prefix)

async def handle_stock_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # Парсим ID из callback_data формата admin_stock_detail_prodID_locID
    parts_after_detail_prefix = query.data.split(ADMIN_DETAIL_PREFIX)[1].split('_') # Получаем список строковых ID [prodID, locID]

    await handle_entity_detail(update, context, 'stock', db.get_stock_by_ids, ADMIN_STOCK_LIST, ADMIN_STOCK_ADD, ADMIN_STOCK_DELETE_CONFIRM, parts_after_detail_prefix) # Переиспользуем ADMIN_STOCK_ADD как entry point для редактирования количества

async def handle_categories_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # Парсим ID из callback_data формата admin_categories_detail_ID
    parts_after_detail_prefix = query.data.split(ADMIN_DETAIL_PREFIX)[1].split('_')

    await handle_entity_detail(update, context, 'categories', db.get_category_by_id, ADMIN_CATEGORIES_LIST, ADMIN_CATEGORIES_UPDATE, ADMIN_CATEGORIES_DELETE_CONFIRM, parts_after_detail_prefix)

async def handle_manufacturers_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # Парсим ID из callback_data формата admin_manufacturers_detail_ID
    parts_after_detail_prefix = query.data.split(ADMIN_DETAIL_PREFIX)[1].split('_')

    await handle_entity_detail(update, context, 'manufacturers', db.get_manufacturer_by_id, ADMIN_MANUFACTURERS_LIST, ADMIN_MANUFACTURERS_UPDATE, ADMIN_MANUFACTURERS_DELETE_CONFIRM, parts_after_detail_prefix)

async def handle_locations_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    query = update.callback_query
    # Парсим ID из callback_data формата admin_locations_detail_ID
    parts_after_detail_prefix = query.data.split(ADMIN_DETAIL_PREFIX)[1].split('_')

    await handle_entity_detail(update, context, 'locations', db.get_location_by_id, ADMIN_LOCATIONS_LIST, ADMIN_LOCATIONS_UPDATE, ADMIN_LOCATIONS_DELETE_CONFIRM, parts_after_detail_prefix)


# --- Главный обработчик колбэков админ меню ---
# Этот хэндлер перехватывает все колбэки, начинающиеся на 'admin_',
# которые не были перехвачены ConversationHandler'ами или более специфичными
# CallbackQueryHandler'ами (для DETAIL и PAGINATION).

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """
    Основной обработчик всех колбэков, начинающихся с 'admin_'.
    Распределяет запросы на соответствующие функции (навигация, LIST).
    Коллбэки, которые являются ENTRY_POINTS для ConversationHandler'ов (ADD, FIND, UPDATE, DELETE_CONFIRM),
    или специфичные колбэки DETAIL/PAGINATION должны быть перехвачены до этого хэндлера.
    """
    user_id = update.effective_user.id
    if not is_admin(user_id):
        # answer() уже вызван в main.py для колбэков
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return # Прерываем выполнение для не-админов

    query = update.callback_query
    data = query.data
    # answer() уже вызван в main.py для колбэков

    logger.info(f"Получен общий админский колбэк (не перехвачен ранее): {data} от пользователя {user_id}")

    # Навигационные колбэки и первый клик по "Список сущностей"
    # parse_admin_callback здесь поможет определить intent
    entity, action, _ = parse_admin_callback(data)

    if entity is None or action is None:
        logger.warning(f"Неверный формат админского колбэка в handle_admin_callback: {data}")
        await query.edit_message_text("Неизвестное действие администрирования.")
        await show_admin_main_menu(update, context)
        return

    # Обработка навигационных колбэков ('back', 'main') и первого клика по разделу ('products', 'stock' etc.)
    if action == 'main' or action == 'back':
         if entity == 'main' or data == ADMIN_BACK_MAIN: await show_admin_main_menu(update, context)
         elif entity == 'products' or data == ADMIN_BACK_PRODUCTS_MENU: await show_products_menu(update, context)
         elif entity == 'stock' or data == ADMIN_BACK_STOCK_MENU: await show_stock_menu(update, context)
         elif entity == 'categories' or data == ADMIN_BACK_CATEGORIES_MENU: await show_categories_menu(update, context)
         elif entity == 'manufacturers' or data == ADMIN_BACK_MANUFACTURERS_MENU: await show_manufacturers_menu(update, context)
         elif entity == 'locations' or data == ADMIN_BACK_LOCATIONS_MENU: await show_locations_menu(update, context)
         else:
              logger.warning(f"Неизвестный навигационный колбэк: {data}")
              await query.edit_message_text("Неизвестный раздел администрирования.")
              await show_admin_main_menu(update, context)

    # Обработка первого клика по "Список сущностей" (без пагинации)
    elif action == 'list':
        # handle_entity_list обрабатывает и первую страницу, и пагинацию.
        # Этот блок ловит только первый клик 'admin_entity_list'.
        # Пагинационные колбэки 'admin_entity_list_page_X' перехватываются раньше в main.py.
        if entity == 'products' and data == ADMIN_PRODUCTS_LIST:
            await handle_products_list(update, context)
        elif entity == 'stock' and data == ADMIN_STOCK_LIST:
            await handle_stock_list(update, context)
        elif entity == 'categories' and data == ADMIN_CATEGORIES_LIST:
            await handle_categories_list(update, context)
        elif entity == 'manufacturers' and data == ADMIN_MANUFACTURERS_LIST:
            await handle_manufacturers_list(update, context)
        elif entity == 'locations' and data == ADMIN_LOCATIONS_LIST:
            await handle_locations_list(update, context)
        else:
            logger.warning(f"Неизвестный колбэк списка: {data}")
            await query.edit_message_text("Неизвестный список для отображения.")
            await show_admin_main_menu(update, context)

    # Коллбэки, которые являются ENTRY_POINTS для ConversationHandler'ов (ADD, FIND, UPDATE из меню, DELETE_CONFIRM с деталей),
    # должны быть перехвачены ConversationHandler'ами, зарегистрированными ПЕРЕД этим хэндлером в main.py.
    # Если они попали сюда, это ошибка конфигурации или логики.
    # Также специфичные колбэки DETAIL и PAGINATION перехватываются перед этим хэндлером.
    # Если колбэк попал сюда и его action не 'back', 'main', или 'list', то это, скорее всего, некорректный или необработанный колбэк.
    # Добавляем лог для диагностики таких случаев.
    elif action not in ['list', 'back', 'main']:
        logger.error(f"Необработанный админский колбэк в handle_admin_callback: {data}")
        await query.edit_message_text("Произошла внутренняя ошибка или неизвестное действие.")
        await show_admin_main_menu(update, context)


    # handle_admin_callback не завершает ConversationHandler, он только маршрутизирует
    return # Возвращаем None, если не инициирован ConversationHandler
