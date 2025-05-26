# your_bot/handlers/admin_delete_handlers_aiogram.py
# FSM и обработчики для операций удаления сущностей в админ-панели aiogram

import logging
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.exc import IntegrityError, NoResultFound # Импорт ошибок SQLAlchemy

# Импорт функций работы с БД
from utils import db

# Импорт общих FSM утилит и констант
# from .fsm.fsm_utils import CANCEL_FSM_CALLBACK # CANCEL_FSM_CALLBACK может быть не нужен, если используем специфичный DELETE_CANCEL_ACTION_PREFIX

# Импорт админских констант
from handlers.admin_constants_aiogram import (
    # Префиксы для запуска подтверждения (из детального просмотра)
    PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX, STOCK_DELETE_CONFIRM_CALLBACK_PREFIX,
    CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX, MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX,
    LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX,
    # Префиксы для действий внутри диалога подтверждения
    DELETE_EXECUTE_ACTION_PREFIX, DELETE_CANCEL_ACTION_PREFIX,
    # Для навигации после удаления/отмены (к списку или главному меню)
    BACK_TO_PRODUCTS_LIST_CALLBACK, BACK_TO_STOCK_LIST_CALLBACK,
    BACK_TO_CATEGORIES_LIST_CALLBACK, BACK_TO_MANUFACTURERS_LIST_CALLBACK,
    BACK_TO_LOCATIONS_LIST_CALLBACK, ADMIN_BACK_MAIN,
    # Для возврата к деталям после отмены (нужны префиксы детального просмотра)
    PRODUCT_DETAIL_VIEW_CALLBACK_PREFIX, STOCK_DETAIL_VIEW_CALLBACK_PREFIX,
    CATEGORY_DETAIL_VIEW_CALLBACK_PREFIX, MANUFACTURER_DETAIL_VIEW_CALLBACK_PREFIX,
    LOCATION_DETAIL_VIEW_CALLBACK_PREFIX,
)
# Импорт хелпера для отправки/редактирования сообщений и ENTITY_CONFIG
from handlers.admin_list_detail_handlers_aiogram import _send_or_edit_message, show_entity_detail, ENTITY_CONFIG
# Импорт функции показа главного меню для fallback
from handlers.admin_handlers_aiogram import show_admin_main_menu_aiogram


# Настройка логирования
logger = logging.getLogger(__name__)

# --- FSM States ---
class DeleteFSM(StatesGroup):
    """Состояние для подтверждения удаления."""
    confirm_delete = State()

# --- Helper Mapping ---
# Mapping entity type string to DB delete function and display name/callbacks
DELETE_ENTITY_CONFIG = {
    "product": {
        "name_singular": "Товар",
        "name_plural": "Товаров",
        "db_delete_func": db.delete_product,
        "list_callback": BACK_TO_PRODUCTS_LIST_CALLBACK, # Куда вернуться после успешного удаления
        "detail_prefix": PRODUCT_DETAIL_VIEW_CALLBACK_PREFIX # Для возврата к деталям при отмене
    },
    "stock": {
        "name_singular": "Запись остатка",
        "name_plural": "Остатков",
        "db_delete_func": db.delete_stock, # Это функция, принимающая product_id, location_id
        "list_callback": BACK_TO_STOCK_LIST_CALLBACK,
         "detail_prefix": STOCK_DETAIL_VIEW_CALLBACK_PREFIX
    },
    "category": {
        "name_singular": "Категория",
        "name_plural": "Категорий",
        "db_delete_func": db.delete_category,
        "list_callback": BACK_TO_CATEGORIES_LIST_CALLBACK,
         "detail_prefix": CATEGORY_DETAIL_VIEW_CALLBACK_PREFIX
    },
    "manufacturer": {
        "name_singular": "Производитель",
        "name_plural": "Производителей",
        "db_delete_func": db.delete_manufacturer,
        "list_callback": BACK_TO_MANUFACTURERS_LIST_CALLBACK,
         "detail_prefix": MANUFACTURER_DETAIL_VIEW_CALLBACK_PREFIX
    },
    "location": {
        "name_singular": "Местоположение",
        "name_plural": "Местоположений",
        "db_delete_func": db.delete_location,
        "list_callback": BACK_TO_LOCATIONS_LIST_CALLBACK,
         "detail_prefix": LOCATION_DETAIL_VIEW_CALLBACK_PREFIX
    },
}

