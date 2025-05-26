# your_bot/handlers/admin_stock_conversations.py
# ConversationHandler'ы для добавления/изменения, поиска и удаления остатков

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from decimal import Decimal, InvalidOperation # Импортируем на случай копирования/вставки

# Импорт констант
from .admin_constants import (
    ADMIN_STOCK_ADD, ADMIN_STOCK_FIND,
    ADMIN_BACK_STOCK_MENU, CONVERSATION_END,
    ADMIN_DETAIL_PREFIX, ADMIN_EDIT_PREFIX,
    ADMIN_STOCK_DELETE_CONFIRM,
    ADMIN_DELETE_EXECUTE_PREFIX
    # Импорт констант состояний не требуется, используем локальные
)
from .admin_menus import show_stock_menu, is_admin
# from .admin_menus import handle_stock_detail # Не импортируем, возврат в список


# Импорт функций базы данных
from utils import db

logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler для остатков ---
# Add/Update Stock States
(STOCK_OPERATION_PRODUCT_ID_STATE, STOCK_OPERATION_LOCATION_ID_STATE, STOCK_OPERATION_QUANTITY_STATE) = range(3) # Нумерация с 0

# Find Stock States
(STOCK_FIND_PRODUCT_NAME_STATE, STOCK_FIND_LOCATION_NAME_STATE) = range(3, 5)

# Delete Stock States
(STOCK_DELETE_CONFIRM_STATE,) = range(5, 6)


