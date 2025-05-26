# your_bot/handlers/admin_manufacturer_conversations.py
# ConversationHandler'ы для добавления, поиска, обновления и удаления производителей

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
    ADMIN_MANUFACTURERS_ADD, ADMIN_MANUFACTURERS_FIND, ADMIN_MANUFACTURERS_UPDATE,
    ADMIN_BACK_MANUFACTURERS_MENU, CONVERSATION_END,
    ADMIN_DETAIL_PREFIX, ADMIN_EDIT_PREFIX,
    ADMIN_MANUFACTURERS_DELETE_CONFIRM,
    ADMIN_DELETE_EXECUTE_PREFIX
    # Импорт констант состояний не требуется, используем локальные
)
from .admin_menus import show_manufacturers_menu, is_admin
# from .admin_menus import handle_manufacturers_detail # Не импортируем, возврат в список


# Импорт функций базы данных
from utils import db

logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler для производителей ---
# Add Manufacturer States
(MANUFACTURER_ADD_NAME_STATE,) = range(1)

# Find Manufacturer States
(MANUFACTURER_FIND_QUERY_STATE,) = range(1, 2)

# Update Manufacturer States
(MANUFACTURER_UPDATE_ID_STATE, MANUFACTURER_UPDATE_NAME_STATE) = range(2, 4)

# Delete Manufacturer States
(MANUFACTURER_DELETE_CONFIRM_STATE,) = range(4, 5)


# --- Функции отмены ConversationHandler (общие для всех операций с производителями) ---
async def cancel_manufacturer_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущую операцию с производителями (добавление, поиск, обновление или удаление)."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return CONVERSATION_END

    if 'new_manufacturer' in context.user_data:
        del context.user_data['new_manufacturer']
    if 'updated_manufacturer_data' in context.user_data:
        del context.user_data['updated_manufacturer_data']
    if 'manufacturer_to_delete_id' in context.user_data:
         del context.user_data['manufacturer_to_delete_id']

    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text("Операция с производителем отменена.")
        except Exception:
             chat_id = update.effective_chat.id
             await context.bot.send_message(chat_id=chat_id, text="Операция с производителем отменена.")
    elif update.message:
        await update.message.reply_text("Операция с производителем отменена.")

    await show_manufacturers_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Добавление производителя ---

async def add_manufacturer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога добавления производителя. Запрашивает название."""
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
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске add_manufacturer_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог добавления производителя.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* нового производителя:",
        parse_mode='Markdown'
    )
    return MANUFACTURER_ADD_NAME_STATE

async def handle_manufacturer_name_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия производителя при добавлении и выполняет добавление."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите *название* производителя:", parse_mode='Markdown')
        return MANUFACTURER_ADD_NAME_STATE # Остаемся в текущем состоянии

    try:
        # Вызов функции добавления из utils.db
        added_manufacturer = db.add_manufacturer(name=name)

        if added_manufacturer:
            await update.message.reply_text(f"✅ Производитель '{added_manufacturer.name}' (ID: {added_manufacturer.id}) успешно добавлен!")
        else:
             # db.add_manufacturer уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при добавлении производителя '{name}'. Возможно, производитель с таким названием уже существует.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.add_manufacturer: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при добавлении производителя.")

    await show_manufacturers_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Поиск производителя ---

async def find_manufacturer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога поиска производителя. Запрашивает поисковый запрос."""
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
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске find_manufacturer_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог поиска производителя.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* производителя или его часть для поиска:",
        parse_mode='Markdown'
    )
    return MANUFACTURER_FIND_QUERY_STATE

