# your_bot/handlers/admin_handlers_aiogram.py
# Обработчики административного меню для aiogram

import logging
from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Union

# Импортируем константы
from .admin_constants_aiogram import (
    ADMIN_MAIN_CALLBACK,
    ADMIN_PRODUCTS_CALLBACK, ADMIN_STOCK_CALLBACK, ADMIN_CATEGORIES_CALLBACK,
    ADMIN_MANUFACTURERS_CALLBACK, ADMIN_LOCATIONS_CALLBACK, # Исправлено MANUFACTURER_MAIN_MENU_CALLBACK на ADMIN_MANUFACTURERS_CALLBACK
    ADMIN_BACK_MAIN,
    # Импортируем константы действий (Добавить, Просмотреть список)
    PRODUCT_ADD_CALLBACK, PRODUCT_LIST_CALLBACK,
    STOCK_ADD_CALLBACK, STOCK_LIST_CALLBACK,
    CATEGORY_ADD_CALLBACK, CATEGORY_LIST_CALLBACK,
    MANUFACTURER_ADD_CALLBACK, MANUFACTURER_LIST_CALLBACK,
    LOCATION_ADD_CALLBACK, LOCATION_LIST_CALLBACK,
)

# Импорт функций отображения меню сущностей
from .admin_entity_menus_aiogram import (
    show_products_menu_aiogram, show_stock_menu_aiogram,
    show_categories_menu_aiogram, show_manufacturers_menu_aiogram,
    show_locations_menu_aiogram,
)

# Импорт функций отображения списков из admin_list_detail_handlers_aiogram (для ENTRY POINTS)
from .admin_list_detail_handlers_aiogram import (
    show_entity_list # Используем общую функцию для всех списков
)
# Импорт стартовых функций FSM для добавления (для ENTRY POINTS)
from .fsm.category_add_fsm import start_category_add
from .fsm.manufacturer_add_fsm import start_manufacturer_add
from .fsm.location_add_fsm import start_location_add
from .fsm.product_add_fsm import start_product_add
from .fsm.stock_add_fsm import start_stock_add

# Импорт хелпера для отправки/редактирования сообщения (определен в admin_list_detail_handlers_aiogram)
from .admin_list_detail_handlers_aiogram import _send_or_edit_message

# Заглушка для функции проверки администратора (замените на вашу реальную логику)
# В реальном проекте лучше брать ID из конфига или БД
ADMIN_USER_IDS = [6669548787] # <-- ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ID ВАШИХ АДМИНИСТРАТОРОВ

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_USER_IDS


