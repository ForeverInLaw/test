# your_bot/bot.py
# Main application entry point for the Telegram bot.
# Initializes all components, configures logging, sets up database and Redis connections,
# registers handlers and middlewares, and starts the bot.

import asyncio
import logging
import sys
import os # Импорт os для получения BOT_TOKEN из переменных окружения
from typing import Dict, Any
from dotenv import load_dotenv # Импорт для загрузки .env файла

# Удалите или закомментируйте старые импорты, связанные со старой структурой админки/хэндлеров
# from handlers.admin_delete_handlers_aiogram import register_delete_handlers # <-- Удалить
# from app.handlers import common_handlers, user_handlers, admin_handlers # <-- Возможно, удалить admin_handlers

from aiogram import Bot, Dispatcher, types, Router # Импорт Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage # Импорт MemoryStorage как fallback/альтернатива
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.state import State # Импорт State для фильтра State("*")


# Импорт функций инициализации БД
# Убедитесь, что utils/db.py находится по этому пути
from utils.db import init_db, close_db

# Импорт общих админских хэндлеров (навигация, команда /admin, ENTRY POINTы для FSM/List)
# Убедитесь, что admin_handlers_aiogram.py создан
from handlers.admin_handlers_aiogram import (
    handle_admin_command,
    admin_menu_navigation_handler,
    handle_product_add, handle_stock_add, handle_category_add, handle_manufacturer_add, handle_location_add, # ENTRY POINTs для ADD FSMs
    handle_product_list, handle_stock_list, handle_category_list, handle_manufacturer_list, handle_location_list, # ENTRY POINTs для List views
    # Также импортируем show_admin_main_menu_aiogram для использования в cancel_fsm_handler, если он там импортируется
    show_admin_main_menu_aiogram
)

# Импорт констант админ-меню
# Убедитесь, что admin_constants_aiogram.py создан
from handlers.admin_constants_aiogram import (
    # Основные меню/навигация
    ADMIN_PRODUCTS_CALLBACK, ADMIN_STOCK_CALLBACK, ADMIN_CATEGORIES_CALLBACK,
    ADMIN_MANUFACTURERS_CALLBACK, ADMIN_LOCATIONS_CALLBACK, ADMIN_BACK_MAIN,
    # Действия (используются как фильтры)
    PRODUCT_ADD_CALLBACK, PRODUCT_LIST_CALLBACK,
    STOCK_ADD_CALLBACK, STOCK_LIST_CALLBACK,
    CATEGORY_ADD_CALLBACK, CATEGORY_LIST_CALLBACK,
    MANUFACTURER_ADD_CALLBACK, MANUFACTURER_LIST_CALLBACK,
    LOCATION_ADD_CALLBACK, LOCATION_LIST_CALLBACK,
    # Общие FSM константы из fsm_utils (могут быть импортированы из fsm_utils напрямую, но для фильтров удобнее здесь)
    CANCEL_FSM_CALLBACK, # CONFIRM_ACTION_CALLBACK нужен в FSM модулях, не здесь
    # Константы для List/Detail/Update/Delete (нужны как фильтры)
    PAGINATION_CALLBACK_PREFIX, PRODUCT_PAGE_CALLBACK_PREFIX, STOCK_PAGE_CALLBACK_PREFIX, CATEGORY_PAGE_CALLBACK_PREFIX, MANUFACTURER_PAGE_CALLBACK_PREFIX, LOCATION_PAGE_CALLBACK_PREFIX, # Для фильтрации пагинации
    PRODUCT_DETAIL_VIEW_CALLBACK_PREFIX, STOCK_DETAIL_VIEW_CALLBACK_PREFIX, CATEGORY_DETAIL_VIEW_CALLBACK_PREFIX, MANUFACTURER_DETAIL_VIEW_CALLBACK_PREFIX, LOCATION_DETAIL_VIEW_CALLBACK_PREFIX, # Для фильтрации деталей
    BACK_TO_PRODUCTS_LIST_CALLBACK, BACK_TO_STOCK_LIST_CALLBACK, BACK_TO_CATEGORIES_LIST_CALLBACK, BACK_TO_MANUFACTURERS_LIST_CALLBACK, BACK_TO_LOCATIONS_LIST_CALLBACK, # Для фильтрации "Назад к списку"
    PRODUCT_UPDATE_INIT_CALLBACK_PREFIX, STOCK_UPDATE_INIT_CALLBACK_PREFIX, CATEGORY_UPDATE_INIT_CALLBACK_PREFIX, MANUFACTURER_UPDATE_INIT_CALLBACK_PREFIX, LOCATION_UPDATE_INIT_CALLBACK_PREFIX, # Для фильтрации инициации обновления
    PRODUCT_DELETE_CONFIRM_CALLBACK_PREFIX, STOCK_DELETE_CONFIRM_CALLBACK_PREFIX, CATEGORY_DELETE_CONFIRM_CALLBACK_PREFIX, MANUFACTURER_DELETE_CONFIRM_CALLBACK_PREFIX, LOCATION_DELETE_CONFIRM_CALLBACK_PREFIX, # Для фильтрации инициации удаления (подтверждение)
    DELETE_EXECUTE_ACTION_PREFIX, DELETE_CANCEL_ACTION_PREFIX # Для фильтрации действий внутри FSM удаления
)

