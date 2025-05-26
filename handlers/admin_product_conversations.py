# your_bot/handlers/admin_product_conversations.py
# ConversationHandler'ы для добавления, поиска, обновления и удаления товаров

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CommandHandler 
)
from decimal import Decimal, InvalidOperation

# Импорт констант
from .admin_constants import (
    ADMIN_PRODUCTS_ADD, ADMIN_PRODUCTS_FIND, ADMIN_PRODUCTS_UPDATE,
    ADMIN_BACK_PRODUCTS_MENU, CONVERSATION_END,
    ADMIN_DETAIL_PREFIX, ADMIN_EDIT_PREFIX, # Используем префиксы для парсинга
    ADMIN_PRODUCTS_DELETE_CONFIRM, # Entry point для ConvHandler удаления
    ADMIN_DELETE_EXECUTE_PREFIX, # Префикс для колбэка выполнения удаления
    # Импорт констант состояний (локальные определения предпочтительнее для ясности в файле,
    # но используем импорт из constants для Entry Points и Fallbacks)
    PRODUCT_ADD_NAME, PRODUCT_ADD_DESCRIPTION, PRODUCT_ADD_PRICE,
    PRODUCT_ADD_CATEGORY, PRODUCT_ADD_MANUFACTURER,
    PRODUCT_ADD_CONFIRM, PRODUCT_FIND_QUERY,
    PRODUCT_UPDATE_ID, PRODUCT_UPDATE_NAME, PRODUCT_UPDATE_DESCRIPTION,
    PRODUCT_UPDATE_PRICE, PRODUCT_UPDATE_CATEGORY_ID, PRODUCT_UPDATE_MANUFACTURER_ID,
    PRODUCT_UPDATE_CONFIRM
)
from .admin_menus import show_products_menu, is_admin # Импорт функций меню и проверки админа
from .admin_menus import handle_products_detail # Импорт хэндлера деталей для возврата

# Импорт функций базы данных
from utils import db

logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler для удаления товара ---
PRODUCT_DELETE_CONFIRM_STATE = 0 # Локальное состояние для ожидания подтверждения


# --- Функции отмены ConversationHandler (общие для всех операций с товарами) ---
async def cancel_product_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущую операцию с товарами (добавление, поиск, обновление или удаление)."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return CONVERSATION_END

    # Удаляем сохраненные данные, если они есть
    if 'new_product' in context.user_data:
        del context.user_data['new_product']
    if 'updated_product_data' in context.user_data:
         del context.user_data['updated_product_data']
    if 'product_to_delete_id' in context.user_data:
         del context.user_data['product_to_delete_id']

    # Отправляем сообщение об отмене
    if update.callback_query:
        await update.callback_query.answer()
        try:
            # Пытаемся отредактировать сообщение, которое инициировало отмену (например, кнопку "Назад")
            await update.callback_query.edit_message_text("Операция с товаром отменена.")
        except Exception:
             # Если сообщение уже изменено или удалено (например, отмена через /cancel)
             chat_id = update.effective_chat.id
             await context.bot.send_message(chat_id=chat_id, text="Операция с товаром отменена.")

    elif update.message: # Отмена через команду /cancel
         await update.message.reply_text("Операция с товаром отменена.")


    # Возвращаемся в меню товаров
    await show_products_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Добавление товара ---
# (Без изменений, кроме использования локальных или импортированных из constants состояний)
async def add_product_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога добавления товара."""
    # ... (код handle_products_add из ref) ...
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог добавления товара.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* нового товара:",
        parse_mode='Markdown'
    )

    context.user_data['new_product'] = {}
    return PRODUCT_ADD_NAME

async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия товара."""
    # ... (код handle_product_name из ref) ...
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите *название* товара:", parse_mode='Markdown')
        return PRODUCT_ADD_NAME

    context.user_data['new_product']['name'] = name
    await update.message.reply_text("Введите *описание* товара:", parse_mode='Markdown')
    return PRODUCT_ADD_DESCRIPTION

