# your_bot/handlers/admin_category_conversations.py
# ConversationHandler'ы для добавления, поиска, обновления и удаления категорий

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

# Импорт констант
from .admin_constants import (
    ADMIN_CATEGORIES_ADD, ADMIN_CATEGORIES_FIND, ADMIN_CATEGORIES_UPDATE,
    ADMIN_BACK_CATEGORIES_MENU, CONVERSATION_END,
    ADMIN_DETAIL_PREFIX, ADMIN_EDIT_PREFIX,
    ADMIN_CATEGORIES_DELETE_CONFIRM,
    ADMIN_DELETE_EXECUTE_PREFIX
    # Импорт констант состояний не требуется, используем локальные
)
from .admin_menus import show_categories_menu, is_admin
# from .admin_menus import handle_categories_detail # Не импортируем, возврат в список


# Импорт функций базы данных
from utils import db

logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler для категорий ---
# Add Category States
(CATEGORY_ADD_NAME_STATE, CATEGORY_ADD_PARENT_ID_STATE) = range(2)

# Find Category States
(CATEGORY_FIND_QUERY_STATE,) = range(2, 3)

# Update Category States
(CATEGORY_UPDATE_ID_STATE, CATEGORY_UPDATE_NAME_STATE, CATEGORY_UPDATE_PARENT_ID_STATE) = range(3, 6)

# Delete Category States
(CATEGORY_DELETE_CONFIRM_STATE,) = range(6, 7)


# --- Функции отмены ConversationHandler (общие для всех операций с категориями) ---
async def cancel_category_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущую операцию с категориями (добавление, поиск, обновление или удаление)."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return CONVERSATION_END

    if 'new_category' in context.user_data:
        del context.user_data['new_category']
    if 'updated_category_data' in context.user_data:
        del context.user_data['updated_category_data']
    if 'category_to_delete_id' in context.user_data:
         del context.user_data['category_to_delete_id']

    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text("Операция с категорией отменена.")
        except Exception:
             chat_id = update.effective_chat.id
             await context.bot.send_message(chat_id=chat_id, text="Операция с категорией отменена.")

    elif update.message:
        await update.message.reply_text("Операция с категорией отменена.")

    await show_categories_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Добавление категории ---

async def add_category_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога добавления категории. Запрашивает название."""
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
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске add_category_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог добавления категории.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* новой категории:",
        parse_mode='Markdown'
    )

    context.user_data['new_category'] = {}
    return CATEGORY_ADD_NAME_STATE


async def handle_category_name_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия категории при добавлении."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите *название* категории:", parse_mode='Markdown')
        return CATEGORY_ADD_NAME_STATE # Остаемся в текущем состоянии

    context.user_data['new_category']['name'] = name

    await update.message.reply_text(
        "Введите *ID родительской категории*, если есть (можно пропустить, введя '-'):\n"
        "Для просмотра списка категорий временно выйдите из диалога (/cancel) и воспользуйтесь меню \"Список категорий\".",
        parse_mode='Markdown'
    )
    return CATEGORY_ADD_PARENT_ID_STATE


async def handle_category_parent_id_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID родительской категории при добавлении и выполняет добавление."""
    parent_id_text = update.message.text.strip()
    parent_id = None

    if parent_id_text != '-':
        try:
            parent_id = int(parent_id_text)
            parent_category = db.get_category_by_id(parent_id)
            if not parent_category:
                await update.message.reply_text(
                    f"Родительская категория с ID `{parent_id_text}` не найдена. Пожалуйста, введите корректный *ID родительской категории* или '-' чтобы пропустить:",
                    parse_mode='Markdown'
                )
                return CATEGORY_ADD_PARENT_ID_STATE # Остаемся в текущем состоянии
        except ValueError:
            await update.message.reply_text("ID родительской категории должен быть целым числом или '-'. Пожалуйста, введите корректный *ID* или '-':", parse_mode='Markdown')
            return CATEGORY_ADD_PARENT_ID_STATE
        except Exception as e:
             logger.error(f"Ошибка при поиске родительской категории по ID {parent_id_text} при добавлении: {e}", exc_info=True)
             await update.message.reply_text("❌ Произошла ошибка при поиске родительской категории.")
             await cancel_category_operation(update, context)
             return CONVERSATION_END


    category_name = context.user_data['new_category'].get('name')
    if not category_name: # Проверка на всякий случай
        await update.message.reply_text("Ошибка: Название категории не было сохранено.")
        # Очищаем user_data и возвращаемся в меню
        if 'new_category' in context.user_data: del context.user_data['new_category']
        await show_categories_menu(update, context)
        return CONVERSATION_END

    try:
        # Вызов функции добавления из utils.db
        added_category = db.add_category(name=category_name, parent_id=parent_id)

        if added_category:
            parent_info = f" (родитель: ID `{parent_id}`)" if parent_id else ""
            await update.message.reply_text(f"✅ Категория '{added_category.name}' (ID: {added_category.id}){parent_info} успешно добавлена!")
        else:
             # db.add_category уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при добавлении категории '{category_name}'. Возможно, категория с таким названием уже существует.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.add_category: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при добавлении категории.")

    # Очищаем user_data
    if 'new_category' in context.user_data:
        del context.user_data['new_category']

    # Возвращаемся в меню категорий
    await show_categories_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Поиск категории ---