# Mapping from the *_DELETE_CONFIRM_CALLBACK_PREFIX (from detail view) to the entity type string
DELETE_CONFIRM_PREFIX_TO_ENTITY_TYPE = {
    PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX: "product",
    STOCK_DELETE_CONFIRM_CALLBACK_PREFIX: "stock",
    CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX: "category",
    MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX: "manufacturer",
    LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX: "location",
}


# --- Handlers ---

async def start_delete_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Удалить' в детальном просмотре.
    Парсит ID сущности, получает ее данные и показывает сообщение с подтверждением.
    """
    await callback_query.answer() # Отвечаем на колбэк сразу

    data = callback_query.data
    entity_type = None
    entity_id_or_ids_str = None

    # Определяем тип сущности и извлекаем ID(ы) по префиксу из callback_data
    for prefix, etype in DELETE_CONFIRM_PREFIX_TO_ENTITY_TYPE.items():
        if data.startswith(prefix):
            entity_type = etype
            entity_id_or_ids_str = data[len(prefix):]
            break

    if not entity_type or not entity_id_or_ids_str:
        logger.error(f"Некорректный callback_data для старта подтверждения удаления: {data}")
        await _send_or_edit_message(callback_query, "❌ Ошибка: Не удалось определить сущность для удаления.")
        await state.clear() # Сбрасываем FSM
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    delete_config = DELETE_ENTITY_CONFIG.get(entity_type)
    if not delete_config:
         logger.error(f"Не найдена конфигурация удаления для сущности типа: {entity_type}")
         await _send_or_edit_message(callback_query, "❌ Ошибка конфигурации удаления.")
         await state.clear()
         await show_admin_main_menu_aiogram(callback_query, state)
         return

    # Попытка получить имя/идентификатор сущности для сообщения подтверждения
    entity_display_name = f"{delete_config['name_singular']} ID: `{entity_id_or_ids_str}`"
    try:
        # Используем ENTITY_CONFIG из admin_list_detail_handlers_aiogram для получения функции поиска
        entity_list_detail_config = ENTITY_CONFIG.get(entity_type)
        if entity_list_detail_config and 'db_get_by_id_func' in entity_list_detail_config:
            if entity_type == "stock":
                # Для остатка нужно получить продукт и локацию для отображения
                try:
                    prod_id, loc_id = map(int, entity_id_or_ids_str.split(':'))
                    stock_item = db.get_stock_by_ids(prod_id, loc_id)
                    if stock_item:
                         product = db.get_product_by_id(prod_id) # Получаем связанные сущности
                         location = db.get_location_by_id(loc_id)
                         prod_name = product.name if product else "Неизвестный товар"
                         loc_name = location.name if location else "Неизвестная локация"
                         # Форматируем имя для отображения, экранируя символы MarkdownV2
                         prod_name_esc = types.utils.markdown.text_decorations.escape_markdown(prod_name)
                         loc_name_esc = types.utils.markdown.text_decorations.escape_markdown(loc_name)
                         entity_display_name = f"Запись остатка (Товар: `{prod_name_esc}`, Локация: `{loc_name_esc}`)"
                    else:
                         # Если остаток не найден (хотя кнопка была показана), используем ID
                         entity_display_name = f"Запись остатка (ID: `{entity_id_or_ids_str}`)"

                except ValueError: # Некорректный формат prod_id:loc_id
                     logger.warning(f"Некорректный формат ID остатка {entity_id_or_ids_str} при получении имени для подтверждения.")
                     entity_display_name = f"Запись остатка (ID: `{entity_id_or_ids_str}`)" # Fallback

            else:
                # Для остальных сущностей с одиночным ID
                entity_id = int(entity_id_or_ids_str)
                entity = entity_list_detail_config['db_get_by_id_func'](entity_id)
                if entity:
                     # Используем атрибут 'name' если есть, иначе repr или ID. Экранируем.
                     entity_name = getattr(entity, 'name', str(entity))
                     entity_name_esc = types.utils.markdown.text_decorations.escape_markdown(str(entity_name))
                     entity_display_name = f"{delete_config['name_singular']} '{entity_name_esc}' (ID: `{entity_id_or_ids_str}`)"
                # else: entity not found, use default display name

    except Exception as e:
        logging.warning(f"Не удалось получить имя сущности {entity_type} ID {entity_id_or_ids_str} для сообщения подтверждения: {e}")
        # Игнорируем ошибку и используем default_display_name

    # Сохраняем контекст удаления в состоянии FSM
    await state.update_data(
        delete_entity_type=entity_type,
        delete_entity_id_or_ids_str=entity_id_or_ids_str,
        delete_entity_display_name=entity_display_name # Сохраняем сгенерированное имя для подтверждения/результата
    )

    # Переходим в состояние подтверждения
    await state.set_state(DeleteFSM.confirm_delete)

    text = (
        f"⚠️ **Подтверждение удаления** ⚠️\n\n"
        f"Вы уверены, что хотите удалить {entity_display_name}? Это действие **необратимо**."
    )

    # Кнопки: Да (Выполнить удаление), Нет (Отмена)
    # В callback_data кнопок действий включаем тип сущности и ID для последующей обработки
    keyboard = [
        [types.InlineKeyboardButton(
             text="✅ Да, удалить",
             callback_data=f"{DELETE_EXECUTE_ACTION_PREFIX}{entity_type}:{entity_id_or_ids_str}"
         )],
        [types.InlineKeyboardButton(
             text="❌ Нет, отмена",
             # Передаем тип сущности и ID, чтобы легко вернуться к детальному просмотру при отмене
             callback_data=f"{DELETE_CANCEL_ACTION_PREFIX}{entity_type}:{entity_id_or_ids_str}"
         )],
    ]
    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Редактируем сообщение детального просмотра, чтобы показать подтверждение
    await _send_or_edit_message(callback_query, text, reply_markup=reply_markup)


async def execute_delete(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Да, удалить' и выполняет фактическое удаление.
    """
    await callback_query.answer("Выполняю удаление...")

    # Получаем данные из callback_data (предпочтительнее, чем из state, если возможно)
    # Формат: {ACTION_PREFIX}{entity_type}:{entity_id_or_ids_str}
    data_parts = callback_query.data.split(":")
    if len(data_parts) < 3 or data_parts[0] != DELETE_EXECUTE_ACTION_PREFIX.strip(':'):
         logging.error(f"Некорректный callback_data для выполнения удаления: {callback_query.data}")
         await _send_or_edit_message(callback_query, "❌ Ошибка: Не удалось распознать данные для удаления.")
         await state.clear() # Сбрасываем FSM
         from .admin_handlers_aiogram import show_admin_main_menu_aiogram # Avoid circular import
         await show_admin_main_menu_aiogram(callback_query, state) # Возвращаемся в главное меню
         return

    entity_type = data_parts[1]
    entity_id_or_ids_str = ":".join(data_parts[2:]) # Объединяем оставшиеся части для составного ключа

    # Получаем display_name из state для сообщения результата, т.к. его сложно восстановить
    user_data = await state.get_data()
    entity_display_name = user_data.get("delete_entity_display_name", DELETE_ENTITY_CONFIG.get(entity_type, {}).get('name_singular', 'сущность'))

    delete_config = DELETE_ENTITY_CONFIG.get(entity_type)
    if not delete_config or 'db_delete_func' not in delete_config:
        logging.error(f"Не найдена конфигурация удаления или функция для сущности типа: {entity_type}")
        await _send_or_edit_message(callback_query, "❌ Ошибка конфигурации удаления.")
        await state.clear()
        from .admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)
        return

    db_delete_func = delete_config['db_delete_func']
    delete_successful = False
    error_text = None

    try:
        if entity_type == "stock":
             # Функция удаления остатка ожидает product_id, location_id как int
             try:
                 prod_id, loc_id = map(int, entity_id_or_ids_str.split(':'))
                 delete_successful = db_delete_func(prod_id, loc_id)
             except ValueError:
                 error_text = f"Некорректный формат ID остатка: `{entity_id_or_ids_str}`."
                 logging.error(error_text)
        else:
             # Остальные функции удаления ожидают одиночный int ID
             try:
                 entity_id = int(entity_id_or_ids_str)
                 delete_successful = db_delete_func(entity_id)
             except ValueError:
                 error_text = f"Некорректный формат ID для сущности типа {entity_type}: `{entity_id_or_ids_str}`."
                 logging.error(error_text)

    except IntegrityError:
         error_text = f"Не удалось удалить {entity_display_name}, так как с ним связаны другие записи в базе данных."
         logging.warning(f"IntegrityError при удалении {entity_type} ID {entity_id_or_ids_str}")
    except Exception as e:
        error_text = f"Произошла внутренняя ошибка при удалении {entity_display_name}: {e}"
        logging.error(f"Неизвестная ошибка при удалении {entity_type} ID {entity_id_or_ids_str}", exc_info=True)

    # Формируем сообщение о результате
    if delete_successful:
        result_text = f"✅ **{delete_config['name_singular']} успешно удален!** ({entity_display_name})"
    elif error_text:
        result_text = f"❌ **Ошибка удаления:** {error_text}"
    else:
         # Если delete_successful False, но error_text None, значит db_delete_func вернула False
         result_text = f"❌ Не удалось удалить {entity_display_name}. Возможно, она не найдена."


    # Редактируем сообщение подтверждения с результатом
    await _send_or_edit_message(callback_query, result_text)

    await state.clear() # Завершаем FSM

    # Навигация после завершения
    # Предлагаем вернуться к списку или в главное меню
    keyboard_buttons = []
    list_callback = delete_config.get('list_callback')
    if list_callback:
         # Кнопка "К списку <Сущность>"
         keyboard_buttons.append([types.InlineKeyboardButton(text=f"📋 К списку {delete_config['name_plural']}", callback_data=list_callback)])

    # Кнопка "Главное меню"
    keyboard_buttons.append([types.InlineKeyboardButton(text="⬅️ Главное меню", callback_data=ADMIN_BACK_MAIN)])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    # Отправляем новое сообщение с кнопками навигации
    await callback_query.message.answer("Выберите следующее действие:", reply_markup=reply_markup)


