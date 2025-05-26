# your_bot/main.py
# Основной файл бота (модифицированный для интеграции админ меню и CRUD диалогов)

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Импорт хэндлеров и констант для админ меню
from handlers.admin_menus import (
    show_admin_main_menu,
    handle_admin_callback,
    is_admin,
    # Импортируем функции отображения меню для fallbacks (используются в cancel handlers)
    show_products_menu, show_stock_menu, show_categories_menu,
    show_manufacturers_menu, show_locations_menu,
    # Импортируем хэндлеры для DETAIL, которые вызываются напрямую из handle_admin_callback
    handle_products_detail, handle_stock_detail, handle_categories_detail,
    handle_manufacturers_detail, handle_locations_detail,
    # Импортируем хэндлеры для LIST, которые вызываются напрямую из handle_admin_callback
    handle_products_list, handle_stock_list, handle_categories_list,
    handle_manufacturers_list, handle_locations_list
)
from handlers.admin_constants import (
     ADMIN_CALLBACK_PATTERN,
     # Импортируем константы колбэков-entry_points для регистрации ConversationHandler
     ADMIN_PRODUCTS_ADD, ADMIN_PRODUCTS_FIND, ADMIN_PRODUCTS_UPDATE, ADMIN_PRODUCTS_DELETE_CONFIRM,
     ADMIN_STOCK_ADD, ADMIN_STOCK_FIND, ADMIN_STOCK_DELETE_CONFIRM,
     ADMIN_CATEGORIES_ADD, ADMIN_CATEGORIES_FIND, ADMIN_CATEGORIES_UPDATE, ADMIN_CATEGORIES_DELETE_CONFIRM,
     ADMIN_MANUFACTURERS_ADD, ADMIN_MANUFACTURERS_FIND, ADMIN_MANUFACTURERS_UPDATE, ADMIN_MANUFACTURERS_DELETE_CONFIRM,
     ADMIN_LOCATIONS_ADD, ADMIN_LOCATIONS_FIND, ADMIN_LOCATIONS_UPDATE, ADMIN_LOCATIONS_DELETE_CONFIRM,
     # Импортируем префиксы колбэков, которые не являются entry points для ConvHandler
     ADMIN_DETAIL_PREFIX, ADMIN_LIST_PAGE_PREFIX
     # Состояния ConversationHandler используются локально в файлах с хэндлерами
)

# Импорт ConversationHandler'ов из новых файлов
from handlers.admin_product_conversations import (
    add_product_conv_handler, find_product_conv_handler, update_product_conv_handler, delete_product_conv_handler # Добавлен delete
)
from handlers.admin_stock_conversations import (
    add_stock_conv_handler, find_stock_conv_handler, delete_stock_conv_handler # Добавлен delete
)
from handlers.admin_category_conversations import (
    add_category_conv_handler, find_category_conv_handler, update_category_conv_handler, delete_category_conv_handler # Добавлен delete
)
from handlers.admin_manufacturer_conversations import (
    add_manufacturer_conv_handler, find_manufacturer_conv_handler, update_manufacturer_conv_handler, delete_manufacturer_conv_handler # Добавлен delete
)
from handlers.admin_location_conversations import (
    add_location_conv_handler, find_location_conv_handler, update_location_conv_handler, delete_location_conv_handler # Добавлен delete
)

# Импорт модуля базы данных
from utils import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Пример обычного хэндлера
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Используйте команду /admin для доступа к административному меню (если у вас есть права).')