async def handle_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод описания товара."""
    # ... (код handle_product_description из ref) ...
    description = update.message.text.strip()
    context.user_data['new_product']['description'] = description

    await update.message.reply_text("Введите *цену* товара (например, 100.50). Используйте точку как разделитель десятичных знаков:", parse_mode='Markdown')
    return PRODUCT_ADD_PRICE

async def handle_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод цены товара."""
    # ... (код handle_product_price из ref) ...
    price_text = update.message.text.strip().replace(',', '.')
    try:
        price = Decimal(price_text)
        if price < 0:
            await update.message.reply_text("Цена не может быть отрицательной. Введите корректную *цену*:", parse_mode='Markdown')
            return PRODUCT_ADD_PRICE

        context.user_data['new_product']['price'] = price

        await update.message.reply_text(
            "Введите *ID категории* для товара.\n"
            "Для просмотра списка категорий временно выйдите из диалога и воспользуйтесь меню \"Список категорий\".",
            parse_mode='Markdown'
        )
        return PRODUCT_ADD_CATEGORY

    except InvalidOperation:
        await update.message.reply_text("Пожалуйста, введите корректное число для цены (например, 100 или 100.50).", parse_mode='Markdown')
        return PRODUCT_ADD_PRICE

async def handle_product_category_id_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
     """Обрабатывает ввод ID категории товара при добавлении."""
     # ... (код handle_product_category_id_add из ref) ...
     category_id_text = update.message.text.strip()
     try:
         category_id = int(category_id_text)
         category = db.get_category_by_id(category_id)

         if category:
             context.user_data['new_product']['category_id'] = category_id
             context.user_data['new_product']['category_name'] = category.name

             await update.message.reply_text(
                 f"Категория найдена: *{category.name}*.\n"
                 "Теперь введите *ID производителя* для товара.\n"
                 "Для просмотра списка производителей временно выйдите из диалога и воспользуйтесь меню \"Список производителей\".",
                 parse_mode='Markdown'
             )
             return PRODUCT_ADD_MANUFACTURER
         else:
             await update.message.reply_text(
                 f"Категория с ID `{category_id_text}` не найдена. Пожалуйста, введите корректный *ID категории*:",
                 parse_mode='Markdown'
             )
             return PRODUCT_ADD_CATEGORY

     except ValueError:
         await update.message.reply_text("ID категории должен быть целым числом. Пожалуйста, введите корректный *ID категории*:", parse_mode='Markdown')
         return PRODUCT_ADD_CATEGORY
     except Exception as e:
         logger.error(f"Ошибка при поиске категории по ID {category_id_text} при добавлении товара: {e}", exc_info=True)
         await update.message.reply_text("❌ Произошла ошибка при поиске категории.")
         await cancel_product_operation(update, context)
         return CONVERSATION_END