async def find_category_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога поиска категории. Запрашивает поисковый запрос."""
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
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске find_category_entry")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог поиска категории.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название* категории или его часть для поиска:",
        parse_mode='Markdown'
    )
    return CATEGORY_FIND_QUERY_STATE

async def handle_category_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод поискового запроса и выполняет поиск."""
    query_text = update.message.text.strip()
    if not query_text:
         await update.message.reply_text("Поисковый запрос не может быть пустым. Введите *название* или его часть:", parse_mode='Markdown')
         return CATEGORY_FIND_QUERY_STATE

    try:
        # Вызов функции поиска из utils.db
        results = db.find_categories_by_name(query_text)

        response_text = f"Результаты поиска по запросу '{query_text}':\n\n"
        if results:
            for cat in results:
                 parent_info = f" (Родитель: ID `{cat.parent_id}`)" if cat.parent_id is not None else ""
                 response_text += f"📁 ID: `{cat.id}`\n" \
                                  f"  Название: *{cat.name}*{parent_info}\n\n"
        else:
            response_text += "Категории по вашему запросу не найдены."

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при вызове db.find_categories_by_name: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при поиске категорий.")


    await show_categories_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Обновление категории ---

async def update_category_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога обновления категории. Запрашивает ID категории."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    # Если entry point вызван из кнопки "Редактировать" на странице деталей
    # Callback формат: admin_categories_detail_ID_edit_ID
    if ADMIN_EDIT_PREFIX in query.data:
         try:
             # Парсим ID категории из callback_data
             parts = query.data.split(ADMIN_EDIT_PREFIX)
             category_id_str = parts[-1]
             category_id = int(category_id_str)
             logger.info(f"Запущено обновление категории из деталей. ID: {category_id}")

             # Пытаемся убрать клавиатуру из сообщения деталей
             if query.message:
                  try:
                      await query.message.edit_reply_markup(reply_markup=None)
                  except Exception:
                       logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске update_category_entry")


             # Переходим сразу к загрузке категории
             temp_message = type('obj', (object,), {'text': str(category_id), 'from_user': update.effective_user, 'chat': update.effective_chat})()
             temp_update = type('obj', (object,), {'message': temp_message, 'effective_user': update.effective_user, 'effective_chat': update.effective_chat, 'callback_query': None})()
             return await handle_category_update_id(temp_update, context)

         except (ValueError, IndexError) as e:
             logger.error(f"Не удалось распарсить ID категории из edit callback: {query.data}", exc_info=True)
             await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования.")
             await show_categories_menu(update, context)
             return CONVERSATION_END
         except Exception as e:
              logger.error(f"Непредвиденная ошибка при запуске обновления из деталей: {e}", exc_info=True)
              await query.edit_message_text("❌ Произошла ошибка при запуске диалога редактирования.")
              await show_categories_menu(update, context)
              return CONVERSATION_END


    # Если entry point вызван из меню
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске update_category_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог обновления категории.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *ID категории*, которую хотите обновить:",
        parse_mode='Markdown'
    )
    context.user_data['updated_category_data'] = {}
    return CATEGORY_UPDATE_ID_STATE