# --- Функции отмены ConversationHandler (общие для всех операций с остатками) ---
async def cancel_stock_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущую операцию с остатками (добавление/изменение, поиск или удаление)."""
    user_id = update.effective_user.id
    if not is_admin(user_id): return CONVERSATION_END

    # Удаляем сохраненные данные, если они есть
    if 'stock_item_data' in context.user_data:
        del context.user_data['stock_item_data']
    if 'stock_find_criteria' in context.user_data:
        del context.user_data['stock_find_criteria']
    if 'stock_to_delete_ids' in context.user_data:
         del context.user_data['stock_to_delete_ids']

    # Отправляем сообщение об отмене
    if update.callback_query:
        await update.callback_query.answer()
        try:
             await update.callback_query.edit_message_text("Операция с остатками отменена.")
        except Exception:
             chat_id = update.effective_chat.id
             await context.bot.send_message(chat_id=chat_id, text="Операция с остатками отменена.")
    elif update.message:
        await update.message.reply_text("Операция с остатками отменена.")

    await show_stock_menu(update, context)
    return CONVERSATION_END

# --- Функции обработчиков состояний: Добавление/Изменение остатка ---

async def add_stock_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога добавления/изменения остатка. Запрашивает ID товара."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    # Если entry point вызван из кнопки "Редактировать" на странице деталей остатка
    # Callback формат: admin_stock_detail_prodID_locID_edit_prodID_locID
    if ADMIN_EDIT_PREFIX in query.data:
        try:
             # Парсим ID товара и локации из callback_data: admin_stock_detail_prodID_locID_edit_prodID_locID
             # Нам нужны ID после _edit_
             parts = query.data.split(ADMIN_EDIT_PREFIX)
             ids_str = parts[-1] # product_id_location_id
             ids = ids_str.split('_')
             if len(ids) == 2:
                  product_id = int(ids[0])
                  location_id = int(ids[1])
                  logger.info(f"Запущено изменение остатка из деталей. Product ID: {product_id}, Location ID: {location_id}")

                  # Пытаемся убрать клавиатуру из сообщения деталей
                  if query.message:
                       try:
                           await query.message.edit_reply_markup(reply_markup=None)
                       except Exception:
                           logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске add_stock_entry (edit)")

                  # Загружаем существующий остаток, чтобы показать его пользователю
                  existing_stock = db.get_stock_by_ids(product_id, location_id)
                  if not existing_stock:
                       await query.edit_message_text(f"❌ Ошибка: Остаток для товара ID `{product_id}` и местоположения ID `{location_id}` не найден.")
                       await show_stock_menu(update, context)
                       return CONVERSATION_END

                  # Сохраняем ID и количество для дальнейшего использования
                  context.user_data['stock_item_data'] = {
                       'product_id': product_id,
                       'location_id': location_id,
                       'original_quantity': existing_stock.quantity # Сохраняем текущее количество
                  }

                  # Получаем названия товара и локации для сообщения
                  session = db.SessionLocal()
                  try:
                      product = session.query(db.Product).get(product_id)
                      location = session.query(db.Location).get(location_id)
                      product_name = product.name if product else 'Неизвестный товар'
                      location_name = location.name if location else 'Неизвестное местоположение'
                      context.user_data['stock_item_data']['product_name'] = product_name
                      context.user_data['stock_item_data']['location_name'] = location_name
                  except Exception as e:
                       logger.error(f"Ошибка при загрузке оригинальных названий для остатка prodID={product_id}, locID={location_id} при редактировании: {e}", exc_info=True)
                       context.user_data['stock_item_data']['product_name'] = 'Ошибка загрузки товара'
                       context.user_data['stock_item_data']['location_name'] = 'Ошибка загрузки локации'
                  finally:
                       session.close()

                  await context.bot.send_message( # Отправляем новое сообщение, т.к. старое могли отредактировать
                      chat_id=update.effective_chat.id,
                      text=f"Редактирование остатка:\n\n"
                           f"📦 Товар: *{context.user_data['stock_item_data']['product_name']}* (ID: `{product_id}`)\n"
                           f"📍 Местоположение: *{context.user_data['stock_item_data']['location_name']}* (ID: `{location_id}`)\n"
                           f"Текущее количество: `{existing_stock.quantity}`\n\n"
                           "Введите новое *количество* остатка (целое неотрицательное число):",
                      parse_mode='Markdown'
                  )

                  # Переходим сразу к запросу количества
                  return STOCK_OPERATION_QUANTITY_STATE

             else:
                  logger.error(f"Неверное количество ID для остатка из edit callback: {query.data}")
                  await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования остатка.")
                  await show_stock_menu(update, context)
                  return CONVERSATION_END

        except (ValueError, IndexError) as e:
             logger.error(f"Не удалось распарсить ID остатка из edit callback: {query.data}", exc_info=True)
             await query.edit_message_text("❌ Ошибка: Неверный формат ID для редактирования остатка.")
             await show_stock_menu(update, context)
             return CONVERSATION_END
        except Exception as e:
             logger.error(f"Непредвиденная ошибка при запуске изменения остатка из деталей: {e}", exc_info=True)
             await query.edit_message_text("❌ Произошла ошибка при запуске диалога редактирования остатка.")
             await show_stock_menu(update, context)
             return CONVERSATION_END


    # Если entry point вызван из кнопки "Добавить/Изменить остаток" в меню
    if query.message:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске add_stock_entry (menu)")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог добавления/изменения остатка.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *ID товара*:",
        parse_mode='Markdown'
    )
    context.user_data['stock_item_data'] = {}
    return STOCK_OPERATION_PRODUCT_ID_STATE


async def handle_stock_operation_product_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID товара для остатка (Add/Update)."""
    product_id_text = update.message.text.strip()
    try:
        product_id = int(product_id_text)
        product = db.get_product_by_id(product_id)

        if product:
            context.user_data['stock_item_data']['product_id'] = product_id
            context.user_data['stock_item_data']['product_name'] = product.name

            await update.message.reply_text(
                f"Товар найден: *{product.name}*.\n"
                "Теперь введите *ID местоположения*:",
                parse_mode='Markdown'
            )
            return STOCK_OPERATION_LOCATION_ID_STATE
        else:
            await update.message.reply_text(
                f"Товар с ID `{product_id_text}` не найден. Пожалуйста, введите корректный *ID товара*:",
                 parse_mode='Markdown'
            )
            return STOCK_OPERATION_PRODUCT_ID_STATE

    except ValueError:
        await update.message.reply_text("ID товара должен быть целым числом. Пожалуйста, введите корректный *ID товара*:", parse_mode='Markdown')
        return STOCK_OPERATION_PRODUCT_ID_STATE
    except Exception as e:
         logger.error(f"Ошибка при поиске товара по ID {product_id_text} для операции с остатком: {e}", exc_info=True)
         await update.message.reply_text("❌ Произошла ошибка при поиске товара.")
         await cancel_stock_operation(update, context)
         return CONVERSATION_END


