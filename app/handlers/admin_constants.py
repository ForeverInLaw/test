# your_bot/handlers/admin_constants.py
# Константы для колбэк-данных административного меню и состояний ConversationHandler

# Основное меню админа
ADMIN_MAIN_CALLBACK = 'admin_main'

# Меню разделов
ADMIN_PRODUCTS_CALLBACK = 'admin_products'
ADMIN_STOCK_CALLBACK = 'admin_stock'
ADMIN_CATEGORIES_CALLBACK = 'admin_categories'
ADMIN_MANUFACTURERS_CALLBACK = 'admin_manufacturers'
ADMIN_LOCATIONS_CALLBACK = 'admin_locations'

# Действия внутри меню Товаров
ADMIN_PRODUCTS_LIST = 'admin_products_list'
ADMIN_PRODUCTS_ADD = 'admin_products_add'
ADMIN_PRODUCTS_FIND = 'admin_products_find'
ADMIN_PRODUCTS_UPDATE = 'admin_products_update' # Добавлено
ADMIN_PRODUCTS_DETAIL = 'admin_products_detail'   # Добавлено для детального просмотра (используется как префикс)
ADMIN_PRODUCTS_DELETE_CONFIRM = 'admin_products_delete_confirm' # Добавлено для подтверждения удаления (используется как префикс entry point)


# Действия внутри меню Остатков (ADMIN_STOCK_ADD теперь подразумевает Добавление/Изменение)
ADMIN_STOCK_LIST = 'admin_stock_list'
ADMIN_STOCK_ADD = 'admin_stock_add' # Добавление/Изменение остатка (используется как префикс entry point)
ADMIN_STOCK_FIND = 'admin_stock_find' # (используется как префикс entry point)
ADMIN_STOCK_DETAIL = 'admin_stock_detail'     # Добавлено для детального просмотра (используется как префикс)
ADMIN_STOCK_DELETE_CONFIRM = 'admin_stock_delete_confirm' # Добавлено для подтверждения удаления (используется как префикс entry point)


# Действия внутри меню Категорий
ADMIN_CATEGORIES_LIST = 'admin_categories_list'
ADMIN_CATEGORIES_ADD = 'admin_categories_add' # (используется как префикс entry point)
ADMIN_CATEGORIES_FIND = 'admin_categories_find' # (используется как префикс entry point)
ADMIN_CATEGORIES_UPDATE = 'admin_categories_update' # Добавлено (используется как префикс entry point)
ADMIN_CATEGORIES_DETAIL = 'admin_categories_detail' # Добавлено для детального просмотра (используется как префикс)
ADMIN_CATEGORIES_DELETE_CONFIRM = 'admin_categories_delete_confirm' # Добавлено для подтверждения удаления (используется как префикс entry point)


# Действия внутри меню Производителей
ADMIN_MANUFACTURERS_LIST = 'admin_manufacturers_list'
ADMIN_MANUFACTURERS_ADD = 'admin_manufacturers_add' # (используется как префикс entry point)
ADMIN_MANUFACTURERS_FIND = 'admin_manufacturers_find' # (используется как префикс entry point)
ADMIN_MANUFACTURERS_UPDATE = 'admin_manufacturers_update' # Добавлено (используется как префикс entry point)
ADMIN_MANUFACTURERS_DETAIL = 'admin_manufacturers_detail' # Добавлено для детального просмотра (используется как префикс)
ADMIN_MANUFACTURERS_DELETE_CONFIRM = 'admin_manufacturers_delete_confirm' # Добавлено для подтверждения удаления (используется как префикс entry point)


# Действия внутри меню Местоположений
ADMIN_LOCATIONS_LIST = 'admin_locations_list'
ADMIN_LOCATIONS_ADD = 'admin_locations_add' # (используется как префикс entry point)
ADMIN_LOCATIONS_FIND = 'admin_locations_find' # (используется как префикс entry point)
ADMIN_LOCATIONS_UPDATE = 'admin_locations_update' # Добавлено (используется как префикс entry point)
ADMIN_LOCATIONS_DETAIL = 'admin_locations_detail' # Добавлено для детального просмотра (используется как префикс)
ADMIN_LOCATIONS_DELETE_CONFIRM = 'admin_locations_delete_confirm' # Добавлено для подтверждения удаления (используется как префикс entry point)


# Кнопки "Назад" и навигации
ADMIN_BACK_MAIN = 'admin_back_main'
ADMIN_BACK_PRODUCTS_MENU = 'admin_back_products_menu'
ADMIN_BACK_STOCK_MENU = 'admin_back_stock_menu'
ADMIN_BACK_CATEGORIES_MENU = 'admin_back_categories_menu'
ADMIN_BACK_MANUFACTURERS_MENU = 'admin_back_manufacturers_menu'
ADMIN_BACK_LOCATIONS_MENU = 'admin_back_locations_menu'