async def handle_manufacturer_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод поискового запроса и выполняет поиск."""
    query_text = update.message.text.strip()
    if not query_text:
         await update.message.reply_text("Поисковый запрос не может быть пустым. Введите *название* или его часть:", parse_mode='Markdown')
         return MANUFACTURER_FIND_QUERY_STATE

    try:
        # Вызов функции поиска из utils.db
        results = db.find_manufacturers_by_name(query_text)

        response_text = f"Результаты поиска по запросу '{query_text}':\n\n"
        if results:
            for m in results:
                 response_text += f"🏭 ID: `{m.id}`\n" \
                                  f"  Название: *{m.name}*\n\n"
        else:
            response_text += "Производители по вашему запросу не найдены."

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при вызове db.find_manufacturers_by_name: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при поиске производителей.")

    await show_manufacturers_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Обновление производителя ---

async def update_manufacturer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога обновления производителя. Запрашивает ID производителя."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    # Если entry point вызван из кнопки "Редактировать" на странице деталей
    # Callback формат: admin_manufacturers_detail_ID_edit_ID
    if ADMIN_EDIT_PREFIX in query.data:
         try:
             # Парсим ID производителя из callback_data
             parts = query.data.split(ADMIN_EDIT_PREFIX)
             manufacturer_id_str = parts[-1]
             manufacturer_id = int(manufacturer_id_str)
             logger.info(f"Запущено обновление производителя из деталей. ID: {manufacturer_id}")

             # Пытаемся убрать клавиатуру из сообщения деталей
             if query.message:
                  try:
                      await query.message.edit_reply_markup(reply_markup=None)
                  except Exception:
                       logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске update_manufacturer_entry")

             # Переходим сразу к загрузке производителя
             temp_message = type('obj', (object,), {'text': str(manufacturer_id), 'from_user': update.effective_user, 'chat': update.effective_chat})()
             temp_update = type('obj', (object,), {'message': temp_message, 'effective_user': update.effective_user, 'effective_chat': update.effective_chat, 'callback_query': None})()
             return await handle_manufacturer_update_id(temp_update, context)

         except (ValueError, IndexError) as e:
             logger.error(f"Не удалось распарсить ID производителя из edit callback: {query.data}", exc_info=True)
             await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования.")
             await show_manufacturers_menu(update, context)
             return CONVERSATION_END
         except Exception as e:
              logger.error(f"Непредвиденная ошибка при запуске обновления из деталей: {e}", exc_info=True)
              await query.edit_message_text("❌ Произошла ошибка при запуске диалога редактирования.")
              await show_manufacturers_menu(update, context)
              return CONVERSATION_END


    # Если entry point вызван из меню
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске update_manufacturer_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог обновления производителя.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *ID производителя*, которого хотите обновить:",
        parse_mode='Markdown'
    )
    context.user_data['updated_manufacturer_data'] = {}
    return MANUFACTURER_UPDATE_ID_STATE

async def handle_manufacturer_update_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID производителя для обновления."""
    manufacturer_id_text = update.message.text.strip()
    try:
        manufacturer_id = int(manufacturer_id_text)
        manufacturer = db.get_manufacturer_by_id(manufacturer_id)

        if manufacturer:
            context.user_data['updated_manufacturer_data']['id'] = manufacturer_id
            context.user_data['updated_manufacturer_data']['original_name'] = manufacturer.name

            summary = (
                f"Найден производитель ID `{manufacturer.id}`: *{manufacturer.name}*.\n\n"
                "Введите новое *название* производителя (можно пропустить, введя '='):" # Добавлена возможность оставить старое значение
            )
            await update.message.reply_text(summary, parse_mode='Markdown')

            return MANUFACTURER_UPDATE_NAME_STATE
        else:
            await update.message.reply_text(
                f"Производитель с ID `{manufacturer_id_text}` не найден. Пожалуйста, введите корректный *ID производителя* для обновления:",
                parse_mode='Markdown'
            )
            return MANUFACTURER_UPDATE_ID_STATE

    except ValueError:
        await update.message.reply_text("ID производителя должен быть целым числом. Пожалуйста, введите корректный *ID производителя*:", parse_mode='Markdown')
        return MANUFACTURER_UPDATE_ID_STATE
    except Exception as e:
        logger.error(f"Ошибка при получении производителя по ID {manufacturer_id_text} для обновления: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске производителя.")
        await cancel_manufacturer_operation(update, context)
        return CONVERSATION_END


