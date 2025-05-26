# your_bot/handlers/admin_constants_aiogram.py
# Константы для callback_data административного меню в aiogram

# Основное меню админа
ADMIN_MAIN_CALLBACK = 'admin_main'

# Меню разделов
ADMIN_PRODUCTS_CALLBACK = 'admin_products'
ADMIN_STOCK_CALLBACK = 'admin_stock'
ADMIN_CATEGORIES_CALLBACK = 'admin_categories'
ADMIN_MANUFACTURERS_CALLBACK = 'admin_manufacturers'
ADMIN_LOCATIONS_CALLBACK = 'admin_locations'

# Кнопки "Назад"
ADMIN_BACK_MAIN = 'admin_back_main' # Назад в главное админ-меню

# Константы действий для сущностей (добавление, список)
PRODUCT_ADD_CALLBACK = "product_add_action"
PRODUCT_LIST_CALLBACK = "product_list_action"
STOCK_ADD_CALLBACK = "stock_add_action"
STOCK_LIST_CALLBACK = "stock_list_action"
CATEGORY_ADD_CALLBACK = "category_add_action"
CATEGORY_LIST_CALLBACK = "category_list_action"
MANUFACTURER_ADD_CALLBACK = "manufacturer_add_action"
MANUFACTURER_LIST_CALLBACK = "manufacturer_list_action"
LOCATION_ADD_CALLBACK = "location_add_action"
LOCATION_LIST_CALLBACK = "location_list_action"

# --- Константы для LIST, DETAIL, PAGINATION ---

# Базовый префикс для колбэков пагинации
PAGINATION_CALLBACK_PREFIX = "page:" # Определен в fsm_utils, но полезно иметь здесь для справки

# Префиксы для пагинации списков
PRODUCT_PAGE_CALLBACK_PREFIX = "prod_page:"
STOCK_PAGE_CALLBACK_PREFIX = "stock_page:"
CATEGORY_PAGE_CALLBACK_PREFIX = "cat_page:"
MANUFACTURER_PAGE_CALLBACK_PREFIX = "man_page:"
LOCATION_PAGE_CALLBACK_PREFIX = "loc_page:"

# Префиксы для детального просмотра сущности по ID(s)
PRODUCT_DETAIL_VIEW_CALLBACK_PREFIX = "prod_detail:"       # f"{PRODUCT_DETAIL_VIEW_CALLBACK_PREFIX}{product_id}"
STOCK_DETAIL_VIEW_CALLBACK_PREFIX = "stock_detail:"       # f"{STOCK_DETAIL_VIEW_CALLBACK_PREFIX}{product_id}:{location_id}"
CATEGORY_DETAIL_VIEW_CALLBACK_PREFIX = "cat_detail:"      # f"{CATEGORY_DETAIL_VIEW_CALLBACK_PREFIX}{category_id}"
MANUFACTURER_DETAIL_VIEW_CALLBACK_PREFIX = "man_detail:"  # f"{MANUFACTURER_DETAIL_VIEW_CALLBACK_PREFIX}{manufacturer_id}"
LOCATION_DETAIL_VIEW_CALLBACK_PREFIX = "loc_detail:"      # f"{LOCATION_DETAIL_VIEW_CALLBACK_PREFIX}{location_id}"

# Префиксы для инициации действий (редактирование, удаление) с сущностью по ID(s) из ДЕТАЛЬНОГО ПРОСМОТРА
# Эти префиксы запускают соответствующие FSM
PRODUCT_UPDATE_INIT_CALLBACK_PREFIX = "prod_update_init:"       # f"{PRODUCT_UPDATE_INIT_CALLBACK_PREFIX}{product_id}"
STOCK_UPDATE_INIT_CALLBACK_PREFIX = "stock_update_init:"       # f"{STOCK_UPDATE_INIT_CALLBACK_PREFIX}{product_id}:{location_id}"
CATEGORY_UPDATE_INIT_CALLBACK_PREFIX = "cat_update_init:"      # f"{CATEGORY_UPDATE_INIT_CALLBACK_PREFIX}{category_id}"
MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX = "man_update_init:"  # f"{MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX}{manufacturer_id}"
LOCATION_UPDATE_INIT_CALLBACK_PREFIX = "loc_update_init:"      # f"{LOCATION_UPDATE_INIT_CALLBACK_PREFIX}{location_id}"

