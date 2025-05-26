# handlers/admin_list_detail_handlers_aiogram.py
import logging
from typing import Optional, Union, List

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

# Исправленный импорт для устранения ошибки "attempted relative import beyond top-level package"
# Предполагается, что 'utils' - это пакет в корне проекта, на одном уровне с 'handlers'
from utils import db

# Импорты для будущей полной реализации (можно раскомментировать и дополнить по мере необходимости)
# from .admin_constants_aiogram import ADMIN_MAIN_MENU_CALLBACK # Пример
# from ..utils.db import YourEntityType # Пример

logger = logging.getLogger(__name__)
admin_list_detail_router = Router(name="admin_list_detail_router")

async def _send_or_edit_message(
    target: Union[types.Message, types.CallbackQuery],
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    state: Optional[FSMContext] = None,
    parse_mode: Optional[str] = "HTML",
    message_id_to_edit: Optional[int] = None,
    bot_instance: Optional[Bot] = None # Явное указание экземпляра бота
):
    """
    Отправляет новое сообщение или редактирует существующее.
    Если предоставлен state, пытается извлечь 'last_bot_message_id' для редактирования.
    Если предоставлен message_id_to_edit, он имеет приоритет.
    Если target - CallbackQuery, по умолчанию редактируется сообщение этого callback, если не найден другой ID.
    """
    bot_to_use = bot_instance if bot_instance else target.bot

    chat_id: Optional[int] = None
    actual_message_id_to_edit: Optional[int] = message_id_to_edit

    if isinstance(target, types.Message):
        chat_id = target.chat.id
        if actual_message_id_to_edit is None and state:
            data = await state.get_data()
            actual_message_id_to_edit = data.get("last_bot_message_id")
    elif isinstance(target, types.CallbackQuery):
        if target.message is None:
            logger.error("CallbackQuery не имеет сообщения для редактирования или ответа.")
            return None
        chat_id = target.message.chat.id
        if actual_message_id_to_edit is None: # По умолчанию редактируем сообщение callback'а
            actual_message_id_to_edit = target.message.message_id
    else:
        logger.error(f"Неподдерживаемый тип target для _send_or_edit_message: {type(target)}")
        return None

    if actual_message_id_to_edit and chat_id:
        try:
            edited_message = await bot_to_use.edit_message_text(
                chat_id=chat_id,
                message_id=actual_message_id_to_edit,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            # logger.debug(f"Сообщение {actual_message_id_to_edit} в чате {chat_id} отредактировано.")
            if state: # Обновляем last_bot_message_id ID успешно отредактированного сообщения
                 await state.update_data(last_bot_message_id=edited_message.message_id)
            return edited_message
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось отредактировать сообщение {actual_message_id_to_edit} в чате {chat_id}: {e}. Попытка отправить новое сообщение.")
            if "message is not modified" in str(e).lower():
                logger.info("Сообщение не изменено, новое сообщение не отправляется.")
                # Возвращаем контекст исходного сообщения, если оно не было изменено
                current_message_context = target.message if isinstance(target, types.CallbackQuery) else target
                if state and current_message_context: # Убедимся, что last_bot_message_id в state актуален
                    await state.update_data(last_bot_message_id=current_message_context.message_id)
                return current_message_context
            # Для других ошибок (например, "message to edit not found") отправляем новое сообщение
            # Продолжение ниже для отправки нового сообщения
        except Exception as e:
            logger.error(f"Неожиданная ошибка при редактировании сообщения {actual_message_id_to_edit} в чате {chat_id}: {e}. Попытка отправить новое сообщение.")
            # Продолжение ниже для отправки нового сообщения

    # Отправка нового сообщения, если редактирование не удалось или не предполагалось
    new_sent_message: Optional[types.Message] = None
    if chat_id: # Убедимся, что chat_id определен
        if isinstance(target, types.CallbackQuery) and target.message: # Для CallbackQuery отвечаем на исходное сообщение
            new_sent_message = await bot_to_use.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif isinstance(target, types.Message): # Для Message также используем send_message
            new_sent_message = await bot_to_use.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
             # Если target не Message и не CallbackQuery с target.message (маловероятно после проверок выше)
             logger.error("Невозможно отправить новое сообщение: chat_id определен, но контекст target неясен.")
             return None
    else:
        logger.error("Невозможно отправить новое сообщение: chat_id не определен.")
        return None

    if new_sent_message and state:
        await state.update_data(last_bot_message_id=new_sent_message.message_id)
        # logger.debug(f"Новое сообщение {new_sent_message.message_id} отправлено в чат {chat_id}, ID сохранен в state.")
    elif not new_sent_message:
        logger.error("Новое сообщение не было отправлено.")

    return new_sent_message

# Entity configuration mapping
ENTITY_CONFIG = {
    "product": {
        "display_name": "Товары",
        "detail_prefix": "prod_detail:",
        "page_prefix": "prod_page:",
        "back_callback": "admin_products"
    },
    "stock": {
        "display_name": "Остатки",
        "detail_prefix": "stock_detail:",
        "page_prefix": "stock_page:",
        "back_callback": "admin_stock"
    },
    "category": {
        "display_name": "Категории",
        "detail_prefix": "cat_detail:",
        "page_prefix": "cat_page:",
        "back_callback": "admin_categories"
    },
    "manufacturer": {
        "display_name": "Производители",
        "detail_prefix": "man_detail:",
        "page_prefix": "man_page:",
        "back_callback": "admin_manufacturers"
    },
    "location": {
        "display_name": "Местоположения",
        "detail_prefix": "loc_detail:",
        "page_prefix": "loc_page:",
        "back_callback": "admin_locations"
    }
}

PAGE_SIZE = 10

async def show_entity_list(callback_query: types.CallbackQuery, state: FSMContext, entity_type: str, page: int = 0):
    """
    Универсальная функция для отображения списков сущностей с пагинацией (aiogram).
    
    Args:
        callback_query: CallbackQuery объект aiogram
        state: FSMContext для aiogram
        entity_type: тип сущности ('product', 'stock', 'category', 'manufacturer', 'location')
        page: номер страницы (начиная с 0)
    """
    # Сброс FSM состояния при показе списка
    current_state = await state.get_state()
    if current_state:
        logger.info(f"Сброс FSM при показе списка {entity_type} из состояния: {current_state}")
        await state.clear()
    
    # Проверяем, есть ли конфигурация для данного типа сущности
    if entity_type not in ENTITY_CONFIG:
        logger.error(f"Неизвестный тип сущности: {entity_type}")
        await callback_query.answer("❌ Ошибка: неизвестный тип сущности", show_alert=True)
        return
    
    config = ENTITY_CONFIG[entity_type]
    entity_name_plural = f"{entity_type}s" if entity_type != "category" else "categories"
    
    # Обеспечиваем, что page >= 0
    if page < 0:
        page = 0
    
    offset = page * PAGE_SIZE
    
    try:
        # Получаем общее количество элементов для расчета страниц
        total_count = db.get_entity_count(entity_name_plural)
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE if total_count > 0 else 1
        
        # Корректируем номер страницы, если он превышает максимальный
        if page >= total_pages and total_pages > 0:
            page = total_pages - 1
            offset = page * PAGE_SIZE
        
        # Получаем элементы для текущей страницы
        items = db.get_all_paginated(entity_name_plural, offset, PAGE_SIZE)
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка {entity_type}: {e}", exc_info=True)
        await callback_query.answer("❌ Произошла ошибка при загрузке списка", show_alert=True)
        return
    
    # Формируем ответ
    response_text = f"📋 **{config['display_name']}** (Стр. {page + 1}/{total_pages}, всего: {total_count}):\n\n"
    
    # Создаем inline клавиатуру
    keyboard_buttons = []
    
    if items:
        for item in items:
            item_id_str = ""
            item_display = ""
            
            if entity_type == 'product':
                item_id_str = str(item.id)
                item_display = f"📦 {item.name} (ID: {item.id})"
            elif entity_type == 'stock':
                # Stock имеет составной ключ product_id, location_id
                item_id_str = f"{item.product_id}_{item.location_id}"
                # Получаем названия для отображения
                try:
                    session = db.SessionLocal()
                    product_name = session.query(db.Product.name).filter_by(id=item.product_id).scalar() or 'Неизвестный товар'
                    location_name = session.query(db.Location.name).filter_by(id=item.location_id).scalar() or 'Неизвестное местоположение'
                    session.close()
                    item_display = f"📦 {product_name} @ {location_name} (кол-во: {item.quantity})"
                except Exception:
                    session.close()
                    item_display = f"📦 Товар ID:{item.product_id} @ Локация ID:{item.location_id} (кол-во: {item.quantity})"
            elif entity_type == 'category':
                item_id_str = str(item.id)
                item_display = f"📂 {item.name} (ID: {item.id})"
            elif entity_type == 'manufacturer':
                item_id_str = str(item.id)
                item_display = f"🏭 {item.name} (ID: {item.id})"
            elif entity_type == 'location':
                item_id_str = str(item.id)
                item_display = f"📍 {item.name} (ID: {item.id})"
            
            # Добавляем кнопку для детального просмотра
            detail_callback = f"{config['detail_prefix']}{item_id_str}"
            keyboard_buttons.append([types.InlineKeyboardButton(
                text=item_display,
                callback_data=detail_callback
            )])
    else:
        response_text += "Список пуст."
    
    # Добавляем кнопки пагинации
    pagination_buttons = []
    if page > 0:
        prev_callback = f"{config['page_prefix']}{page - 1}"
        pagination_buttons.append(types.InlineKeyboardButton(
            text="⬅️ Предыдущая",
            callback_data=prev_callback
        ))
    
    if page < total_pages - 1:
        next_callback = f"{config['page_prefix']}{page + 1}"
        pagination_buttons.append(types.InlineKeyboardButton(
            text="Следующая ➡️",
            callback_data=next_callback
        ))
    
    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([types.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=config['back_callback']
    )])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем/редактируем сообщение
    await _send_or_edit_message(callback_query, response_text, keyboard, state, parse_mode="Markdown")

async def show_entity_detail(callback_query: types.CallbackQuery, state: FSMContext, entity_type: str, entity_id_str: str):
    """
    Заглушка для функции детального просмотра сущности.
    TODO: Реализовать полную функциональность детального просмотра.
    """
    logger.info(f"Запрос детального просмотра {entity_type} с ID: {entity_id_str}")
    await callback_query.answer("🚧 Детальный просмотр в разработке", show_alert=True)

# TODO: Реализовать обработчики для детального просмотра (DETAIL)
# и соответствующих callback-обработчиков для редактирования и удаления.

def register_list_detail_handlers(router: Router):
    """
    Регистрирует обработчики списков и деталей сущностей в предоставленном роутере.
    """
    router.include_router(admin_list_detail_router)

logger.info("Router 'admin_list_detail_router', utility '_send_or_edit_message', and 'show_entity_list' are defined.")