async def handle_product_manufacturer_id_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID производителя при добавлении и предлагает подтверждение."""
    # ... (код handle_product_manufacturer_id_add из ref) ...
    manufacturer_id_text = update.message.text.strip()
    try:
        manufacturer_id = int(manufacturer_id_text)
        manufacturer = db.get_manufacturer_by_id(manufacturer_id)

        if manufacturer:
            context.user_data['new_product']['manufacturer_id'] = manufacturer_id
            context.user_data['new_product']['manufacturer_name'] = manufacturer.name

            product_data = context.user_data['new_product']
            summary = (
                "Проверьте данные нового товара:\n\n"
                f"Название: *{product_data.get('name', 'Не указано')}*\n"
                f"Описание: {product_data.get('description', 'Не указано')}\n"
                f"Цена: *{product_data.get('price', 'Не указано')}*\n"
                f"Категория ID: `{product_data.get('category_id', 'Не указано')}` (*{product_data.get('category_name', 'Не найдено')}*)\n"
                f"Производитель ID: `{product_data.get('manufacturer_id', 'Не указано')}` (*{product_data.get('manufacturer_name', 'Не найдено')}*)\n\n"
                "Подтвердите добавление товара."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data="add_product_confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data=ADMIN_BACK_PRODUCTS_MENU)]
            ])

            await update.message.reply_text(summary, reply_markup=keyboard, parse_mode='Markdown')
            return PRODUCT_ADD_CONFIRM

        else:
            await update.message.reply_text(
                f"Производитель с ID `{manufacturer_id_text}` не найден. Пожалуйста, введите корректный *ID производителя*:",
                parse_mode='Markdown'
            )
            return PRODUCT_ADD_MANUFACTURER

    except ValueError:
        await update.message.reply_text("ID производителя должен быть целым числом. Пожалуйста, введите корректный *ID производителя*:", parse_mode='Markdown')
        return PRODUCT_ADD_MANUFACTURER
    except Exception as e:
        logger.error(f"Ошибка при поиске производителя по ID {manufacturer_id_text} при добавлении товара: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске производителя.")
        await cancel_product_operation(update, context)
        return CONVERSATION_END


async def handle_product_add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершает диалог добавления товара, сохраняет в БД и возвращается в меню."""
    # ... (код handle_product_add_confirm из ref) ...
    query = update.callback_query
    await query.answer()

    product_data = context.user_data.pop('new_product', None)

    if not product_data:
        await query.edit_message_text("Ошибка: Данные для добавления товара потеряны.")
        await show_products_menu(update, context)
        return CONVERSATION_END

    try:
        await query.edit_message_reply_markup(reply_markup=None) # Убираем кнопки

        added_product = db.add_product(
            name=product_data.get('name'),
            description=product_data.get('description'),
            price=product_data.get('price'),
            category_id=product_data.get('category_id'),
            manufacturer_id=product_data.get('manufacturer_id')
        )

        if added_product:
            await query.message.reply_text(f"✅ Товар '{added_product.name}' (ID: {added_product.id}) успешно добавлен!")
        else:
             await query.message.reply_text(f"❌ Ошибка при добавлении товара '{product_data.get('name', '')}'. Возможно, товар с таким названием уже существует или указаны неверные ID категории/производителя.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.add_product: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Произошла непредвиденная ошибка при добавлении товара.")

    await show_products_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Поиск товара ---
# (Без изменений)
async def find_product_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога поиска товара."""
    # ... (код find_product_entry из ref) ...
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог поиска товара.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* товара или его часть для поиска:",
        parse_mode='Markdown'
    )
    return PRODUCT_FIND_QUERY

async def handle_product_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод поискового запроса и выполняет поиск."""
    # ... (код handle_product_search_query из ref) ...
    query_text = update.message.text.strip()
    if not query_text:
         await update.message.reply_text("Поисковый запрос не может быть пустым. Введите *название* или его часть:", parse_mode='Markdown')
         return PRODUCT_FIND_QUERY

    try:
        results = db.find_products_by_name(query_text)

        response_text = f"Результаты поиска по запросу '{query_text}':\n\n"
        if results:
            for p in results:
                 description_short = (p.description[:50] + '...') if p.description and len(p.description) > 50 else (p.description or 'Нет описания')
                 response_text += f"📦 ID: `{p.id}`\n" \
                                  f"  Название: *{p.name}*\n" \
                                  f"  Цена: {p.price} руб.\n" \
                                  f"  Описание: {description_short}\n\n"
        else:
            response_text += "Товары по вашему запросу не найдены."

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при вызове db.find_products_by_name: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при поиске товаров.")

    await show_products_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Обновление товара ---
