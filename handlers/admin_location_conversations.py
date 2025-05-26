# your_bot/handlers/admin_location_conversations.py
# ConversationHandler'ы для добавления, поиска, обновления и удаления местоположений

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Импорт констант
from .admin_constants import (
    ADMIN_LOCATIONS_ADD, ADMIN_LOCATIONS_FIND, ADMIN_LOCATIONS_UPDATE,
    ADMIN_BACK_LOCATIONS_MENU, CONVERSATION_END,
    ADMIN_DETAIL_PREFIX, ADMIN_EDIT_PREFIX,
    ADMIN_LOCATIONS_DELETE_CONFIRM,
    ADMIN_DELETE_EXECUTE_PREFIX
    # Импорт констант состояний не требуется, используем локальные
)
from .admin_menus import show_locations_menu, is_admin
# from .admin_menus import handle_locations_detail # Не импортируем, возврат в список


# Импорт функций базы данных
from utils import db

logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler для местоположений ---
# Add Location States
(LOCATION_ADD_NAME_STATE,) = range(1)

# Find Location States
(LOCATION_FIND_QUERY_STATE,) = range(1, 2)

# Update Location States
(LOCATION_UPDATE_ID_STATE, LOCATION_UPDATE_NAME_STATE) = range(2, 4)

# Delete Location States
(LOCATION_DELETE_CONFIRM_STATE,) = range(4, 5)


# --- Функции отмены ConversationHandler (общие для всех операций с местоположениями) ---
async def cancel_location_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущую операцию с местоположениями (добавление, поиск, обновление или удаление)."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return CONVERSATION_END

    if 'new_location' in context.user_data:
        del context.user_data['new_location']
    if 'updated_location_data' in context.user_data:
        del context.user_data['updated_location_data']
    if 'location_to_delete_id' in context.user_data:
         del context.user_data['location_to_delete_id']


    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text("Операция с местоположением отменена.")
        except Exception:
             chat_id = update.effective_chat.id
             await context.bot.send_message(chat_id=chat_id, text="Операция с местоположением отменена.")
    elif update.message:
        await update.message.reply_text("Операция с местоположением отменена.")

    await show_locations_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Добавление местоположения ---

async def add_location_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога добавления местоположения. Запрашивает название."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске add_location_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог добавления местоположения.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* нового местоположения:",
        parse_mode='Markdown'
    )
    return LOCATION_ADD_NAME_STATE

async def handle_location_name_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия местоположения при добавлении и выполняет добавление."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите *название* местоположения:", parse_mode='Markdown')
        return LOCATION_ADD_NAME_STATE # Остаемся в текущем состоянии

    try:
        # Вызов функции добавления из utils.db
        added_location = db.add_location(name=name)

        if added_location:
            await update.message.reply_text(f"✅ Местоположение '{added_location.name}' (ID: {added_location.id}) успешно добавлено!")
        else:
             # db.add_location уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при добавлении местоположения '{name}'. Возможно, местоположение с таким названием уже существует.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.add_location: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при добавлении местоположения.")

    await show_locations_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Поиск местоположения ---

async def find_location_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога поиска местоположения. Запрашивает поисковый запрос."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске find_location_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог поиска местоположения.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* местоположения или его часть для поиска:",
        parse_mode='Markdown'
    )
    return LOCATION_FIND_QUERY_STATE