async def handle_category_update_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID категории для обновления."""
    category_id_text = update.message.text.strip()
    try:
        category_id = int(category_id_text)
        category = db.get_category_by_id(category_id)

        if category:
            context.user_data['updated_category_data']['id'] = category_id
            context.user_data['updated_category_data']['original_name'] = category.name
            # Сохраняем оригинальный parent_id на случай ввода "="
            context.user_data['updated_category_data']['original_parent_id'] = category.parent_id


            summary = (
                f"Найдена категория ID `{category.id}`: *{category.name}*.\n"
                f"Текущий родитель: ID `{category.parent_id}`\n\n"
                "Введите новое *название* категории (можно пропустить, введя '='):" # Добавлена возможность оставить старое значение
            )
            await update.message.reply_text(summary, parse_mode='Markdown')

            return CATEGORY_UPDATE_NAME_STATE
        else:
            await update.message.reply_text(
                f"Категория с ID `{category_id_text}` не найдена. Пожалуйста, введите корректный *ID категории* для обновления:",
                parse_mode='Markdown'
            )
            return CATEGORY_UPDATE_ID_STATE

    except ValueError:
        await update.message.reply_text("ID категории должен быть целым числом. Пожалуйста, введите корректный *ID категории*:", parse_mode='Markdown')
        return CATEGORY_UPDATE_ID_STATE
    except Exception as e:
         logger.error(f"Ошибка при получении категории по ID {category_id_text} для обновления: {e}", exc_info=True)
         await update.message.reply_text("❌ Произошла ошибка при поиске категории.")
         await cancel_category_operation(update, context)
         return CONVERSATION_END


async def handle_category_update_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового названия категории."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Название не может быть пустым. Введите новое *название* категории (можно пропустить, введя '='):", parse_mode='Markdown')
        return CATEGORY_UPDATE_NAME_STATE

    # Если пользователь ввел '=', оставляем старое значение
    if name == '=':
        original_name = context.user_data['updated_category_data'].get('original_name')
        context.user_data['updated_category_data']['name'] = original_name
        await update.message.reply_text("Название оставлено без изменений.")
    else:
        context.user_data['updated_category_data']['name'] = name


    await update.message.reply_text(
        "Введите новый *ID родительской категории*, если есть (можно пропустить, введя '-', или оставить старое значение, введя '='):\n"
        "Для просмотра списка категорий временно выйдите из диалога (/cancel) и воспользуйтесь меню \"Список категорий\".",
        parse_mode='Markdown'
    )
    return CATEGORY_UPDATE_PARENT_ID_STATE

async def handle_category_update_parent_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод нового ID родительской категории и выполняет обновление."""
    parent_id_text = update.message.text.strip()
    parent_id = None # Значение для обновления в БД
    category_id = context.user_data['updated_category_data'].get('id')

    if parent_id_text == '=':
         # Оставляем старое значение
         parent_id = context.user_data['updated_category_data'].get('original_parent_id')
         await update.message.reply_text(f"Родительская категория оставлена без изменений (ID: {parent_id if parent_id is not None else 'Нет'}).")

    elif parent_id_text != '-':
        try:
            parent_id_input = int(parent_id_text)
            # Проверка: нельзя сделать категорию родителем самой себя
            if parent_id_input == category_id:
                await update.message.reply_text(
                     "Категория не может быть родителем самой себя. Введите корректный *ID родительской категории*, '-' или '=':",
                     parse_mode='Markdown'
                )
                return CATEGORY_UPDATE_PARENT_ID_STATE
            # Проверка существования родительской категории
            parent_category = db.get_category_by_id(parent_id_input)
            if not parent_category:
                await update.message.reply_text(
                    f"Родительская категория с ID `{parent_id_text}` не найдена. Пожалуйста, введите корректный *ID родительской категории*, '-' или '=':",
                    parse_mode='Markdown'
                )
                return CATEGORY_UPDATE_PARENT_ID_STATE
            # Проверка на циклическую зависимость (упрощенная: проверяем только прямое родительство)
            # Более сложная проверка требует обхода дерева, что может быть ресурсоемким и лучше реализовано в логике БД
            # Например, можно проверить, является ли обновляемая категория дочерней для parent_id_input
            # CurrentCategory IS DESCENDANT OF ProposedParent
            # Пропустим эту проверку здесь для простоты, полагаясь на возможные ошибки БД при сложных циклах.
            parent_id = parent_id_input # Если проверки пройдены, используем введенный ID

        except ValueError:
            await update.message.reply_text("ID родительской категории должен быть целым числом, '-' или '='. Пожалуйста, введите корректный *ID* или '-':", parse_mode='Markdown')
            return CATEGORY_UPDATE_PARENT_ID_STATE
        except Exception as e:
             logger.error(f"Ошибка при поиске родительской категории по ID {parent_id_text} при обновлении: {e}", exc_info=True)
             await update.message.reply_text("❌ Произошла ошибка при поиске родительской категории.")
             await cancel_category_operation(update, context)
             return CONVERSATION_END
    # Если ввели '-', parent_id останется None

    context.user_data['updated_category_data']['parent_id'] = parent_id

    # Выполняем обновление
    category_id_to_update = context.user_data['updated_category_data'].get('id')
    new_name = context.user_data['updated_category_data'].get('name')
    new_parent_id_value = context.user_data['updated_category_data'].get('parent_id') # Получаем уже обработанное значение

    if not category_id_to_update or new_name is None: # Название не может быть None
        await update.message.reply_text("Ошибка: Не удалось получить все данные для обновления.")
        if 'updated_category_data' in context.user_data: del context.user_data['updated_category_data']
        await show_categories_menu(update, context)
        return CONVERSATION_END

    try:
        # update_data содержит только те поля, которые нужно обновить
        update_data = {'name': new_name}
        # Добавляем parent_id, только если он был введен (не '=' или '-')
        # Или если был введен '-' (тогда parent_id = None)
        # Если было '=', parent_id уже взят из original
        if parent_id_text != '=': # Обновляем parent_id, если пользователь что-то ввел, кроме '='
             update_data['parent_id'] = new_parent_id_value

        updated_category = db.update_category(category_id_to_update, update_data)

        if updated_category:
             parent_info = f" (родитель: ID `{updated_category.parent_id}`)" if updated_category.parent_id is not None else ""
             await update.message.reply_text(f"✅ Категория ID `{category_id_to_update}` успешно обновлена! Новое название: *{updated_category.name}*{parent_info}", parse_mode='Markdown')
        else:
             # db.update_category уже логирует причину
             await update.message.reply_text(f"❌ Ошибка при обновлении категории ID `{category_id_to_update}`. Возможно, категория с таким названием уже существует или указан неверный ID родителя.")

    except Exception as e:
        logger.error(f"Ошибка при вызове db.update_category для ID {category_id_to_update}: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при обновлении категории.")

    if 'updated_category_data' in context.user_data:
        del context.user_data['updated_category_data']

    await show_categories_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Удаление категории ---