# Функция для построения клавиатуры главного меню
def build_admin_main_keyboard():
    """Строит клавиатуру основного админского меню для aiogram."""
    keyboard = [
        [types.InlineKeyboardButton(text="📚 Управление товарами", callback_data=ADMIN_PRODUCTS_CALLBACK)],
        [types.InlineKeyboardButton(text="📦 Управление остатками", callback_data=ADMIN_STOCK_CALLBACK)],
        [types.InlineKeyboardButton(text="📂 Управление категориями", callback_data=ADMIN_CATEGORIES_CALLBACK)],
        [types.InlineKeyboardButton(text="🏭 Управление производителями", callback_data=ADMIN_MANUFACTURERS_CALLBACK)],
        [types.InlineKeyboardButton(text="📍 Управление местоположениями", callback_data=ADMIN_LOCATIONS_CALLBACK)],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# Функция показа главного меню
async def show_admin_main_menu_aiogram(target: Union[types.Message, types.CallbackQuery], state: FSMContext):
    """
    Генерирует и отправляет сообщение с Inline-клавиатурой главного админ-меню.
    Используется для ответа на команду /admin или при возврате в главное меню.
    """
    user_id = target.from_user.id
    if not is_admin(user_id):
        if isinstance(target, types.Message):
             await target.answer("У вас нет прав администратора.")
        elif isinstance(target, types.CallbackQuery):
             await target.answer("У вас нет прав администратора.", show_alert=True)
        return

    # Сбрасываем состояние FSM при возврате в главное меню
    # Это нужно, чтобы пользователь не остался в FSM-диалоге после нажатия кнопки "Главное меню"
    current_state = await state.get_state()
    if current_state:
         logging.info(f"Сброс FSM при показе главного меню из состояния: {current_state}")
         await state.clear()

    keyboard = build_admin_main_keyboard()
    text = "⚙️ **Главное админ-меню**\nВыберите раздел администрирования:"

    # Используем хелпер для отправки/редактирования
    await _send_or_edit_message(target, text, keyboard)


# Обработчик команды /admin
async def handle_admin_command(message: types.Message, state: FSMContext):
     """Обрабатывает команду /admin и показывает главное админ-меню."""
     await show_admin_main_menu_aiogram(message, state)


# Callback-обработчики для главного меню (навигация)
# Этот хэндлер отвечает только за навигацию по подменю и возврат в главное
async def admin_menu_navigation_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатия на кнопки главного админ-меню и кнопки "Назад" из подменю.
    Перенаправляет в соответствующие подменю или возвращает в главное меню.
    Не запускает FSM-диалоги (ими занимаются отдельные хэндлеры).
    """
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return

    data = callback_query.data
    await callback_query.answer() # Обязательно отвечаем на колбэк

    # Сброс FSM при навигации между меню разделов
    # Это важно, чтобы выйти из любого FSM-диалога, если пользователь нажал кнопку меню
    current_state = await state.get_state()
    if current_state:
         logging.info(f"Сброс FSM при навигации меню из состояния: {current_state}")
         await state.clear()


    # Логика маршрутизации по нажатой кнопке
    if data == ADMIN_PRODUCTS_CALLBACK:
        await show_products_menu_aiogram(callback_query, state)
    elif data == ADMIN_STOCK_CALLBACK:
        await show_stock_menu_aiogram(callback_query, state)
    elif data == ADMIN_CATEGORIES_CALLBACK:
        await show_categories_menu_aiogram(callback_query, state)
    elif data == ADMIN_MANUFACTURERS_CALLBACK: # Исправлено MANUFACTURER_MAIN_MENU_CALLBACK на ADMIN_MANUFACTURERS_CALLBACK
        await show_manufacturers_menu_aiogram(callback_query, state)
    elif data == ADMIN_LOCATIONS_CALLBACK:
        await show_locations_menu_aiogram(callback_query, state)
    elif data == ADMIN_BACK_MAIN:
        # Кнопка "Назад" из подменю ведет в главное меню
        await show_admin_main_menu_aiogram(callback_query, state)
    else:
        logging.warning(f"Неизвестный навигационный колбэк в admin_menu_navigation_handler: {data}")
        await show_admin_main_menu_aiogram(callback_query, state)


# --- Обработчики для действий "Добавить" (ENTRY POINTS для FSM добавления) ---
# Эти хэндлеры будут вызывать стартовые функции соответствующих FSM.
# Сами FSM-диалоги обрабатываются в отдельных модулях (handlers.fsm.*_add_fsm).
# Их фильтры (F.data == ...) должны быть зарегистрированы в bot.py или admin_router ПЕРЕД навигационным хэндлером.

async def handle_product_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Запускает FSM для добавления Товара."""
    # state.clear() вызывается внутри start_product_add
    await start_product_add(callback_query, state)


async def handle_stock_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Запускает FSM для добавления Остатка."""
    await start_stock_add(callback_query, state)


async def handle_category_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Запускает FSM для добавления Категории."""
    await start_category_add(callback_query, state)


async def handle_manufacturer_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Запускает FSM для добавления Производителя."""
    await start_manufacturer_add(callback_query, state)


async def handle_location_add(callback_query: types.CallbackQuery, state: FSMContext):
    """Запускает FSM для добавления Местоположения."""
    await start_location_add(callback_query, state)


# --- Обработчики для действий "Просмотреть список" (ENTRY POINTS для LIST/DETAIL) ---
# Эти хэндлеры будут вызывать стартовые функции отображения списка из admin_list_detail_handlers_aiogram.
# Их фильтры (F.data == ...) должны быть зарегистрированы в bot.py или admin_router ПЕРЕД навигационным хэндлером.

async def handle_product_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает просмотр списка Товаров."""
    # state.clear() вызывается внутри show_entity_list (обертка handle_show_entity_list)
    await show_entity_list(callback_query, state, entity_type="product", page=0)


async def handle_stock_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает просмотр списка Остатков."""
    await show_entity_list(callback_query, state, entity_type="stock", page=0)


async def handle_category_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает просмотр списка Категорий."""
    await show_entity_list(callback_query, state, entity_type="category", page=0)


async def handle_manufacturer_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает просмотр списка Производителей."""
    await show_entity_list(callback_query, state, entity_type="manufacturer", page=0)


async def handle_location_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Начинает просмотр списка Местоположений."""
    await show_entity_list(callback_query, state, entity_type="location", page=0)


# --- Router Registration ---
# Этот файл не содержит функции регистрации роутера для самого себя,
# т.к. его хэндлеры регистрируются в bot.py (Command) и admin_router (CallbackQuery)
# в определенном порядке относительно FSM и list/detail роутеров.