async def handle_location_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод поискового запроса и выполняет поиск."""
    query_text = update.message.text.strip()
    if not query_text:
         await update.message.reply_text("Поисковый запрос не может быть пустым. Введите *название* или его часть:", parse_mode='Markdown')
         return LOCATION_FIND_QUERY_STATE

    try:
        # Вызов функции поиска из utils.db
        results = db.find_locations_by_name(query_text)

        response_text = f"Результаты поиска по запросу '{query_text}':\n\n"
        if results:
            for loc in results:
                 response_text += f"📍 ID: `{loc.id}`\n" \
                                  f"  Название: *{loc.name}*\n\n"
        else:
            response_text += "Местоположения по вашему запросу не найдены."

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при вызове db.find_locations_by_name: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при поиске местоположений.")

    await show_locations_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Обновление местоположения ---

async def update_location_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога обновления местоположения. Запрашивает ID местоположения."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    # Если entry point вызван из кнопки "Редактировать" на странице деталей
    # Callback формат: admin_locations_detail_ID_edit_ID
    if ADMIN_EDIT_PREFIX in query.data:
         try:
             # Парсим ID местоположения из callback_data
             parts = query.data.split(ADMIN_EDIT_PREFIX)
             location_id_str = parts[-1]
             location_id = int(location_id_str)
             logger.info(f"Запущено обновление местоположения из деталей. ID: {location_id}")

             # Пытаемся убрать клавиатуру из сообщения деталей
             if query.message:
                  try:
                      await query.message.edit_reply_markup(reply_markup=None)
                  except Exception:
                       logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске update_location_entry")


             # Переходим сразу к загрузке местоположения
             temp_message = type('obj', (object,), {'text': str(location_id), 'from_user': update.effective_user, 'chat': update.effective_chat})()
             temp_update = type('obj', (object,), {'message': temp_message, 'effective_user': update.effective_user, 'effective_chat': update.effective_chat, 'callback_query': None})()
             return await handle_location_update_id(temp_update, context)

         except (ValueError, IndexError) as e:
             logger.error(f"Не удалось распарсить ID местоположения из edit callback: {query.data}", exc_info=True)
             await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования.")
             await show_locations_menu(update, context)
             return CONVERSATION_END
         except Exception as e:
              logger.error(f"Непредвиденная ошибка при запуске обновления из деталей: {e}", exc_info=True)
              await query.edit_message_text("❌ Произошла ошибка при запуске диалога редактирования.")
              await show_locations_menu(update, context)
              return CONVERSATION_END


    # Если entry point вызван из меню
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске update_location_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог обновления местоположения.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *ID местоположения*, которое хотите обновить:",
        parse_mode='Markdown'
    )
    context.user_data['updated_location_data'] = {}
    return LOCATION_UPDATE_ID_STATE

async def handle_location_update_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID местоположения для обновления."""
    location_id_text = update.message.text.strip()
    try:
        location_id = int(location_id_text)
        location = db.get_location_by_id(location_id)

        if location:
            context.user_data['updated_location_data']['id'] = location_id
            context.user_data['updated_location_data']['original_name'] = location.name

            summary = (
                f"Найдено местоположение ID `{location.id}`: *{location.name}*.\n\n"
                "Введите новое *название* местоположения (можно пропустить, введя '='):" # Добавлена возможность оставить старое значение
            )
            await update.message.reply_text(summary, parse_mode='Markdown')

            return LOCATION_UPDATE_NAME_STATE
        else:
            await update.message.reply_text(
                f"Местоположение с ID `{location_id_text}` не найдено. Пожалуйста, введите корректный *ID местоположения* для обновления:",
                parse_mode='Markdown'
            )
            return LOCATION_UPDATE_ID_STATE

    except ValueError:
        await update.message.reply_text("ID местоположения должен быть целым числом. Пожалуйста, введите корректный *ID местоположения*:", parse_mode='Markdown')
        return LOCATION_UPDATE_ID_STATE
    except Exception as e:
        logger.error(f"Ошибка при получении местоположения по ID {location_id_text} для обновления: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске местоположения.")
        await cancel_location_operation(update, context)
        return CONVERSATION_END


async def handle_location_update_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового названия местоположения и выполняет обновление."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите новое *название* местоположения (можно пропустить, введя '='):", parse_mode='Markdown')
        return LOCATION_UPDATE_NAME_STATE

    location_id_to_update = context.user_data['updated_location_data'].get('id')
    if not location_id_to_update:
        await update.message.reply_text("Ошибка: Не удалось получить ID местоположения для обновления.")
        if 'updated_location_data' in context.user_data: del context.user_data['updated_location_data']
        await show_locations_menu(update, context)
        return CONVERSATION_END

    # Если пользователь ввел '=', оставляем старое значение
    if name == '=':
         new_name = context.user_data['updated_location_data'].get('original_name')
         await update.message.reply_text("Название оставлено без изменений.")
    else:
         new_name = name

    try:
        update_data = {'name': new_name}
        updated_location = db.update_location(location_id_to_update, update_data)

        if updated_location:
            await update.message.reply_text(f"✅ Местоположение ID `{location_id_to_update}` успешно обновлено! Новое название: *{updated_location.name}*", parse_mode='Markdown')
        else:
             # db.update_location уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при обновлении местоположения ID `{location_id_to_update}`. Возможно, местоположение с таким названием уже существует.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.update_location для ID {location_id_to_update}: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при обновлении местоположения.")

    if 'updated_location_data' in context.user_data:
        del context.user_data['updated_location_data']

    await show_locations_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Удаление местоположения ---

async def delete_location_confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога подтверждения удаления местоположения."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID местоположения из callback_data: admin_locations_detail_ID_delete_confirm_ID
        # ID для удаления - это последний ID после ADMIN_DELETE_CONFIRM_PREFIX
        parts = query.data.split(ADMIN_DELETE_CONFIRM_PREFIX)
        location_id_str = parts[-1]
        location_id = int(location_id_str)
        context.user_data['location_to_delete_id'] = location_id

        # Пытаемся убрать клавиатуру из сообщения деталей
        if query.message:
             try:
                 await query.message.edit_reply_markup(reply_markup=None)
             except Exception:
                  logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске delete_location_confirm_entry")


        location = db.get_location_by_id(location_id)
        if not location:
             await query.edit_message_text(f"❌ Ошибка: Местоположение с ID `{location_id}` не найдено для удаления.")
             await show_locations_menu(update, context)
             return CONVERSATION_END


        confirmation_text = (
            f"Вы уверены, что хотите удалить местоположение?\n\n"
            f"📍 ID: `{location.id}`\n"
            f"Название: *{location.name}*\n\n"
            f"*ВНИМАНИЕ:* Удаление местоположения может удалить связанные записи остатков!" # Предупреждение о связях
        )

        # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID
        # entity "location" жестко прописан
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"location{ADMIN_DELETE_EXECUTE_PREFIX}{location_id}")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data=ADMIN_BACK_LOCATIONS_MENU)] # Отмена возвращает в меню местоположений
        ])

        await query.edit_message_text(confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

        return LOCATION_DELETE_CONFIRM_STATE

    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось распарсить ID местоположения из delete confirm callback: {query.data}", exc_info=True)
        await query.edit_