async def delete_category_confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога подтверждения удаления категории."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID категории из callback_data: admin_categories_detail_ID_delete_confirm_ID
        # ID для удаления - это последний ID после ADMIN_DELETE_CONFIRM_PREFIX
        parts = query.data.split(ADMIN_DELETE_CONFIRM_PREFIX)
        category_id_str = parts[-1]
        category_id = int(category_id_str)
        context.user_data['category_to_delete_id'] = category_id

        # Пытаемся убрать клавиатуру из сообщения деталей
        if query.message:
             try:
                 await query.message.edit_reply_markup(reply_markup=None)
             except Exception:
                  logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске delete_category_confirm_entry")


        category = db.get_category_by_id(category_id)
        if not category:
             await query.edit_message_text(f"❌ Ошибка: Категория с ID `{category_id}` не найдена для удаления.")
             await show_categories_menu(update, context)
             return CONVERSATION_END

        parent_info = f" (Родитель: ID `{category.parent_id}`)" if category.parent_id is not None else ""
        confirmation_text = (
            f"Вы уверены, что хотите удалить категорию?\n\n"
            f"📁 ID: `{category.id}`\n"
            f"Название: *{category.name}*{parent_info}\n\n"
            f"*ВНИМАНИЕ:* Удаление категории может сделать связанные товары сиротами или удалить их (в зависимости от настроек БД)! "
            "Также могут быть затронуты дочерние категории (удалены, если CASCADE)." # Предупреждение о связях
        )

        # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID
        # entity "category" жестко прописан
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"category{ADMIN_DELETE_EXECUTE_PREFIX}{category_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=ADMIN_BACK_CATEGORIES_MENU)] # Отмена возвращает в меню категорий
        ])

        await query.edit_message_text(confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

        return CATEGORY_DELETE_CONFIRM_STATE

    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось распарсить ID категории из delete confirm callback: {query.data}", exc_info=True)
        await query.edit_message_text("❌ Ошибка: Неверный формат ID для удаления.")
        await show_categories_menu(update, context)
        return CONVERSATION_END
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске подтверждения удаления категории: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при подготовке к удалению категории.")
        await show_categories_menu(update, context)
        return CONVERSATION_END


async def handle_category_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет удаление категории из БД."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    category_id = None # Инициализация для логгирования в случае ошибки парсинга

    try:
        # Парсим ID категории из callback_data: category_delete_execute_ID
        parts = query.data.split(ADMIN_DELETE_EXECUTE_PREFIX)
        category_id_str = parts[-1]
        category_id = int(category_id_str)

        # Опционально: Проверяем, совпадает ли ID с сохраненным
        # saved_id = context.user_data.get('category_to_delete_id')
        # if saved_id is None or saved_id != category_id:
        #      logger.error(f"Несоответствие сохраненного ({saved_id}) и полученного ({category_id}) ID при выполнении удаления категории.")
        #      await query.edit_message_text("❌ Ошибка: Несоответствие ID при выполнении удаления.")
        #      await show_categories_menu(update, context)
        #      if 'category_to_delete_id' in context.user_data: del context.user_data['category_to_delete_id']
        #      return CONVERSATION_END

        # Удаляем кнопки подтверждения
        try:
             await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
             logger.debug("Не удалось убрать клавиатуру после выполнения удаления категории")


        # Вызываем функцию удаления из utils.db
        success = db.delete_category(category_id)

        if success:
            await query.message.reply_text(f"✅ Категория ID `{category_id}` успешно удалена!")
        else:
             # db.delete_category уже логирует причину
             await query.message.reply_text(f"❌ Не удалось удалить категорию ID `{category_id}`. Возможно, существуют связанные товары или дочерние категории, или произошла другая ошибка.")

    except (ValueError, IndexError) as e:
         logger.error(f"Не удалось распарсить ID категории из delete execute callback: {query.data}", exc_info=True)
         await query.edit_message_text("❌ Ошибка: Неверный формат ID при выполнении удаления.")
    except Exception as e:
         logger.error(f"Непредвиденная ошибка при выполнении удаления категории ID {category_id}: {e}", exc_info=True)
         await query.message.reply_text("❌ Произошла непредвиденная ошибка при удалении категории.")

    if 'category_to_delete_id' in context.user_data:
         del context.user_data['category_to_delete_id']

    await show_categories_menu(update, context)
    return CONVERSATION_END


# --- Определение ConversationHandler'ов для Категорий ---

add_category_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_category_entry, pattern=f'^{ADMIN_CATEGORIES_ADD}$')],
    states={
        CATEGORY_ADD_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_name_add)],
        CATEGORY_ADD_PARENT_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_parent_id_add)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_category_operation, pattern=f'^{ADMIN_BACK_CATEGORIES_MENU}$'),
        CommandHandler("cancel", cancel_category_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_category_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

find_category_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(find_category_entry, pattern=f'^{ADMIN_CATEGORIES_FIND}$')],
    states={
        CATEGORY_FIND_QUERY_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_search_query)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_category_operation, pattern=f'^{ADMIN_BACK_CATEGORIES_MENU}$'),
        CommandHandler("cancel", cancel_category_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_category_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

# Паттерн для entry_points обновления
# Из меню: ^admin_categories_update$
# Из деталей: ^admin_categories_detail_ID_edit_ID$
update_category_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(update_category_entry, pattern=f'^{ADMIN_CATEGORIES_UPDATE}$'),
        CallbackQueryHandler(update_category_entry, pattern=f'^{ADMIN_CATEGORIES_DETAIL}\d+{ADMIN_EDIT_PREFIX}\d+$')
    ],
    states={
        CATEGORY_UPDATE_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_update_id)],
        CATEGORY_UPDATE_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_update_name)],
        CATEGORY_UPDATE_PARENT_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_update_parent_id)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_category_operation, pattern=f'^{ADMIN_BACK_CATEGORIES_MENU}$'),
        CommandHandler("cancel", cancel_category_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_category_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

# Паттерн для entry_points удаления
# С деталей: ^admin_categories_detail_ID_delete_confirm_ID$
delete_category_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_category_confirm_entry, pattern=f'^{ADMIN_CATEGORIES_DETAIL}\d+{ADMIN_DELETE_CONFIRM_PREFIX}\d+$')
    ],
    states={
        CATEGORY_DELETE_CONFIRM_STATE: [
             # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID
             # entity "category" жестко прописан в колбэке кнопки "Да, удалить"
             CallbackQueryHandler(handle_category_delete_execute, pattern=f'^category{ADMIN_DELETE_EXECUTE_PREFIX}\d+$'), # Кнопка "Да, удалить"
             CallbackQueryHandler(cancel_category_operation, pattern=f'^{ADMIN_BACK_CATEGORIES_MENU}$') # Кнопка "Нет, отмена"
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_category_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_category_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)