# (Без изменений, кроме использования локальных или импортированных из constants состояний)
async def update_product_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога обновления товара. Запрашивает ID товара."""
    # ... (код update_product_entry из ref) ...
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    # Если entry point вызван из кнопки "Редактировать" на странице деталей
    if ADMIN_EDIT_PREFIX in query.data:
        try:
             # Парсим ID товара из callback_data: admin_products_edit_ID
             parts = query.data.split(ADMIN_EDIT_PREFIX)
             product_id = int(parts[-1])
             logger.info(f"Запущено обновление товара из деталей. ID: {product_id}")
             # Переходим сразу к загрузке товара
             # Имитируем сообщение с ID для перенаправления в handle_product_update_id
             # Это немного костыль, но позволяет переиспользовать логику handle_product_update_id
             update.message = type('obj', (object,), {'text': str(product_id)})() # Создаем имитацию Message
             return await handle_product_update_id(update, context)

        except (ValueError, IndexError) as e:
             logger.error(f"Не удалось распарсить ID товара из edit callback: {query.data}", exc_info=True)
             await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования.")
             await show_products_menu(update, context)
             return CONVERSATION_END
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при запуске обновления из деталей: {e}", exc_info=True)
             await query.edit_message_text("❌ Произошла ошибка при запуске диалога редактирования.")
             await show_products_menu(update, context)
             return CONVERSATION_END


    # Если entry point вызван из кнопки "Обновить товар по ID" в меню
    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог обновления товара.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *ID товара*, который хотите обновить:",
        parse_mode='Markdown'
    )
    context.user_data['updated_product_data'] = {}
    return PRODUCT_UPDATE_ID


async def handle_product_update_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID товара для обновления."""
    # ... (код handle_product_update_id из ref) ...
    product_id_text = update.message.text.strip()
    try:
        product_id = int(product_id_text)
        product = db.get_product_by_id(product_id)

        if product:
            context.user_data['updated_product_data']['id'] = product_id
            # Сохраняем текущие данные для удобства и сравнения
            context.user_data['updated_product_data']['original'] = {
                 'name': product.name,
                 'description': product.description,
                 'price': product.price,
                 'category_id': product.category_id,
                 'manufacturer_id': product.manufacturer_id,
            }

            summary = (
                f"Найден товар ID `{product.id}`:\n\n"
                f"Название: *{product.name}*\n"
                f"Описание: {product.description or 'Нет описания'}\n"
                f"Цена: {product.price} руб.\n"
                f"Категория ID: `{product.category_id}`\n"
                f"Производитель ID: `{product.manufacturer_id}`\n\n"
                "Введите новое *название* товара:"
            )
            await update.message.reply_text(summary, parse_mode='Markdown')

            return PRODUCT_UPDATE_NAME
        else:
            await update.message.reply_text(
                f"Товар с ID `{product_id_text}` не найден. Пожалуйста, введите корректный *ID товара* для обновления:",
                parse_mode='Markdown'
            )
            return PRODUCT_UPDATE_ID

    except ValueError:
        await update.message.reply_text("ID товара должен быть целым числом. Пожалуйста, введите корректный *ID товара*:", parse_mode='Markdown')
        return PRODUCT_UPDATE_ID
    except Exception as e:
         logger.error(f"Ошибка при получении товара по ID {product_id_text} для обновления: {e}", exc_info=True)
         await update.message.reply_text("❌ Произошла ошибка при поиске товара.")
         await cancel_product_operation(update, context)
         return CONVERSATION_END


async def handle_product_update_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового названия товара."""
    # ... (код handle_product_update_name из ref) ...
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите новое *название* товара:", parse_mode='Markdown')
        return PRODUCT_UPDATE_NAME

    context.user_data['updated_product_data']['name'] = name
    await update.message.reply_text("Введите новое *описание* товара (можно пропустить, введя '-'):", parse_mode='Markdown')
    return PRODUCT_UPDATE_DESCRIPTION


async def handle_product_update_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового описания товара."""
    # ... (код handle_product_update_description из ref) ...
    description = update.message.text.strip()
    context.user_data['updated_product_data']['description'] = description if description != '-' else None

    await update.message.reply_text("Введите новую *цену* товара (например, 100.50). Используйте точку как разделитель десятичных знаков:", parse_mode='Markdown')
    return PRODUCT_UPDATE_PRICE


