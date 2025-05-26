# Исправлен циклический импорт show_admin_main_menu_aiogram

import logging
from typing import Union
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем константы из admin_constants_aiogram.py
# Предполагается, что следующие константы определены в handlers/admin_constants_aiogram.py:
from .admin_constants_aiogram import (
    ADMIN_BACK_MAIN,
    ADMIN_PRODUCTS_CALLBACK, ADMIN_STOCK_CALLBACK, ADMIN_CATEGORIES_CALLBACK,
    ADMIN_MANUFACTURERS_CALLBACK, ADMIN_LOCATIONS_CALLBACK,
    PRODUCT_ADD_CALLBACK, PRODUCT_LIST_CALLBACK,
    STOCK_ADD_CALLBACK, STOCK_LIST_CALLBACK,
    CATEGORY_ADD_CALLBACK, CATEGORY_LIST_CALLBACK,
    MANUFACTURER_ADD_CALLBACK, MANUFACTURER_LIST_CALLBACK,
    LOCATION_ADD_CALLBACK, LOCATION_LIST_CALLBACK,
)

# НЕ ИМПОРТИРУЕМ show_admin_main_menu_aiogram НА ВЕРХНЕМ УРОВНЕ,
# ЧТОБЫ ИЗБЕЖАТЬ ЦИКЛИЧЕСКОГО ИМПОРТА.
# Функция будет импортирована локально в хэндлере handle_back_to_main_menu.


# Импортируем хелпер для отправки/редактирования сообщения
# Предполагается, что _send_or_edit_message определен в handlers.admin_list_detail_handlers_aiogram
# (как в предоставленном референсе "aiogram admin menu fsm crud handlers.md")
try:
    from .admin_list_detail_handlers_aiogram import _send_or_edit_message
except ImportError:
    # Если admin_list_detail_handlers_aiogram еще не создан, определяем хелпер здесь
    logging.warning("admin_list_detail_handlers_aiogram не найден, используя локальный _send_or_edit_message")
    async def _send_or_edit_message(
        target: Union[Message, CallbackQuery],
        text: str,
        reply_markup: InlineKeyboardMarkup = None,
        parse_mode: str = "MarkdownV2"
    ):
        """Хелпер для отправки нового сообщения или редактирования существующего."""
        if isinstance(target, CallbackQuery):
            try:
                # Проверяем, что сообщение существует, прежде чем пытаться редактировать
                if target.message:
                     await target.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                     # Если target.message нет (редкий случай для callback_query), отправляем новое сообщение
                     await target.answer("Не удалось обновить сообщение. Отправлено новое.", show_alert=False)
                     await target.bot.send_message(target.from_user.id, text, reply_markup=reply_markup, parse_mode=parse_mode)

            except Exception as e:
                logging.error(f"Ошибка при редактировании сообщения: {e}. Отправляем новое.")
                # Отвечаем на колбэк перед отправкой нового сообщения
                await target.answer("Не удалось обновить сообщение. Отправлено новое.", show_alert=False)
                await target.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif isinstance(target, Message):
            await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


# Создаем экземпляр роутера для меню сущностей
admin_entity_menus_router = Router(name="admin_entity_menus_router")

# Инициализируем логгер
logger = logging.getLogger(__name__)

# --- Вспомогательная функция для создания клавиатуры меню сущности ---
def _get_entity_menu_keyboard(
    entity_name_singular: str,
    entity_name_plural: str,
    add_callback: str,
    list_callback: str
) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для меню управления конкретной сущностью.

    Args:
        entity_name_singular: Название сущности в единственном числе (например, "Товар").
        entity_name_plural: Название сущности во множественном числе (например, "Товаров").
        add_callback: Callback-дата для кнопки "Добавить {entity_name_singular}".
        list_callback: Callback-дата для кнопки "Просмотреть список {entity_name_plural}".

    Returns:
        Объект InlineKeyboardMarkup.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"➕ Добавить {entity_name_singular}", callback_data=add_callback))
    builder.row(InlineKeyboardButton(text=f"📋 Просмотреть список {entity_name_plural}", callback_data=list_callback))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в главное админ-меню", callback_data=ADMIN_BACK_MAIN))
    return builder.as_markup()


# --- Функции отображения меню сущностей ---