async def handle_manufacturer_update_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового названия производителя и выполняет обновление."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите новое *название* производителя (можно пропустить, введя '='):", parse_mode='Markdown')
        return MANUFACTURER_UPDATE_NAME_STATE

    manufacturer_id_to_update = context.user_data['updated_manufacturer_data'].get('id')
    if not manufacturer_id_to_update:
        await update.message.reply_text("Ошибка: Не удалось получить ID производителя для обновления.")
        if 'updated_manufacturer_data' in context.user_data: del context.user_data['updated_manufacturer_data']
        await show_manufacturers_menu(update, context)
        return CONVERSATION_END

    # Если пользователь ввел '=', оставляем старое значение
    if name == '=':
         new_name = context.user_data['updated_manufacturer_data'].get('original_name')
         await update.message.reply_text("Название оставлено без изменений.")
    else:
         new_name = name

    try:
        update_data = {'name': new_name}
        updated_manufacturer = db.update_manufacturer(manufacturer_id_to_update, update_data)

        if updated_manufacturer:
            await update.message.reply_text(f"✅ Производитель ID `{manufacturer_id_to_update}` успешно обновлен! Новое название: *{updated_manufacturer.name}*", parse_mode='Markdown')
        else:
             # db.update_manufacturer уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при обновлении производителя ID `{manufacturer_id_to_update}`. Возможно, производитель с таким названием уже существует.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.update_manufacturer для ID {manufacturer_id_to_update}: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при обновлении производителя.")

    if 'updated_manufacturer_data' in context.user_data:
        del context.user_data['updated_manufacturer_data']

    await show_manufacturers_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Удаление производителя ---

async def delete_manufacturer_confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога подтверждения удаления производителя."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID производителя из callback_data: admin_manufacturers_detail_ID_delete_confirm_ID
        # ID для удаления - это последний ID после ADMIN_DELETE_CONFIRM_PREFIX
        parts = query.data.split(ADMIN_DELETE_CONFIRM_PREFIX)
        manufacturer_id_str = parts[-1]
        manufacturer_id = int(manufacturer_id_str)
        context.user_data['manufacturer_to_delete_id'] = manufacturer_id

        # Пытаемся убрать клавиатуру из сообщения деталей
        if query.message:
             try:
                 await query.message.edit_reply_markup(reply_markup=None)
             except Exception:
                  logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске delete_manufacturer_confirm_entry")


        manufacturer = db.get_manufacturer_by_id(manufacturer_id)
        if not manufacturer:
             await query.edit_message_text(f"❌ Ошибка: Производитель с ID `{manufacturer_id}` не найден для удаления.")
             await show_manufacturers_menu(update, context)
             return CONVERSATION_END


        confirmation_text = (
            f"Вы уверены, что хотите удалить производителя?\n\n"
            f"🏭 ID: `{manufacturer.id}`\n"
            f"Название: *{manufacturer.name}*\n\n"
            f"*ВНИМАНИЕ:* Удаление производителя может сделать связанные товары сиротами или удалить их (в зависимости от настроек БД)!" # Предупреждение о связях
        )

        # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID
        # entity "manufacturer" жестко прописан
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"manufacturer{ADMIN_DELETE_EXECUTE_PREFIX}{manufacturer_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=ADMIN_BACK_MANUFACTURERS_MENU)] # Отмена возвращает в меню производителей
        ])

        await query.edit_message_text(confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

        return MANUFACTURER_DELETE_CONFIRM_STATE

    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось распарсить ID производителя из delete confirm callback: {query.data}", exc_info=True)
        await query.edit_message_text("❌ Ошибка: Неверный формат ID для удаления.")
        await show_manufacturers_menu(update, context)
        return CONVERSATION_END
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске подтверждения удаления производителя: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при подготовке к удалению производителя.")
        await show_manufacturers_menu(update, context)
        return CONVERSATION_END


async def handle_manufacturer_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет удаление производителя из БД."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    manufacturer_id = None # Инициализация для логгирования

    try:
        # Парсим ID производителя из callback_data: manufacturer_delete_execute_ID
        parts = query.data.split(ADMIN_DELETE_EXECUTE_PREFIX)
        manufacturer_id_str = parts[-1]
        manufacturer_id = int(manufacturer_id_str)

        # Опционально: Проверяем, совпадает ли ID с сохраненным
        # saved_id = context.user_data.get('manufacturer_to_delete_id')
        # if saved_id is None or saved_id != manufacturer_id:
        #      logger.error(f"Несоответствие сохраненного ({saved_id}) и полученного ({manufacturer_id}) ID при выполнении удаления производителя.")
        #      await query.edit_message_text("❌ Ошибка: Несоответствие ID при выполнении удаления.")
        #      await show_manufacturers_menu(update, context)
        #      if 'manufacturer_to_delete_id' in context.user_data: del context.user_data['manufacturer_to_delete_id']
        #      return CONVERSATION_END

        # Удаляем кнопки подтверждения
        try:
             await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
             logger.debug("Не удалось убрать клавиатуру после выполнения удаления производителя")


        # Вызываем функцию удаления из utils.db
        success = db.delete_manufacturer(manufacturer_id)

        if success:
            await query.message.reply_text(f"✅ Производитель ID `{manufacturer_id}` успешно удален!")
        else:
             # db.delete_manufacturer уже логирует причину
             await query.message.reply_text(f"❌ Не удалось удалить производителя ID `{manufacturer_id}`. Возможно, существуют связанные товары или произошла другая ошибка.")

    except (ValueError, IndexError) as e:
         logger.error(f"Не удалось распарсить ID производителя из delete execute callback: {query.data}", exc_info=True)
         await query.edit_message_text("❌ Ошибка: Неверный формат ID при выполнении удаления.")
    except Exception as e:
         logger.error(f"Непредвиденная ошибка при выполнении удаления производителя ID {manufacturer_id}: {e}", exc_info=True)
         await query.message.reply_text("❌ Произошла непредвиденная ошибка при удалении производителя.")

    if 'manufacturer_to_delete_id' in context.user_data:
         del context.user_data['manufacturer_to_delete_id']

    await show_manufacturers_menu(update, context)
    return CONVERSATION_END


# --- Определение ConversationHandler'ов для Производителей ---

add_manufacturer_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_manufacturer_entry, pattern=f'^{ADMIN_MANUFACTURERS_ADD}$')],
    states={
        MANUFACTURER_ADD_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manufacturer_name_add)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_manufacturer_operation, pattern=f'^{ADMIN_BACK_MANUFACTURERS_MENU}$'),
        CommandHandler("cancel", cancel_manufacturer_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_manufacturer_operation)
    ],
     map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