# Импорт общих FSM утилит (для хэндлера отмены)
# Убедитесь, что handlers/fsm/fsm_utils.py создан
from handlers.fsm.fsm_utils import cancel_fsm_handler

# Импорт функций регистрации FSM-обработчиков добавления
# Убедитесь, что файлы handlers/fsm/*_add_fsm.py созданы
from handlers.fsm.category_add_fsm import register_category_add_handlers
from handlers.fsm.manufacturer_add_fsm import register_manufacturer_add_handlers
from handlers.fsm.location_add_fsm import register_location_add_handlers
from handlers.fsm.product_add_fsm import register_product_add_handlers
from handlers.fsm.stock_add_fsm import register_stock_add_handlers

# Импорт функций регистрации FSM-обработчиков обновления
# Убедитесь, что файлы handlers/fsm/*_update_fsm.py созданы
from handlers.fsm.category_update_fsm import register_category_update_handlers
from handlers.fsm.manufacturer_update_fsm import register_manufacturer_update_handlers
from handlers.fsm.location_update_fsm import register_location_update_handlers
from handlers.fsm.product_update_fsm import register_product_update_handlers
from handlers.fsm.stock_update_fsm import register_stock_update_handlers

# Импорт функции регистрации обработчиков списков/деталей/инициации CRUD
# Убедитесь, что handlers/admin_list_detail_handlers_aiogram.py создан
from handlers.admin_list_detail_handlers_aiogram import register_list_detail_handlers

# Импорт функции регистрации обработчиков удаления
# Убедитесь, что handlers/admin_delete_handlers_aiogram.py создан
from handlers.admin_delete_handlers_aiogram import register_delete_handlers