async def show_products_menu_aiogram(target: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает меню управления Товарами."""
    reply_markup = _get_entity_menu_keyboard(
        entity_name_singular="Товар",
        entity_name_plural="Товаров",
        add_callback=PRODUCT_ADD_CALLBACK,
        list_callback=PRODUCT_LIST_CALLBACK
    )
    await _send_or_edit_message(target, "📚 **Меню управления Товарами**\nВыберите действие:", reply_markup)
    # await state.clear() # Очистка состояния может быть выполнена в хэндлере, вызывающем эту функцию,
                          # или при переходе в главное меню


async def show_stock_menu_aiogram(target: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает меню управления Остатками."""
    reply_markup = _get_entity_menu_keyboard(
        entity_name_singular="Остаток",
        entity_name_plural="Остатков",
        add_callback=STOCK_ADD_CALLBACK,
        list_callback=STOCK_LIST_CALLBACK
    )
    await _send_or_edit_message(target, "📦 **Меню управления Остатками**\nВыберите действие:", reply_markup)
    # await state.clear()


async def show_categories_menu_aiogram(target: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает меню управления Категориями."""
    reply_markup = _get_entity_menu_keyboard(
        entity_name_singular="Категорию",
        entity_name_plural="Категорий",
        add_callback=CATEGORY_ADD_CALLBACK,
        list_callback=CATEGORY_LIST_CALLBACK
    )
    await _send_or_edit_message(target, "📂 **Меню управления Категориями**\nВыберите действие:", reply_markup)
    # await state.clear()


async def show_manufacturers_menu_aiogram(target: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает меню управления Производителями."""
    reply_markup = _get_entity_menu_keyboard(
        entity_name_singular="Производителя",
        entity_name_plural="Производителей",
        add_callback=MANUFACTURER_ADD_CALLBACK,
        list_callback=MANUFACTURER_LIST_CALLBACK
    )
    await _send_or_edit_message(target, "🏭 **Меню управления Производителями**\nВыберите действие:", reply_markup)
    # await state.clear()


async def show_locations_menu_aiogram(target: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает меню управления Локациями."""
    reply_markup = _get_entity_menu_keyboard(
        entity_name_singular="Локацию",
        entity_name_plural="Локаций",
        add_callback=LOCATION_ADD_CALLBACK,
        list_callback=LOCATION_LIST_CALLBACK
    )
    await _send_or_edit_message(target, "📍 **Меню управления Локациями**\nВыберите действие:", reply_markup)
    # await state.clear()


# --- Callback-обработчики навигации из главного меню в меню сущностей ---
# Эти хэндлеры вызываются при нажатии кнопок в главном админ-меню

@admin_entity_menus_router.callback_query(F.data == ADMIN_PRODUCTS_CALLBACK)
async def handle_show_products_menu(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает колбэк ADMIN_PRODUCTS_CALLBACK и показывает меню товаров."""
    await callback.answer() # Обязательно отвечаем на колбэк
    await show_products_menu_aiogram(callback, state)

@admin_entity_menus_router.callback_query(F.data == ADMIN_STOCK_CALLBACK)
async def handle_show_stock_menu(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает колбэк ADMIN_STOCK_CALLBACK и показывает меню остатков."""
    await callback.answer()
    await show_stock_menu_aiogram(callback, state)

@admin_entity_menus_router.callback_query(F.data == ADMIN_CATEGORIES_CALLBACK)
async def handle_show_categories_menu(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает колбэк ADMIN_CATEGORIES_CALLBACK и показывает меню категорий."""
    await callback.answer()
    await show_categories_menu_aiogram(callback, state)

@admin_entity_menus_router.callback_query(F.data == ADMIN_MANUFACTURERS_CALLBACK)
async def handle_show_manufacturers_menu(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает колбэк ADMIN_MANUFACTURERS_CALLBACK и показывает меню производителей."""
    await callback.answer()
    await show_manufacturers_menu_aiogram(callback, state)

@admin_entity_menus_router.callback_query(F.data == ADMIN_LOCATIONS_CALLBACK)
async def handle_show_locations_menu(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает колбэк ADMIN_LOCATIONS_CALLBACK и показывает меню локаций."""
    await callback.answer()
    await show_locations_menu_aiogram(callback, state)


# --- Заглушечные callback-обработчики для кнопок действий (Добавить, Просмотреть список) ---
# Эти хэндлеры будут заменены реальной логикой FSM или показа списков на следующих этапах.
# Важно: при реализации реальной логики, эти заглушки должны быть заменены
# или их фильтры должны быть удалены/изменены.

@admin_entity_menus_router.callback_query(F.data == PRODUCT_ADD_CALLBACK)
async def handle_product_add_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Добавить Товар'."""
    await callback.answer("Обработчик 'Добавить Товар' будет реализован позже.")
    # TODO: Здесь будет вызов функции запуска FSM диалога добавления товара

@admin_entity_menus_router.callback_query(F.data == PRODUCT_LIST_CALLBACK)
async def handle_product_list_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Просмотреть список Товаров'."""
    await callback.answer("Обработчик 'Просмотреть список Товаров' будет реализован позже.")
    # TODO: Здесь будет вызов функции показа списка товаров (возможно, из admin_list_detail_handlers_aiogram)

@admin_entity_menus_router.callback_query(F.data == STOCK_ADD_CALLBACK)
async def handle_stock_add_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Добавить Остаток'."""
    await callback.answer("Обработчик 'Добавить Остаток' будет реализован позже.")
    # TODO: Здесь будет вызов функции запуска FSM диалога добавления остатка

@admin_entity_menus_router.callback_query(F.data == STOCK_LIST_CALLBACK)
async def handle_stock_list_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Просмотреть список Остатков'."""
    await callback.answer("Обработчик 'Просмотреть список Остатков' будет реализован позже.")
    # TODO: Здесь будет вызов функции показа списка остатков

@admin_entity_menus_router.callback_query(F.data == CATEGORY_ADD_CALLBACK)
async def handle_category_add_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Добавить Категорию'."""
    await callback.answer("Обработчик 'Добавить Категорию' будет реализован позже.")
    # TODO: Здесь будет вызов функции запуска FSM диалога добавления категории

@admin_entity_menus_router.callback_query(F.data == CATEGORY_LIST_CALLBACK)
async def handle_category_list_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Просмотреть список Категорий'."""
    await callback.answer("Обработчик 'Просмотреть список Категорий' будет реализован позже.")
    # TODO: Здесь будет вызов функции показа списка категорий

@admin_entity_menus_router.callback_query(F.data == MANUFACTURER_ADD_CALLBACK)
async def handle_manufacturer_add_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Добавить Производителя'."""
    await callback.answer("Обработчик 'Добавить Производителя' будет реализован позже.")
    # TODO: Здесь будет вызов функции запуска FSM диалога добавления производителя

@admin_entity_menus_router.callback_query(F.data == MANUFACTURER_LIST_CALLBACK)
async def handle_manufacturer_list_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Просмотреть список Производителей'."""
    await callback.answer("Обработчик 'Просмотреть список Производителей' будет реализован позже.")
    # TODO: Здесь будет вызов функции показа списка производителей

@admin_entity_menus_router.callback_query(F.data == LOCATION_ADD_CALLBACK)
async def handle_location_add_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Добавить Локацию'."""
    await callback.answer("Обработчик 'Добавить Локацию' будет реализован позже.")
    # TODO: Здесь будет вызов функции запуска FSM диалога добавления локации

@admin_entity_menus_router.callback_query(F.data == LOCATION_LIST_CALLBACK)
async def handle_location_list_placeholder(callback: CallbackQuery, state: FSMContext):
    """Заглушка для действия 'Просмотреть список Локаций'."""
    await callback.answer("Обработчик 'Просмотреть список Локаций' будет реализован позже.")
    # TODO: Здесь будет вызов функции показа списка локаций


# --- Callback-обработчик кнопки "Назад в главное меню" ---
# Эта кнопка присутствует в меню каждой сущности и ведет обратно в главное админ-меню.

@admin_entity_menus_router.callback_query(F.data == ADMIN_BACK_MAIN)
async def handle_back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбэк ADMIN_BACK_MAIN, очищает FSM состояние
    и показывает главное админ-меню.
    """
    await callback.answer() # Обязательно отвечаем на колбэк

    # --- ЛОКАЛЬНЫЙ ИМПОРТ show_admin_main_menu_aiogram ---
    # Этот импорт выполняется только при вызове функции handle_back_to_main_menu,
    # а не при загрузке модуля, что разрывает циклический импорт.
    try:
        from .admin_handlers_aiogram import show_admin_main_menu_aiogram as show_main_menu
        logger.info("Локальный импорт show_admin_main_menu_aiogram успешен.")
    except ImportError as e:
        logger.error(f"Ошибка локального импорта show_admin_main_menu_aiogram: {e}. Невозможно вернуться в главное меню.")
        await _send_or_edit_message(
            callback,
            "❌ Ошибка: Не удалось загрузить главное админ-меню из-за проблемы с импортом.\n"
            "Пожалуйста, проверьте логи бота.",
            reply_markup=None # Убираем кнопки, если невозможно вернуться
        )
        return # Прерываем выполнение функции, если импорт не удался

    # Очищаем состояние FSM при возврате в главное меню
    await state.clear()
    logger.debug("FSM состояние очищено при возврате в главное меню.")

    # Вызываем функцию показа главного меню
    # Используем target=callback для редактирования сообщения, если это возможно
    await show_main_menu(target=callback, state=state, is_callback=True)
    logger.info("Вызвана show_admin_main_menu_aiogram.")


# Note: Регистрация обработчиков выполнена с помощью декораторов @admin_entity_menus_router.<тип>.register(...)
# Функция register_admin_entity_menu_handlers из референса больше не нужна,
# так как роутер admin_entity_menus_router уже содержит все зарегистрированные хэндлеры.

# Этот роутер admin_entity_menus_router должен быть включен в главный диспетчер или
# основной админский роутер в вашем файле bot.py или другом файле сборки роутеров.
# Пример в bot.py: dp.include_router(admin_entity_menus_router)
# Если у вас есть главный админский роутер (например, в handlers/admin_handlers_aiogram.py),
# то включать нужно там: admin_main_router.include_router(admin_entity_menus_router)