# Префиксы для ИНИЦИАЦИИ ПОДТВЕРЖДЕНИЯ удаления с сущностью по ID(s) из ДЕТАЛЬНОГО ПРОСМОТРА
# Эти префиксы запускают FSM/диалог подтверждения удаления
PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX = "prod_delete_confirm:"      # f"{PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX}{product_id}"
STOCK_DELETE_CONFIRM_CALLBACK_PREFIX = "stock_delete_confirm:"      # f"{STOCK_DELETE_CONFIRM_CALLBACK_PREFIX}{product_id}:{location_id}"
CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX = "cat_delete_confirm:"     # f"{CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX}{category_id}"
MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX = "man_delete_confirm:" # f"{MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX}{manufacturer_id}"
LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX = "loc_delete_confirm:"     # f"{LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX}{location_id}"

# Константы для возврата к списку из детального просмотра
BACK_TO_PRODUCTS_LIST_CALLBACK = "back_to_prod_list"
BACK_TO_STOCK_LIST_CALLBACK = "back_to_stock_list"
BACK_TO_CATEGORIES_LIST_CALLBACK = "back_to_cat_list"
BACK_TO_MANUFACTURERS_LIST_CALLBACK = "back_to_man_list"
BACK_TO_LOCATIONS_LIST_CALLBACK = "back_to_loc_list"

# --- Константы для FSM Update ---

# Префиксы для колбэков выбора/пагинации внутри FSM Update (для связанных сущностей)
# Важно, чтобы они были уникальны
UPDATE_CAT_PARENT_PAGE_PREFIX = "upd_cat_par_page:"
UPDATE_CAT_PARENT_SEL_PREFIX = "upd_cat_par_sel:"

UPDATE_PROD_CAT_PAGE_PREFIX = "upd_prod_cat_page:"
UPDATE_PROD_CAT_SEL_PREFIX = "upd_prod_cat_sel:"

UPDATE_PROD_MAN_PAGE_PREFIX = "upd_prod_man_page:"
UPDATE_PROD_MAN_SEL_PREFIX = "upd_prod_man_sel:"

# Константы для кнопок "Пропустить" или "Оставить текущее значение"
# SKIP_INPUT_MARKER = "-" # Определен в fsm_utils
KEEP_CURRENT_PARENT_CALLBACK = "upd_cat_keep_parent"
KEEP_CURRENT_CATEGORY_CALLBACK = "upd_prod_keep_cat"
KEEP_CURRENT_MANUFACTURER_CALLBACK = "upd_prod_keep_man"
# Для остатка только количество, пропуска нет, только ввод нового или отмена FSM

# FSM confirmation/cancel callbacks are in fsm_utils.py

# --- Константы для FSM Delete (подтверждение, отмена, выполнение) ---
# Action prefixes used *within* the delete confirmation dialog buttons
# Формат callback_data: {ACTION_PREFIX}{entity_type_string}:{entity_id_or_ids_str}
DELETE_EXECUTE_ACTION_PREFIX = "del_act_exec:" # Callback для кнопки "✅ Да, удалить"
DELETE_CANCEL_ACTION_PREFIX = "del_act_cancel:" # Callback для кнопки "❌ Нет, отмена"

# FSM общие константы (импортированы из fsm_utils для централизованного доступа)
CANCEL_FSM_CALLBACK = "cancel_fsm"
PAGINATION_CALLBACK_PREFIX = "page:"