# Импорт LanguageMiddleware из структуры пользователя
from app.middlewares.language_middleware import LanguageMiddleware # <-- Ваш существующий импорт

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO), # Чтение LOG_LEVEL из env
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main application function."""
    logger.info("Starting Telegram bot application...")

    # Load environment variables from .env file
    load_dotenv()
    logger.info("Environment variables loaded from .env file")

    # Получение токена бота из переменных окружения
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        logger.critical("BOT_TOKEN environment variable not set!")
        sys.exit(1)

    bot = None
    dp = None
    storage = None # Объявляем storage заранее

    try:
        # Initialize bot with default properties, set parse_mode to HTML for better message formatting
        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML) # <-- Используем HTML для форматирования
        )

        # Initialize Redis storage for FSM
        # Используем REDIS_URL из settings, как в вашем коде TMPkC
        redis_url = os.environ.get("REDIS_URL") # Чтение REDIS_URL из env
        if redis_url:
            try:
                storage = RedisStorage.from_url(redis_url)
                logger.info("Redis storage initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis storage from URL {redis_url}: {e}")
                logger.info("Falling back to memory storage (FSM state will not persist)")
                storage = MemoryStorage()
        else:
             logger.warning("REDIS_URL environment variable not set. Using MemoryStorage (FSM state will not persist).")
             storage = MemoryStorage()


        # Initialize dispatcher
        dp = Dispatcher(storage=storage)

        # Initialize database
        try:
            # Используем вашу функцию init_db из utils/db.py
            init_db() # Убедитесь, что init_db() вызывается без await, если она синхронная
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            # Если БД недоступна, возможно, стоит завершить работу
            sys.exit(1) # Выход при критической ошибке БД

        # --- Register middlewares ---
        # Используйте вашу существующую логику регистрации LanguageMiddleware
        try:
            # language_middleware = LanguageMiddleware() # Инициализируйте если требуется
            # dp.message.middleware(language_middleware)
            # dp.callback_query.middleware(language_middleware)
            # Или используйте outer_middleware для лучшей совместимости, как в инструкции:
            language_middleware = LanguageMiddleware() # Инициализируйте если требуется
            dp.update.outer_middleware.register(language_middleware)
            logger.info("LanguageMiddleware registered")
        except ImportError:
            logger.warning("LanguageMiddleware not found (ImportError). Skipping registration.")
        except Exception as e:
             logger.error(f"Error registering LanguageMiddleware: {e}")


        logger.info("Registering admin and other routers...")

        # --- Register admin panel routers ---

        # Создаем главный роутер для админки
        admin_router = Router(name="admin")

        # Создаем отдельные роутеры для каждого типа операций или сущности
        # Это помогает организовать хэндлеры и управлять порядком их регистрации
        category_add_router = Router(name="category_add_fsm")
        manufacturer_add_router = Router(name="manufacturer_add_fsm")
        location_add_router = Router(name="location_add_fsm")
        product_add_router = Router(name="product_add_fsm")
        stock_add_router = Router(name="stock_add_fsm")

        category_update_router = Router(name="category_update_fsm")
        manufacturer_update_router = Router(name="manufacturer_update_fsm")
        location_update_router = Router(name="location_update_fsm")
        product_update_router = Router(name="product_update_fsm")
        stock_update_router = Router(name="stock_update_fsm")

        list_detail_router = Router(name="list_detail_admin")
        delete_router = Router(name="delete_admin") # Роутер для FSM удаления


        # 1. Регистрация общего хэндлера отмены. Регистрируется на высшем уровне (admin_router),
        # чтобы перехватывать в любом состоянии FSM внутри админки.
        # Важно зарегистрировать его ДО любых других хэндлеров колбэков на этом роутере.
        admin_router.callback_query.register(cancel_fsm_handler, F.text(CANCEL_FSM_CALLBACK), State("*"))


        # 2. Регистрация стартовых хэндлеров FSM (по колбэку из меню сущностей)
        # Эти хэндлеры запускают соответствующий FSM. Регистрируем их на admin_router.
        # Важно, чтобы их фильтры (F.data == ...) были более специфичными, чем фильтр навигационного хэндлера.
        # Регистрируются перед навигационным хэндлером.
        admin_router.callback_query.register(handle_product_add, F.text(PRODUCT_ADD_CALLBACK))
        admin_router.callback_query.register(handle_stock_add, F.text(STOCK_ADD_CALLBACK))
        admin_router.callback_query.register(handle_category_add, F.text(CATEGORY_ADD_CALLBACK))
        admin_router.callback_query.register(handle_manufacturer_add, F.text(MANUFACTURER_ADD_CALLBACK))
        admin_router.callback_query.register(handle_location_add, F.text(LOCATION_ADD_CALLBACK))

        # 3. Регистрация ENTRY POINT хэндлеров для списков (по колбэку из меню сущностей)
        # Эти хэндлеры запускают отображение списка сущностей. Регистрируем их на admin_router.
        # Регистрируются перед навигационным хэндлером.
        admin_router.callback_query.register(handle_product_list, F.text(PRODUCT_LIST_CALLBACK))
        admin_router.callback_query.register(handle_stock_list, F.text(STOCK_LIST_CALLBACK))
        admin_router.callback_query.register(handle_category_list, F.text(CATEGORY_LIST_CALLBACK))
        admin_router.callback_query.register(handle_manufacturer_list, F.text(MANUFACTURER_LIST_CALLBACK))
        admin_router.callback_query.register(handle_location_list, F.text(LOCATION_LIST_CALLBACK))


        # 4. Регистрация навигационного хэндлера главного меню и кнопки "Назад". Регистрируется на admin_router.
        # У него менее специфичный фильтр (список колбэков), поэтому он должен быть зарегистрирован ПОСЛЕ
        # стартовых FSM хэндлеров и хэндлеров списков.
        admin_router.callback_query.register(admin_menu_navigation_handler,
            F.text(
                [
                    ADMIN_PRODUCTS_CALLBACK, ADMIN_STOCK_CALLBACK, ADMIN_CATEGORIES_CALLBACK,
                    ADMIN_MANUFACTURERS_CALLBACK, ADMIN_LOCATIONS_CALLBACK,
                    ADMIN_BACK_MAIN # Кнопка "Назад" в главное меню
                ]
            )
        )


        # 5. Регистрация хэндлера команды /admin
        admin_router.message.register(handle_admin_command, Command("admin"))

        # TODO: Добавьте проверку is_admin() к этим хэндлерам выше,
        # или используйте Middleware для проверки администратора на admin_router


        # 6. Регистрация всех хэндлеров шагов FSM в их отдельные роутеры
        register_category_add_handlers(category_add_router)
        register_manufacturer_add_handlers(manufacturer_add_router)
        register_location_add_handlers(location_add_router)
        register_product_add_handlers(product_add_router)
        register_stock_add_handlers(stock_add_router)

        register_category_update_handlers(category_update_router)
        register_manufacturer_update_handlers(manufacturer_update_router)
        register_location_update_handlers(location_update_router)
        register_product_update_handlers(product_update_router)
        register_stock_update_handlers(stock_update_router)

        # 6a. Регистрация хэндлеров списков/деталей/инициации CRUD в их роутере
        # Этот роутер содержит обработчики пагинации, деталей, "Назад к списку",
        # а также ENTRY POINT хэндлеры для запуска FSM обновления и удаления
        # (эти хэндлеры в list_detail_router вызывают соответствующие start_*_fsm функции).
        register_list_detail_handlers(list_detail_router)

        # 6b. Регистрация хэндлеров удаления в их роутере (FSM подтверждения и выполнения)
        register_delete_handlers(delete_router)


        # 7. Подключение FSM и других специализированных роутеров к главному админскому роутеру
        # Порядок включения роутеров в admin_router определяет порядок проверки хэндлеров внутри admin_router.
        # Роутеры с более специфичными фильтрами (например, FSM step handlers с State фильтрами,
        # или F.data.startswith фильтры для выборов/пагинации внутри FSM)
        # должны быть включены раньше, чем роутеры с менее специфичными фильтрами.
        # Роутеры добавления и обновления включают хэндлеры с State фильтрами,
        # а также F.data.startswith фильтрами для выборов/пагинации (с уникальными префиксами).
        # Роутер удаления включает хэндлеры с State фильтром DeleteFSM.confirm_delete
        # и F.data.startswith фильтрами для DELETE_EXECUTE_ACTION_PREFIX / DELETE_CANCEL_ACTION_PREFIX.
        # Роутер list_detail включает F.data.startswith фильтры для пагинации списков, деталей,
        # инициации обновления и удаления, а также Text фильтры для "Назад к списку".
        # Навигационный хэндлер (admin_menu_navigation_handler) на admin_router имеет самый общий
        # Text фильтр для колбэков меню.

        # Рекомендованный порядок включения в admin_router:
        # 1. FSM роутеры (Add, Update) - имеют State фильтры и специфичные F.data.startswith
        # 2. Роутер удаления (Delete FSM) - имеет State фильтр и специфичные F.data.startswith
        # 3. Роутер списков/деталей/инициации CRUD - имеет F.data.startswith (менее специфичные, чем FSM steps) и Text (более специфичные, чем навигация)
        # 4. (Уже зарегистрировано на admin_router) Навигационный хэндлер и хэндлер команды /admin

        # Порядок 1 и 2 между собой может быть не так критичен, т.к. State фильтры разделяют их.
        # Но порядок 1,2,3 ПЕРЕД 4 критичен.
        # Роутер list_detail должен быть после FSM Add/Update, т.к. его handle_update_init вызывает start_*_update_fsm.
        # Роутер delete должен быть после FSM Update, т.к. его start_delete_confirmation вызывается из list_detail.

        # Включаем FSM роутеры добавления
        admin_router.include_router(category_add_router)
        admin_router.include_router(manufacturer_add_router)
        admin_router.include_router(location_add_router)
        admin_router.include_router(product_add_router)
        admin_router.include_router(stock_add_router)

        # Включаем FSM роутеры обновления
        admin_router.include_router(category_update_router)
        admin_router.include_router(manufacturer_update_router)
        admin_router.include_router(location_update_router)
        admin_router.include_router(product_update_router)
        admin_router.include_router(stock_update_router)

        # Включаем роутер удаления (FSM подтверждения)
        admin_router.include_router(delete_router)

        # Включаем роутер списков/деталей/инициации CRUD
        admin_router.include_router(list_detail_router)


        # 8. Подключение главного админского роутера к основному диспатчеру
        # Регистрируем admin_router ПЕРЕД любыми другими роутерами (пользовательскими, общими),
        # если админские хэндлеры должны иметь приоритет.
        # Удалите старые регистрации админских хэндлеров, если они были (например, admin_handlers.router)
        # from app.handlers import admin_handlers # <-- Удалить этот импорт, если его роутер заменяется
        # dp.include_router(admin_handlers.router) # <-- Удалить эту строку


        dp.include_router(admin_router)
        logger.info("Admin panel router registered.")

        # Register common handlers (start, help, language selection, etc.)
        from handlers import common_handlers, user_handlers
        dp.include_router(common_handlers.router)
        logger.info("Common handlers router registered.")
        
        # Register user handlers (shopping flow, cart, orders)
        dp.include_router(user_handlers.router)
        logger.info("User handlers router registered.")
        
        # Register complete admin handlers (products, categories, manufacturers, locations, stock CRUD)
        from app.handlers import admin_handlers
        dp.include_router(admin_handlers.router)
        logger.info("Complete admin handlers router registered.")


        # Log bot information
        bot_info = await bot.get_me()
        logger.info(f"Bot @{bot_info.username} (ID: {bot_info.id}) started successfully")

        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected error during bot startup: {e}", exc_info=True)
        # Важно вызвать sys.exit(1) при критической ошибке для сигнализации системе управления (Docker, systemd и т.п.)
        # что приложение упало и, возможно, требует перезапуска.
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("Shutting down bot...")

        if dp and dp.storage:
            await dp.storage.close()
            logger.info("Dispatcher storage closed")

        if bot and bot.session:
            await bot.session.close()
            logger.info("Bot session closed")

        try:
            # Используем вашу функцию close_db из utils/db.py
            close_db() # Убедитесь, что close_db() синхронная
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}", exc_info=True)
            # Не вызываем sys.exit(1) здесь, т.к. это clean up при завершении работы, а не критическая ошибка старта.


if __name__ == "__main__":
    # Убедитесь, что код здесь просто запускает main() и обрабатываетKeyboardInterrupt
    # Критические ошибки внутри main() должны приводить к sys.exit(1)
    try:
        asyncio.run(main())
    except Exception as e:
        # Логируем любые исключения, которые могут просочиться сюда
        logger.critical(f"Application stopped due to unhandled exception: {e}", exc_info=True)
        # sys.exit(1) уже вызывается в main() при критической ошибке