def main() -> None:
    """Запускает бота."""
    # Инициализация базы данных
    db.init_db()
    logger.info("База данных инициализирована.")

    # Создание Application и передача токена бота
    # Замените "7898779323:AAGODe-tArATVTcnJKiqkJsD6TrKo7kK9IY" на ваш реальный токен
    application = Application.builder().token("7898779323:AAGODe-tArATVTcnJKiqkJsD6TrKo7kK9IY").build()

    # --- Регистрация обработчиков ---

    # Обычные хэндлеры
    application.add_handler(CommandHandler("start", start))

    # Регистрация команды для открытия админ меню (доступ только для админов через проверку в show_admin_main_menu)
    application.add_handler(CommandHandler("admin", show_admin_main_menu))

    # Регистрация ConversationHandler'ов ДЛЯ ВСЕХ МНОГОШАГОВЫХ ОПЕРАЦИЙ (ADD, FIND, UPDATE, DELETE CONFIRM).
    # ВАЖНО: Регистрировать их НУЖНО ДО основного CallbackQueryHandler с общим паттерном ADMIN_CALLBACK_PATTERN,
    # чтобы колбэки, инициирующие диалоги (ADMIN_*_ADD, ADMIN_*_FIND, ADMIN_*_UPDATE, ADMIN_*_DELETE_CONFIRM),
    # были перехвачены соответствующими ConversationHandler'ами.
    application.add_handler(add_product_conv_handler)
    application.add_handler(find_product_conv_handler)
    application.add_handler(update_product_conv_handler)
    application.add_handler(delete_product_conv_handler) # Регистрация delete

    application.add_handler(add_stock_conv_handler)
    application.add_handler(find_stock_conv_handler)
    application.add_handler(delete_stock_conv_handler) # Регистрация delete

    application.add_handler(add_category_conv_handler)
    application.add_handler(find_category_conv_handler)
    application.add_handler(update_category_conv_handler)
    application.add_handler(delete_category_conv_handler) # Регистрация delete

    application.add_handler(add_manufacturer_conv_handler)
    application.add_handler(find_manufacturer_conv_handler)
    application.add_handler(update_manufacturer_conv_handler)
    application.add_handler(delete_manufacturer_conv_handler) # Регистрация delete

    application.add_handler(add_location_conv_handler)
    application.add_handler(find_location_conv_handler)
    application.add_handler(update_location_conv_handler)
    application.add_handler(delete_location_conv_handler) # Регистрация delete


    # Регистрация CallbackQueryHandler'ов для ОДНОШАГОВЫХ ОПЕРАЦИЙ или ENTRY POINTS,
    # которые не инициируют ConvHandler (навигация, LIST, DETAIL).
    # Используем более специфичные паттерны ПЕРЕД общим ADMIN_CALLBACK_PATTERN.

    # Хэндлеры для отображения деталей (колбэк формата admin_entity_detail_ID(s))
    application.add_handler(CallbackQueryHandler(handle_products_detail, pattern=rf'^{ADMIN_PRODUCTS_DETAIL}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_stock_detail, pattern=rf'^{ADMIN_STOCK_DETAIL}\d+_\d+$')) # Stock details use two IDs
    application.add_handler(CallbackQueryHandler(handle_categories_detail, pattern=rf'^{ADMIN_CATEGORIES_DETAIL}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_manufacturers_detail, pattern=rf'^{ADMIN_MANUFACTURERS_DETAIL}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_locations_detail, pattern=rf'^{ADMIN_LOCATIONS_DETAIL}\d+$'))

    # Хэндлеры для отображения списков с пагинацией (колбэк формата admin_entity_list(_page_X)?)
    # Обратите внимание, что handle_entity_list обрабатывает оба формата
    # Простой list колбэк обрабатывается ниже в общем handle_admin_callback,
    # но колбэки пагинации ('_page_X') должны быть перехвачены здесь.
    application.add_handler(CallbackQueryHandler(handle_products_list, pattern=rf'^{ADMIN_PRODUCTS_LIST}{ADMIN_LIST_PAGE_PREFIX}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_stock_list, pattern=rf'^{ADMIN_STOCK_LIST}{ADMIN_LIST_PAGE_PREFIX}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_categories_list, pattern=rf'^{ADMIN_CATEGORIES_LIST}{ADMIN_LIST_PAGE_PREFIX}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_manufacturers_list, pattern=rf'^{ADMIN_MANUFACTURERS_LIST}{ADMIN_LIST_PAGE_PREFIX}\d+$'))
    application.add_handler(CallbackQueryHandler(handle_locations_list, pattern=rf'^{ADMIN_LOCATIONS_LIST}{ADMIN_LIST_PAGE_PREFIX}\d+$'))


    # Регистрация основного CallbackQueryHandler для всех админских колбэков,
    # которые НЕ являются entry_points ConversationHandler'ов ИЛИ специфичными
    # одношаговыми колбэками выше (т.е. основная навигация и первый клик по "Список").
    # ВАЖНО: Регистрировать ПОСЛЕ всех более специфичных CallbackQueryHandler'ов и ConversationHandler'ов.
    # handle_admin_callback теперь вызывает show_menus, handle_entity_list (для первой страницы), handle_entity_detail.
    application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=ADMIN_CALLBACK_PATTERN))


    # Запуск бота (режим polling)
    logger.info("Бот запущен в режиме polling.")
    application.run_polling(poll_interval=3.0)

    # Закрытие базы данных при остановке
    db.close_db()
    logger.info("Соединение с базой данных закрыто.")


if __name__ == "__main__":
    main()