# Константы для пагинации, деталей, редактирования и выполнения удаления (используются как префикс в callback_data)
ADMIN_LIST_PAGE_PREFIX = '_page_' # Пример: admin_products_list_page_2
ADMIN_DETAIL_PREFIX = '_detail_'   # Пример: admin_products_detail_123 (deprecated in favour of specific entity detail prefixes)
ADMIN_EDIT_PREFIX = '_edit_' # Пример: admin_products_detail_123_edit_123 (кнопка Edit на деталях)
ADMIN_DELETE_CONFIRM_PREFIX = '_delete_confirm_' # Пример: admin_products_detail_123_delete_confirm_123 (кнопка Delete на деталях)
ADMIN_DELETE_EXECUTE_PREFIX = '_delete_execute_' # Пример: product_delete_execute_123 (кнопка "Да, удалить" в диалоге подтверждения)


# Префикс для всех админских колбэков
ADMIN_CALLBACK_PATTERN = '^admin_' # Общий паттерн для CallbackQueryHandler, перехватывающий навигацию, LIST (без пагинации), DETAIL (без ID)


# --- Состояния ConversationHandler ---
# Используем числовые константы для состояний.
# Важно, чтобы значения были уникальны В ЦЕЛОМ по приложению, если используется один большой ConversationHandler.
# В текущей архитектуре, где каждый диалог - отдельный ConversationHandler, состояния локальны для каждого Handler'а (обычно 0, 1, 2...).
# Однако, для Entry Points и Fallbacks ConvHandler'ы должны использовать импортированные константы из этого файла.
# Мы переопределим состояния локально в каждом файле ConversationHandler'ов (0, 1, 2...),
# а здесь оставим константы для Entry Points и Fallbacks, как они используются в main.py.
# Нумерация ниже приведена для информации и соответствия ref, но состояния внутри ConvHandler'ов будут нумероваться с 0.

# Состояния для добавления товара
PRODUCT_ADD_NAME = 0
PRODUCT_ADD_DESCRIPTION = 1
PRODUCT_ADD_PRICE = 2
PRODUCT_ADD_CATEGORY = 3 # Ожидание ID категории
PRODUCT_ADD_MANUFACTURER = 4 # Ожидание ID производителя
# PRODUCT_ADD_LOCATION = 5 # Не используется в текущей реализации добавления товара
PRODUCT_ADD_CONFIRM = 5 # Ожидание подтверждения (для CallbackQueryHandler)

# Состояние для поиска товара
PRODUCT_FIND_QUERY = 7

# Состояния для добавления/изменения остатка (ADD и UPDATE объединены)
STOCK_OPERATION_PRODUCT_ID = 8 # Ожидание ID товара
STOCK_OPERATION_LOCATION_ID = 9 # Ожидание ID местоположения
STOCK_OPERATION_QUANTITY = 10 # Ожидание количества (выполнение Add/Update происходит здесь)

# Состояния для поиска остатка (теперь 2 шага)
STOCK_FIND_PRODUCT_NAME = 11 # Ожидание названия товара для поиска
STOCK_FIND_LOCATION_NAME = 12 # Ожидание названия локации для поиска (выполнение Find происходит здесь)

# Состояния для добавления категории
CATEGORY_ADD_NAME = 13 # Ожидание названия категории
CATEGORY_ADD_PARENT_ID = 14 # Ожидание ID родителя

# Состояние для поиска категории
CATEGORY_FIND_QUERY = 15

# Состояния для добавления производителя
MANUFACTURER_ADD_NAME = 16 # Ожидание названия

# Состояние для поиска производителя
MANUFACTURER_FIND_QUERY = 17

# Состояния для добавления местоположения
LOCATION_ADD_NAME = 18 # Ожидание названия

# Состояние для поиска местоположения
LOCATION_FIND_QUERY = 19

# Состояния для операций обновления (начало нумерации для UPDATE диалогов)
PRODUCT_UPDATE_ID = 20 # Ожидание ID товара для обновления
PRODUCT_UPDATE_NAME = 21 # Ожидание нового названия
PRODUCT_UPDATE_DESCRIPTION = 22 # Ожидание нового описания
PRODUCT_UPDATE_PRICE = 23 # Ожидание новой цены
PRODUCT_UPDATE_CATEGORY_ID = 24 # Ожидание нового ID категории
PRODUCT_UPDATE_MANUFACTURER_ID = 25 # Ожидание нового ID производителя
PRODUCT_UPDATE_CONFIRM = 26 # Ожидание подтверждения обновления (для CallbackQueryHandler)

CATEGORY_UPDATE_ID = 27 # Ожидание ID категории для обновления
CATEGORY_UPDATE_NAME = 28 # Ожидание нового названия
CATEGORY_UPDATE_PARENT_ID = 29 # Ожидание нового ID родителя

MANUFACTURER_UPDATE_ID = 30 # Ожидание ID производителя для обновления
MANUFACTURER_UPDATE_NAME = 31 # Ожидание нового названия

LOCATION_UPDATE_ID = 32 # Ожидание ID местоположения для обновления
LOCATION_UPDATE_NAME = 33 # Ожидание нового названия

# Состояния для операций удаления (используется одно состояние для подтверждения)
# Числовые значения состояний для удаления определены локально в каждом ConversationHandler (обычно 0)


# Конец ConversationHandler
CONVERSATION_END = -1 # Используется ConversationHandler.END

# Константа для количества элементов на странице в списках
PAGE_SIZE = 10