find_manufacturer_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(find_manufacturer_entry, pattern=f'^{ADMIN_MANUFACTURERS_FIND}$')],
    states={
        MANUFACTURER_FIND_QUERY_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manufacturer_search_query)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_manufacturer_operation, pattern=f'^{ADMIN_BACK_MANUFACTURERS_MENU}$'),
        CommandHandler("cancel", cancel_manufacturer_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_manufacturer_operation)
    ],
     map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

# Паттерн для entry_points обновления
# Из меню: ^admin_manufacturers_update$
# Из деталей: ^admin_manufacturers_detail_ID_edit_ID$
update_manufacturer_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(update_manufacturer_entry, pattern=f'^{ADMIN_MANUFACTURERS_UPDATE}$'),
        CallbackQueryHandler(update_manufacturer_entry, pattern=f'^{ADMIN_MANUFACTURERS_DETAIL}\d+{ADMIN_EDIT_PREFIX}\d+$')
    ],
    states={
        MANUFACTURER_UPDATE_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manufacturer_update_id)],
        MANUFACTURER_UPDATE_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manufacturer_update_name)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_manufacturer_operation, pattern=f'^{ADMIN_BACK_MANUFACTURERS_MENU}$'),
        CommandHandler("cancel", cancel_manufacturer_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_manufacturer_operation)
    ],
     map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

# Паттерн для entry_points удаления
# С деталей: ^admin_manufacturers_detail_ID_delete_confirm_ID$
delete_manufacturer_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_manufacturer_confirm_entry, pattern=f'^{ADMIN_MANUFACTURERS_DETAIL}\d+{ADMIN_DELETE_CONFIRM_PREFIX}\d+$')
    ],
    states={
        MANUFACTURER_DELETE_CONFIRM_STATE: [
             # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID
             # entity "manufacturer" жестко прописан в колбэке кнопки "Да, удалить"
             CallbackQueryHandler(handle_manufacturer_delete_execute, pattern=f'^manufacturer{ADMIN_DELETE_EXECUTE_PREFIX}\d+$'), # Кнопка "Да, удалить"
             CallbackQueryHandler(cancel_manufacturer_operation, pattern=f'^{ADMIN_BACK_MANUFACTURERS_MENU}$') # Кнопка "Нет, отмена"
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_manufacturer_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_manufacturer_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)