async def handle_stock_operation_location_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ID местоположения для остатка (Add/Update)."""
    location_id_text = update.message.text.strip()
    try:
        location_id = int(location_id_text)
        location = db.get_location_by_id(location_id)

        if location:
            context.user_data['stock_item_data']['location_id'] = location_id
            context.user_data['stock_item_data']['location_name'] = location.name

            await update.message.reply_text(
                f"Местоположение найдено: *{location.name}*.\n"
                "Теперь введите *количество остатка* (целое неотрицательное число):",
                parse_mode='Markdown'
            )
            return STOCK_OPERATION_QUANTITY_STATE
        else:
            await update.message.reply_text(
                f"Местоположение с ID `{location_id_text}` не найдено. Пожалуйста, введите корректный *ID местоположения*:",
                parse_mode='Markdown'
            )
            return STOCK_OPERATION_LOCATION_ID_STATE

    except ValueError:
        await update.message.reply_text("ID местоположения должен быть целым числом. Пожалуйста, введите корректный *ID местоположения*:", parse_mode='Markdown')
        return STOCK_OPERATION_LOCATION_ID_STATE
    except Exception as e:
        logger.error(f"Ошибка при поиске местоположения по ID {location_id_text} для операции с остатком: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при поиске местоположения.")
        await cancel_stock_operation(update, context)
        return CONVERSATION_END


async def handle_stock_operation_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод количества и выполняет добавление/обновление остатка."""
    quantity_text = update.message.text.strip()
    try:
        quantity = int(quantity_text)
        if quantity < 0:
            await update.message.reply_text("Количество не может быть отрицательным. Введите корректное *количество остатка*:", parse_mode='Markdown')
            return STOCK_OPERATION_QUANTITY_STATE

        stock_data = context.user_data.get('stock_item_data')
        if not stock_data or 'product_id' not in stock_data or 'location_id' not in stock_data:
             await update.message.reply_text("❌ Ошибка: Данные товара или местоположения потеряны.")
             await show_stock_menu(update, context)
             return CONVERSATION_END

        product_id = stock_data['product_id']
        location_id = stock_data['location_id']
        product_name = stock_data.get('product_name', 'N/A')
        location_name = stock_data.get('location_name', 'N/A')

        try:
            # Проверяем, существует ли уже запись для данного товара и местоположения
            existing_stock = db.get_stock_by_ids(product_id, location_id)

            if existing_stock:
                # Если запись существует, обновляем количество
                updated_stock = db.update_stock_quantity(product_id, location_id, quantity)
                if updated_stock:
                    await update.message.reply_text(
                        f"✅ Остаток для товара *{product_name}* "
                        f"в местоположении *{location_name}* "
                        f"успешно обновлен. Новое количество: `{updated_stock.quantity}`.",
                        parse_mode='Markdown'
                    )
                else:
                     # db.update_stock_quantity уже логирует причину
                     await update.message.reply_text(
                         f"❌ Ошибка при обновлении остатка для товара *{product_name}* "
                         f"в местоположении *{location_name}*.",
                         parse_mode='Markdown'
                    )
            else:
                # Если запись не существует, добавляем новую
                # Проверяем, что количество > 0 для добавления новой записи
                if quantity > 0:
                    added_stock = db.add_stock(product_id, location_id, quantity)
                    if added_stock:
                        await update.message.reply_text(
                            f"✅ Новый остаток для товара *{product_name}* "
                            f"в местоположении *{location_name}* "
                            f"успешно добавлен. Количество: `{added_stock.quantity}`.",
                             parse_mode='Markdown'
                        )
                    else:
                        # db.add_stock уже логирует причину
                        await update.message.reply_text(
                            f"❌ Ошибка при добавлении нового остатка для товара *{product_name}* "
                            f"в местоположении *{location_name}*.",
                            parse_mode='Markdown'
                       )
                else: # Количество 0, запись не существует - ничего не делаем
                     await update.message.reply_text(
                        f"Остаток для товара *{product_name}* в местоположении *{location_name}* отсутствует. "
                        "Введено количество 0. Запись не добавлена.",
                        parse_mode='Markdown'
                   )


        except Exception as e:
             logger.error(f"Ошибка при добавлении/обновлении остатка в DB (product_id={product_id}, location_id={location_id}, quantity={quantity}): {e}", exc_info=True)
             await update.message.reply_text("❌ Произошла непредвиденная ошибка при работе с остатком.")


        if 'stock_item_data' in context.user_data:
            del context.user_data['stock_item_data']

        await show_stock_menu(update, context)
        return CONVERSATION_END

    except ValueError:
        await update.message.reply_text("Количество остатка должно быть целым неотрицательным числом. Введите корректное *количество*:", parse_mode='Markdown')
        return STOCK_OPERATION_QUANTITY_STATE
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при обработке количества остатка '{quantity_text}': {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка.")
        await cancel_stock_operation(update, context)
        return CONVERSATION_END


# --- Функции обработчиков состояний: Поиск остатка ---

async def find_stock_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога поиска остатка. Запрашивает название товара."""
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
            logger.debug("Не удалось убрать клавиатуру из сообщения при запуске find_stock_entry")


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Инициирован диалог поиска остатка.\n"
             "Для отмены введите /cancel\n\n"
             "Введите *название товара* или его часть (можно пропустить, введя '-') для фильтрации:",
        parse_mode='Markdown'
    )
    context.user_data['stock_find_criteria'] = {}

    return STOCK_FIND_PRODUCT_NAME_STATE # Первое состояние поиска


async def handle_stock_find_product_name_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия товара для поиска остатков (шаг 1)."""
    product_query = update.message.text.strip()
    if product_query == '-':
        product_query = None # Пользователь пропустил ввод

    context.user_data['stock_find_criteria']['product_name_query'] = product_query

    await update.message.reply_text(
        "Теперь введите *название местоположения* или его часть (можно пропустить, введя '-') для фильтрации:",
        parse_mode='Markdown'
    )
    return STOCK_FIND_LOCATION_NAME_STATE # Переход к следующему состоянию поиска


async def handle_stock_find_location_name_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод названия местоположения и выполняет поиск остатков (шаг 2)."""
    location_query = update.message.text.strip()
    if location_query == '-':
        location_query = None # Пользователь пропустил ввод

    context.user_data['stock_find_criteria']['location_name_query'] = location_query

    product_name_query = context.user_data['stock_find_criteria'].get('product_name_query')
    location_name_query = context.user_data['stock_find_criteria'].get('location_name_query')

    # Проверка: введен ли хотя бы один критерий?
    if not product_name_query and not location_name_query:
         await update.message.reply_text("Вы не ввели ни название товара, ни название местоположения. Укажите хотя бы один критерий для поиска.")
         # Очищаем user_data и возвращаемся в меню
         if 'stock_find_criteria' in context.user_data: del context.user_data['stock_find_criteria']
         await show_stock_menu(update, context)
         return CONVERSATION_END

    try:
        # Вызов функции поиска из utils.db
        results = db.find_stock(product_name_query=product_name_query, location_name_query=location_name_query)

        response_text = f"Результаты поиска остатков (Товар: '{product_name_query or "любой"}', Местоположение: '{location_name_query or "любое"}'):\n\n"
        if results:
            # Для отображения названий, нужно подгрузить связанные объекты Product и Location
            session = db.SessionLocal()
            try:
                for item in results:
                     # Используем scalar() для получения одного значения из запроса
                     product_name = session.query(db.Product.name).filter_by(id=item.product_id).scalar() or 'Неизвестный товар'
                     location_name = session.query(db.Location.name).filter_by(id=item.location_id).scalar() or 'Неизвестное местоположение'
                     response_text += f"📦 Товар ID `{item.product_id}` (*{product_name}*)\n" \
                                      f"  📍 Местоположение ID `{item.location_id}` (*{location_name}*)\n" \
                                      f"  🔢 Количество: `{item.quantity}`\n\n"
            except Exception as e:
                 logger.error(f"Ошибка при форматировании списка остатков в поиске: {e}", exc_info=True)
                 response_text += "\n❌ Ошибка при загрузке связанных данных."
            finally:
                session.close() # Закрываем сессию
        else:
            response_text += "Остатки по вашим критериям не найдены."

        await update.message.reply_text(response_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка при вызове db.find_stock (товар: '{product_name_query}', локация: '{location_name_query}'): {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла непредвиденная ошибка при поиске остатков.")

    # Очищаем user_data
    if 'stock_find_criteria' in context.user_data:
        del context.user_data['stock_find_criteria']

    # Возвращаемся в меню остатков
    await show_stock_menu(update, context)
    return CONVERSATION_END


# --- Функции обработчиков состояний: Удаление остатка ---

async def delete_stock_confirm_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ENTRY_POINT для диалога подтверждения удаления остатка."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    try:
        # Парсим ID товара и локации из callback_data: admin_stock_detail_prodID_locID_delete_confirm_prodID_locID
        # Нам нужны ID после ADMIN_DELETE_CONFIRM_PREFIX
        parts = query.data.split(ADMIN_DELETE_CONFIRM_PREFIX)
        ids_str = parts[-1] # product_id_location_id
        ids = ids_str.split('_')
        if len(ids) == 2:
             product_id = int(ids[0])
             location_id = int(ids[1])
             context.user_data['stock_to_delete_ids'] = (product_id, location_id) # Сохраняем ID для последующего шага

             # Пытаемся убрать клавиатуру из сообщения деталей
             if query.message:
                  try:
                      await query.message.edit_reply_markup(reply_markup=None)
                  except Exception:
                       logger.debug("Не удалось убрать клавиатуру из сообщения деталей при запуске delete_stock_confirm_entry")

             # Получаем информацию об остатке для отображения в сообщении подтверждения
             stock_item = db.get_stock_by_ids(product_id, location_id)
             if not stock_item:
                  await query.edit_message_text(f"❌ Ошибка: Остаток для товара ID `{product_id}` и местоположения ID `{location_id}` не найден для удаления.")
                  # Возвращаемся в меню остатков
                  await show_stock_menu(update, context)
                  return CONVERSATION_END

             # Получаем названия товара и локации для сообщения
             session = db.SessionLocal()
             try:
                 product = session.query(db.Product).get(product_id)
                 location = session.query(db.Location).get(location_id)
                 product_name = product.name if product else 'Неизвестный товар'
                 location_name = location.name if location else 'Неизвестное местоположение'
             except Exception as e:
                 logger.error(f"Ошибка при загрузке названий для остатка prodID={product_id}, locID={location_id} при подтверждении удаления: {e}", exc_info=True)
                 product_name = 'Ошибка загрузки товара'
                 location_name = 'Ошибка загрузки локации'
             finally:
                 session.close()


             confirmation_text = (
                 f"Вы уверены, что хотите удалить запись об остатке?\n\n"
                 f"📦 Товар: *{product_name}* (ID: `{product_id}`)\n"
                 f"📍 Местоположение: *{location_name}* (ID: `{location_id}`)\n"
                 f"🔢 Количество: `{stock_item.quantity}`"
             )

             # Callback для выполнения удаления кодирует оба ID: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID1_ID2
             # entity "stock" жестко прописан в колбэке
             execute_callback_data = f"stock{ADMIN_DELETE_EXECUTE_PREFIX}{product_id}_{location_id}"
             keyboard = InlineKeyboardMarkup([
                 [InlineKeyboardButton("✅ Да, удалить", callback_data=execute_callback_data)],
                 [InlineKeyboardButton("❌ Отмена", callback_data=ADMIN_BACK_STOCK_MENU)] # Отмена возвращает в меню остатков
             ])

             # Редактируем сообщение, чтобы показать запрос подтверждения
             await query.edit_message_text(confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

             return STOCK_DELETE_CONFIRM_STATE # Переход в состояние ожидания подтверждения
        else:
            logger.error(f"Неверное количество ID для остатка из delete confirm callback: {query.data}")
            await query.edit_message_text("❌ Ошибка: Неверный формат ID для удаления остатка.")
            await show_stock_menu(update, context)
            return CONVERSATION_END

    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось распарсить ID остатка из delete confirm callback: {query.data}", exc_info=True)
        await query.edit_message_text("❌ Ошибка: Неверный формат ID для удаления остатка.")
        await show_stock_menu(update, context)
        return CONVERSATION_END
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске подтверждения удаления остатка: {e}", exc_info=True)
        await query.edit_message_text("❌ Произошла ошибка при подготовке к удалению остатка.")
        await show_stock_menu(update, context)
        return CONVERSATION_END


async def handle_stock_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выполняет удаление записи остатка из БД."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)
        return CONVERSATION_END

    query = update.callback_query
    await query.answer()

    product_id, location_id = None, None # Инициализация для логгирования в случае ошибки парсинга

    try:
        # Парсим ID товара и локации из callback_data: stock_delete_execute_prodID_locID
        parts = query.data.split(ADMIN_DELETE_EXECUTE_PREFIX)
        ids_str = parts[-1] # product_id_location_id
        ids = ids_str.split('_')
        if len(ids) == 2:
             product_id = int(ids[0])
             location_id = int(ids[1])

             # Опционально: Проверяем, совпадает ли ID с сохраненным
             # saved_ids = context.user_data.get('stock_to_delete_ids')
             # if saved_ids is None or saved_ids != (product_id, location_id):
             #      logger.error(f"Несоответствие сохраненных ({saved_ids}) и полученных ({product_id}, {location_id}) ID при выполнении удаления остатка.")
             #      await query.edit_message_text("❌ Ошибка: Несоответствие ID при выполнении удаления.")
             #      await show_stock_menu(update, context)
             #      # Очищаем user_data
             #      if 'stock_to_delete_ids' in context.user_data: del context.user_data['stock_to_delete_ids']
             #      return CONVERSATION_END


             # Удаляем кнопки подтверждения
             try:
                  await query.edit_message_reply_markup(reply_markup=None)
             except Exception:
                  logger.debug("Не удалось убрать клавиатуру после выполнения удаления остатка")


             # Вызываем функцию удаления из utils.db
             success = db.delete_stock(product_id, location_id)

             if success:
                 await query.message.reply_text(f"✅ Запись остатка (Товар ID `{product_id}`, Местоположение ID `{location_id}`) успешно удалена!")
             else:
                  # db.delete_stock уже логирует причину
                  await query.message.reply_text(f"❌ Не удалось удалить запись остатка (Товар ID `{product_id}`, Местоположение ID `{location_id}`). Возможно, запись не найдена.")

        else:
            logger.error(f"Неверное количество ID для остатка из delete execute callback: {query.data}")
            await query.edit_message_text("❌ Ошибка: Неверный формат ID для выполнения удаления остатка.")


    except (ValueError, IndexError) as e:
         logger.error(f"Не удалось распарсить ID остатка из delete execute callback: {query.data}", exc_info=True)
         await query.edit_message_text("❌ Ошибка: Неверный формат ID при выполнении удаления остатка.")
    except Exception as e:
         logger.error(f"Непредвиденная ошибка при выполнении удаления остатка (prodID={product_id}, locID={location_id}): {e}", exc_info=True)
         await query.message.reply_text("❌ Произошла непредвиденная ошибка при удалении остатка.")

    # Очищаем user_data
    if 'stock_to_delete_ids' in context.user_data:
         del context.user_data['stock_to_delete_ids']

    # Возвращаемся в меню остатков
    await show_stock_menu(update, context)
    return CONVERSATION_END


# --- Определение ConversationHandler'ов для Остатков ---

# Паттерн для entry_points добавления/изменения остатка
# Из меню: ^admin_stock_add$
# Из деталей: ^admin_stock_detail_prodID_locID_edit_prodID_locID$
add_stock_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_stock_entry, pattern=f'^{ADMIN_STOCK_ADD}$'),
        CallbackQueryHandler(add_stock_entry, pattern=f'^{ADMIN_STOCK_DETAIL}\d+_\d+{ADMIN_EDIT_PREFIX}\d+_\d+$')
    ],
    states={
        STOCK_OPERATION_PRODUCT_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_operation_product_id)],
        STOCK_OPERATION_LOCATION_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_operation_location_id)],
        STOCK_OPERATION_QUANTITY_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_operation_quantity)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_stock_operation, pattern=f'^{ADMIN_BACK_STOCK_MENU}$'),
        CommandHandler("cancel", cancel_stock_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_stock_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

find_stock_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(find_stock_entry, pattern=f'^{ADMIN_STOCK_FIND}$')],
    states={
        STOCK_FIND_PRODUCT_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_find_product_name_step)],
        STOCK_FIND_LOCATION_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_find_location_name_step)],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_stock_operation, pattern=f'^{ADMIN_BACK_STOCK_MENU}$'),
        CommandHandler("cancel", cancel_stock_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_stock_operation)
    ],
     map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)

# Паттерн для entry_points удаления остатка
# С деталей: ^admin_stock_detail_prodID_locID_delete_confirm_prodID_locID$
delete_stock_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(delete_stock_confirm_entry, pattern=f'^{ADMIN_STOCK_DETAIL}\d+_\d+{ADMIN_DELETE_CONFIRM_PREFIX}\d+_\d+$')
    ],
    states={
        STOCK_DELETE_CONFIRM_STATE: [
             # Callback для выполнения удаления: entity{ADMIN_DELETE_EXECUTE_PREFIX}ID1_ID2
             # entity "stock" жестко прописан в колбэке кнопки "Да, удалить"
             CallbackQueryHandler(handle_stock_delete_execute, pattern=f'^stock{ADMIN_DELETE_EXECUTE_PREFIX}\d+_\d+$'), # Кнопка "Да, удалить"
             CallbackQueryHandler(cancel_stock_operation, pattern=f'^{ADMIN_BACK_STOCK_MENU}$') # Кнопка "Нет, отмена"
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_stock_operation),
        MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_stock_operation)
    ],
    map_to_parent={
        CONVERSATION_END: CONVERSATION_END
    },
    allow_reentry=True
)