async def cancel_delete(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Нет, отмена'.
    """
    await callback_query.answer("Удаление отменено.")

    # Получаем данные из callback_data для возврата к детальному просмотру
    # Формат: {ACTION_PREFIX}{entity_type}:{entity_id_or_ids_str}
    data_parts = callback_query.data.split(":")
    if len(data_parts) < 3 or data_parts[0] != DELETE_CANCEL_ACTION_PREFIX.strip(':'):
         logging.error(f"Некорректный callback_data для отмены удаления: {callback_query.data}")
         await _send_or_edit_message(callback_query, "❌ Ошибка: Не удалось обработать отмену удаления.")
         await state.clear() # Сбрасываем FSM
         from .admin_handlers_aiogram import show_admin_main_menu_aiogram # Avoid circular import
         await show_admin_main_menu_aiogram(callback_query, state) # Возвращаемся в главное меню
         return

    entity_type = data_parts[1]
    entity_id_or_ids_str = ":".join(data_parts[2:]) # Объединяем оставшиеся части для составного клю

    user_data = await state.get_data()
    entity_display_name = user_data.get("delete_entity_display_name", DELETE_ENTITY_CONFIG.get(entity_type, {}).get('name_singular', 'сущности'))

    await state.clear() # Завершаем FSM

    # Сообщаем об отмене
    await _send_or_edit_message(callback_query, f"❌ **Удаление {entity_display_name} отменено.**")

    # Возвращаемся к детальному просмотру сущности (если возможно)
    delete_config = DELETE_ENTITY_CONFIG.get(entity_type)
    if delete_config and delete_config.get('detail_prefix'):
        # show_entity_detail ожидает callback_query, state, entity_type, entity_id_or_ids_str
        # Передаем текущий callback_query, очищенный state, и данные сущности
        # Примечание: state пуст после state.clear(), но это нормально для show_entity_detail,
        # которая получает данные из БД и не полагается на FSM state для отображения.
        # Важно, чтобы show_entity_detail могла использовать callback_query для редактирования/ответа.
        await show_entity_detail(callback_query, state, entity_type, entity_id_or_ids_str)
    else:
        # Если нет префикса деталей (не должно случиться с нашей config), возвращаемся в главное меню
        logging.warning(f"Не найден префикс деталей для сущности типа {entity_type}. Возврат в главное меню после отмены удаления.")
        from .admin_handlers_aiogram import show_admin_main_menu_aiogram
        await show_admin_main_menu_aiogram(callback_query, state)


# --- Router Registration ---

def register_delete_handlers(router: Router):
    """
    Регистрирует обработчики удаления сущностей в предоставленном роутере.
    """

    # ENTRY POINT: Обработчики нажатия кнопки 'Удалить' из детального просмотра
    # Используем F.data.startswith() для каждого типа сущности.
    # Эти хэндлеры запускают FSM подтверждения удаления.
    # Важно: эти хэндлеры должны быть зарегистрированы перед любыми более общими хэндлерами колбэков.
    router.callback_query.register(
        start_delete_confirmation,
        F.data.startswith(PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX)
    )
    router.callback_query.register(
        start_delete_confirmation,
        F.data.startswith(STOCK_DELETE_CONFIRM_CALLBACK_PREFIX)
    )
    router.callback_query.register(
        start_delete_confirmation,
        F.data.startswith(CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX)
    )
    router.callback_query.register(
        start_delete_confirmation,
        F.data.startswith(MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX)
    )
    router.callback_query.register(
        start_delete_confirmation,
        F.data.startswith(LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX)
    )


    # Обработчики нажатий кнопок в диалоге подтверждения удаления (когда FSM активен)
    # Фильтруем по состоянию FSM и префиксу действия
    router.callback_query.register(
        execute_delete,
        DeleteFSM.confirm_delete, # Хэндлер активен только в состоянии confirm_delete
        F.data.startswith(DELETE_EXECUTE_ACTION_PREFIX)
    )
    router.callback_query.register(
        cancel_delete,
        DeleteFSM.confirm_delete, # Хэндлер активен только в состоянии confirm_delete
        F.data.startswith(DELETE_CANCEL_ACTION_PREFIX)
    )

    # Примечание: Общий хэндлер отмены (cancel_fsm_handler из fsm_utils)
    # должен быть зарегистрирован отдельно на уровне диспетчера или основного админского роутера
    # на State("*") и Text(CANCEL_FSM_CALLBACK).
    # Однако, используя DELETE_CANCEL_ACTION_PREFIX для кнопки "Нет, отмена"
    # и наш специфичный хэндлер cancel_delete, мы получаем более точную навигацию обратно
    # к детальному просмотру после отмены. Если бы мы использовали CANCEL_FSM_CALLBACK,
    # сработал бы общий хэндлер, который скорее всего вернул бы в главное меню.