async def handle_product_update_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод новой цены товара."""
    # ... (код handle_product_update_price из ref) ...
    price_text = update.message.text.strip().replace(',', '.')
    try:
        price = Decimal(price_text)
        if price < 0:
            await update.message.reply_text("Цена не может быть отрицательной. Введите корректную *цену*:", parse_mode='Markdown')
            return PRODUCT_UPDATE_PRICE

        context.user_data['updated_product_data']['price'] = price

        await update.message.reply_text(
            "Введите новый *ID категории* для товара:\n"
            "Для просмотра списка категорий временно выйдите из диалога и воспользуйтесь меню \"Список категорий\".",
            parse_mode='Markdown'
        )
        return PRODUCT_UPDATE_CATEGORY_ID

    except InvalidOperation:
        await update.message.reply_text("Пожалуйста, введите корректное число для цены (например, 100 или 100.50).", parse_mode='Markdown')
        return PRODUCT_UPDATE_PRICE

async def handle_product_update_category_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
     """Обрабатывает ввод нового ID категории товара при обновлении."""
     # ... (код handle_product_update_category_id из ref) ...
     category_id_text = update.message.text.strip()
     try:
         category_id = int(category_id_text)
         category = db.get_category_by_id(category_id)

         if category:
             context.user_data['updated_product_data']['category_id'] = category_id
             context.user_data['updated_product_data']['category_name'] = category.name

             await update.message.reply_text(
                 f"Категория найдена: *{category.name}*.\n"
                 "Теперь введите новый *ID производителя* для товара.\n"
                 "Для просмотра списка производителей временно выйдите из диалога и воспользуйтесь меню \"Список производителей\".",
                 parse_mode='Markdown'
             )
             return PRODUCT_UPDATE_MANUFACTURER_ID
         else:
             await update.message.reply_text(
                 f"Категория с ID `{category_id_text}` не найдена. Пожалуйста, введите корректный *ID категории*:",
                 parse_mode='Markdown'
             )
             return PRODUCT_UPDATE_CATEGORY_ID

     except ValueError:
         await update.message.reply_text("ID категории должен быть целым числом. Пожалуйста, введите корректный *ID категории*:", parse_mode='Markdown')
         return PRODUCT_UPDATE_CATEGORY_ID
     except Exception as e:
        logger.error(f"Ошибка при поиске категории по ID {category_id_text} при обновлении товара: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске категории.")
        await cancel_product_operation(update, context)
        return CONVERSATION_END


async def handle_product_update_manufacturer_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового ID производителя при обновлении и предлагает подтверждение."""
    # ... (код handle_product_update_manufacturer_id из ref) ...
    manufacturer_id_text = update.message.text.strip()
    try:
        manufacturer_id = int(manufacturer_id_text)
        manufacturer = db.get_manufacturer_by_id(manufacturer_id)

        if manufacturer:
            context.user_data['updated_product_data']['manufacturer_id'] = manufacturer_id
            context.user_data['updated_product_data']['manufacturer_name'] = manufacturer.name

            product_data = context.user_data['updated_product_data']
            original_data = context.user_data['updated_product_data'].get('original', {})

            summary = (
                f"Обновляемый товар ID `{product_data.get('id', 'N/A')}`:\n\n"
                f"Название: *{original_data.get('name', 'Не указано')}* -> *{product_data.get('name', 'Не указано')}*\n"
                f"Описание: {original_data.get('description', 'Не указано')} -> {product_data.get('description', 'Не указано')}\n"
                f"Цена: *{original_data.get('price', 'Не указано')}* -> *{product_data.get('price', 'Не указано')}*\n"
                f"Категория ID: `{original_data.get('category_id', 'Не указано')}` -> `{product_data.get('category_id', 'Не указано')}` (*{product_data.get('category_name', 'Не найдено')}*)\n"
                f"Производитель ID: `{original_data.get('manufacturer_id', 'Не указано')}` -> `{product_data.get('manufacturer_id', 'Не указано')}` (*{product_data.get('manufacturer_name', 'Не найдено')}*)\n\n"
                "Подтвердите обновление товара."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data="update_product_confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data=ADMIN_BACK_PRODUCTS_MENU)]
            ])

            await update.message.reply_text(summary, reply_markup=keyboard, parse_mode='Markdown')
            return PRODUCT_UPDATE_CONFIRM

        else:
            await update.message.reply_text(
                f"Производитель с ID `{manufacturer_id_text}` не найден. Пожалуйста, введите корректный *ID производителя*:",
                parse_mode='Markdown'
            )
            return PRODUCT_UPDATE_MANUFACTURER_ID

    except ValueError:
        await update.message.reply_text("ID производителя должен быть целым числом. Пожалуйста, введите корректный *ID производителя*:", parse_mode='Markdown')
        return PRODUCT_UPDATE_MANUFACTURER_ID
    except Exception as e:
        logger.error(f"Ошибка при поиске производителя по ID {manufacturer_id_text} при обновлении товара: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске производителя.")
        await cancel_product_operation(update, context)
        return CONVERSATION_END


async def handle_product_update_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет обновление товара в БД и завершает диалог."""
    # ... (код handle_product_update_confirm из ref) ...
    query = update.callback_query
    await query.answer()

    product_data = context.user_data.pop('updated_product_data', None)

    if not product_data or 'id' not in product_data:
        await query.edit_message_text("Ошибка: Данные для обновления товара потеряны.")
        await show_products_menu(update, context)
        return CONVERSATION_END

    try:
        await query.edit_message_reply_markup(reply_markup=None) # Убираем кнопки

        product_id = product_data['id']
        update_data = {k: v for k, v in product_data.items() if k not in ['id', 'original', 'category_name', 'manufacturer_name']}

        updated_product = db.update_product(product_id, update_data)

        if updated_product:
            await query.message.reply_text(f"✅ Товар ID `{product_id}` успешно обновлен!")
        else:
             await query.message.reply_text(f"❌ Ошибка при обновлении товара ID `{product_id}`. Возможно, указаны некорректные данные (например, занятое название или несуществующая категория/производитель).")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.update_product для ID {product_data.get('id')}: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Произошла непредвиденная ошибка при обновлении товара.")

    await show_products_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Удаление товара ---

async def delete_product_confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога подтверждения удаления товара."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID товара из callback_data: admin_products_delete_confirm_ID
        parts = query.data.split(ADMIN_DELETE_CONFIRM_PREFIX)
        product_id = int(parts[-1])
        context.user_data['product_to_delete_id'] = product_id # Сохраняем ID для последующего шага

        # Получаем информацию о товаре для отображения в сообщении подтверждения
        product = db.get_product_by_id(product_id)
        if not product:
             await query.edit_message_text(f"❌ Ошибка: Товар с ID `{product_id}` не найден для удаления.")
             # Возвращаемся в меню товаров
             await show_products_menu(update, context)
             return CONVERSATION_END

        confirmation_text = (
            f"Вы уверены, что хотите удалить товар?\n\n"
            f"📦 ID: `{product.id}`\n"
            f"Название: *{product.name}*\n\n"
            f"*ВНИМАНИЕ:* Удаление товара также может удалить связанные остатки!" # Предупреждение о связях
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"product{ADMIN_DELETE_EXECUTE_PREFIX}{product_id}")], # Callback для выполнения удаления
            [InlineKeyboardButton("❌ Нет, отмена", callback_data=ADMIN_BACK_PRODUCTS_MENU)] # Отмена возвращает в меню товаров
        ])

        # Редактируем сообщение с деталями товара, чтобы показать запрос подтверждения
        await query.edit_message_text(confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

        return PRODUCT_DELETE_CONFIRM_STATE # Переход в состояние ожидания подтверждения

    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось распарсить ID товара из delete confirm callback: {query.data}", exc_info=True)
        await query.edit_message_text("❌ Ошибка: Неверный формат ID для удаления.")
        await show_products_menu(update, context)
        return CONVERSATION_END
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске подтверждения удаления товара: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при подготовке к удалению товара.")
        await show_products_menu(update, context)
        return CONVERSATION_END


async def handle_product_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет удаление товара из БД."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID товара из callback_data: product_delete_execute_ID
        parts = query.data.split(ADMIN_DELETE_EXECUTE_PREFIX)
        product_id = int(parts[-1])
        # Проверяем, совпадает ли ID с сохраненным (опционально, для дополнительной проверки)
        # saved_id = context.user_data.get('product_to_delete_id')
        # if saved_id is None or saved_id != product_id:
        #      await query.edit_message_text("❌ Ошибка: Несоответствие ID при удалении.")
        #      await show_products_menu(update, context)
        #      return CONVERSATION_END

        # Удаляем кнопки подтверждения
        await query.edit_message_reply_markup(reply_markup=None)

        # Вызываем функцию удаления из utils.db
        success = db.delete_product(product_id)

        if success:
            await query.message.reply_text(f"✅ Товар ID `{product_id}` успешно удален!")
        else:
             # db.delete_product уже логирует причину (например, IntegrityError)
             await query.message.reply_text(f"❌ Не удалось удалить товар ID `{product_id}`. Возможно, существуют связанные остатки или произошла другая ошибка.")

    except (ValueError, IndexError) as e:
         logger.error(f"Не удалось распарсить ID товара из delete execute callback: {query.data}", exc_info=True)
         await query.edit_message_text("❌ Ошибка: Неверный формат ID при выполнении удаления.")
    except Exception as e:
         logger.error(f"Непредвиденная ошибка при выполнении удаления товара ID {product_id}: {e}", exc_info=True)
         await query.message.reply_text("❌ Произошла непредвиденная ошибка при удалении товара.")

    # Очищаем user_data
    if 'product_to_delete_id' in context.user_data:
         del context.user_data['product_to_delete_id']

    # Возвращаемся в меню товаров
    await show_products_menu(update, context)
    return CONVERSATION_END


# --- Определение ConversationHandler'ов для Товаров ---

add_product_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_product_entry, pattern=f'^{ADMIN_PRODUCTS_ADD}$')],
    states={
        PRODUCT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_name)],
        PRODUCT_ADD_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_description)],
        PRODUCT_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_price)],
        PRODUCT_ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_category_id_add)],
        PRODUCT_ADD_MANUFACTURER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_manufacturer_id_add)],
        PRODUCT_ADD_CONFIRM: [CallbackQueryHandler(handle_product_add_confirm, pattern='^add_product_confirm$')],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_product_operation, pattern=f'^{ADMIN_BACK_PRODUCTS_MENU}$'),
        CommandHandler("cancel", cancel_product_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_product_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

find_product_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(find_product_entry, pattern=f'^{ADMIN_PRODUCTS_FIND}$')],
    states={
        PRODUCT_FIND_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_search_query)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_product_operation, pattern=f'^{ADMIN_BACK_PRODUCTS_MENU}$'),
        CommandHandler("cancel", cancel_product_operation)
    ],
     map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

update_product_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(update_product_entry, pattern=f'^{ADMIN_PRODUCTS_UPDATE}$'), # Из меню
        CallbackQueryHandler(update_product_entry, pattern=f'^{ADMIN_PRODUCTS_DETAIL}\d+{ADMIN_EDIT_PREFIX}\d+$') # Из кнопки "Редактировать" на странице деталей
    ],
    states={
        PRODUCT_UPDATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_id)],
        PRODUCT_UPDATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_name)],
        PRODUCT_UPDATE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_description)],
        PRODUCT_UPDATE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_price)],
        PRODUCT_UPDATE_CATEGORY_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_category_id)],
        PRODUCT_UPDATE_MANUFACTURER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_update_manufacturer_id)],
        PRODUCT_UPDATE_CONFIRM: [CallbackQueryHandler(handle_product_update_confirm, pattern='^update_product_confirm$')],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_product_operation, pattern=f'^{ADMIN_BACK_PRODUCTS_MENU}$'),
        CommandHandler("cancel", cancel_product_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_product_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

delete_product_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_product_confirm_entry, pattern=f'^{ADMIN_PRODUCTS_DETAIL}\d+{ADMIN_DELETE_CONFIRM_PREFIX}\d+$') # Из кнопки "Удалить" на странице деталей
    ],
    states={
        PRODUCT_DELETE_CONFIRM_STATE: [
             CallbackQueryHandler(handle_product_delete_execute, pattern=f'^product{ADMIN_DELETE_EXECUTE_PREFIX}\d+$'), # Кнопка "Да, удалить"
             CallbackQueryHandler(cancel_product_operation, pattern=f'^{ADMIN_BACK_PRODUCTS_MENU}$') # Кнопка "Нет, отмена"
        ],
    },
    fallbacks=[
        # Отмена по команде /cancel в любом состоянии диалога удаления
        CommandHandler("cancel", cancel_product_operation),
        # Отмена по любому другому текстовому сообщению
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_product_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)
