# your_bot/utils/db.py
# Модуль для взаимодействия с базой данных PostgreSQL с использованием SQLAlchemy

import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Text, DECIMAL as Decimal, ForeignKey, UniqueConstraint, func, BigInteger, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError, NoResultFound, OperationalError
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Конфигурация базы данных ---
# Чтение строки подключения из переменной окружения DATABASE_URL
# Пример: postgresql+psycopg2://user:password@host:port/database
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/telegram_bot")
if DATABASE_URL == "postgresql+psycopg2://user:password@host:port/database":
    logger.warning("Используется URL базы данных по умолчанию. Пожалуйста, установите переменную окружения DATABASE_URL.")


# Создание движка SQLAlchemy
try:
    # Добавляем пул соединений для лучшей производительности в веб-приложениях/ботах
    engine = create_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    logger.info("Движок SQLAlchemy создан.")
except Exception as e:
    logger.error(f"Ошибка при создании движка SQLAlchemy: {e}")
    # В реальном приложении здесь, возможно, нужно завершить работу или предпринять другие действия

# Создание базового класса для декларативного подхода
Base = declarative_base()

# Настройка фабрики сессий и управление сессиями
# scoped_session предоставляет потокобезопасный доступ к одной сессии для каждого потока/контекста
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
logger.info("Фабрика сессий SQLAlchemy настроена.")

# Контекстный менеджер для удобной работы с сессиями
@contextmanager
def session_scope():
    """Предоставляет потокобезопасную сессию с автоматическим коммитом/откатом."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# --- Определение моделей SQLAlchemy ---

class User(Base):
    """Модель для таблицы 'users' (пользователи Telegram)."""
    __tablename__ = 'users'

    telegram_id = Column(BigInteger, primary_key=True, nullable=False)
    language_code = Column(String(5), nullable=False, default="en")
    is_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, language_code='{self.language_code}', is_blocked={self.is_blocked})>"

class Category(Base):
    """Модель для таблицы 'categories'."""
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)

    # Связи
    parent = relationship("Category", remote_side=[id])
    # Использование cascade="all, delete-orphan" при удалении родителя удалит дочерние категории.
    # Если нужна другая логика (например, обнуление parent_id дочерних), нужно изменить cascade или добавить обработку перед удалением.
    # Для простоты текущая схема удаляет детей.
    children = relationship("Category", backref="parent", cascade="all, delete-orphan")
    # ForeignKey в products не имеет cascade по умолчанию, что приведет к IntegrityError при удалении категории, связанной с товарами.
    products = relationship("Product", backref="category")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"

class Manufacturer(Base):
    """Модель для таблицы 'manufacturers'."""
    __tablename__ = 'manufacturers'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)

    # Связи (IntegrityError при удалении производителя, связанного с товарами)
    products = relationship("Product", backref="manufacturer")

    def __repr__(self):
        return f"<Manufacturer(id={self.id}, name='{self.name}')>"

class Product(Base):
    """Модель для таблицы 'products'."""
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False) # name не unique, т.к. товары могут иметь одинаковые названия, но разные характеристики/ID
    description = Column(Text, nullable=True)
    price = Column(Decimal(10, 2), nullable=False) # DECIMAL для точных денежных значений

    # Внешние ключи (по умолчанию ON DELETE NO ACTION, что вызовет IntegrityError)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    manufacturer_id = Column(Integer, ForeignKey('manufacturers.id'), nullable=False)

    # Связи (backref определены в Category и Manufacturer)
    # Использование cascade="all, delete-orphan" при удалении товара удалит связанные записи остатков.
    stock_items = relationship("Stock", backref="product", cascade="all, delete-orphan") # Связь один-ко-многим с Stock

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"

class Location(Base):
    """Модель для таблицы 'locations'."""
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)

    # Связи (IntegrityError при удалении локации, связанной с остатками)
    stock_items = relationship("Stock", backref="location") # Связь один-ко-многим с Stock

    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}')>"

class Stock(Base):
    """Модель для таблицы 'stock'."""
    __tablename__ = 'stock'

    product_id = Column(Integer, ForeignKey('products.id'), primary_key=True)
    location_id = Column(Integer, ForeignKey('locations.id'), primary_key=True)
    quantity = Column(Integer, nullable=False) # Количество должно быть неотрицательным, проверка в логике приложения

    # Связи (backref определены в Product и Location)

    def __repr__(self):
        return f"<Stock(product_id={self.product_id}, location_id={self.location_id}, quantity={self.quantity})>"

    # Ограничение уникальности гарантируется составным первичным ключом


# --- Функции инициализации и закрытия БД ---

def init_db():
    """Создает все таблицы в базе данных."""
    logger.info("Попытка создания таблиц в базе данных...")
    logger.info(f"ДИАГНОСТИКА: Модели в Base.metadata: {list(Base.metadata.tables.keys())}")
    logger.info(f"ДИАГНОСТИКА: DATABASE_URL: {DATABASE_URL}")
    try:
        # Base.metadata.create_all создает таблицы, если они еще не существуют
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы успешно созданы или уже существуют.")
        logger.info(f"ДИАГНОСТИКА: Созданные таблицы: {list(Base.metadata.tables.keys())}")
    except OperationalError as e:
        logger.error(f"Ошибка подключения к базе данных или создания таблиц: {e}")
        # В реальном приложении здесь, возможно, нужно завершить работу или предпринять другие действия
    except Exception as e:
        logger.error(f"Неизвестная ошибка при создании таблиц: {e}")

def close_db():
    """Закрывает сессию SQLAlchemy."""
    # При использовании scoped_session, dispose() может быть вызвана для очистки ресурсов в конце работы приложения
    SessionLocal.remove()
    engine.dispose()
    logger.info("Соединение с базой данных закрыто.")


# --- Вспомогательные функции для пагинации ---

def get_entity_model(entity_name: str):
    """Возвращает класс модели SQLAlchemy по имени сущности."""
    models = {
        'products': Product,
        'categories': Category,
        'manufacturers': Manufacturer,
        'locations': Location,
        'stock': Stock,
    }
    return models.get(entity_name)

def get_entity_count(entity_name: str) -> int:
    """Получает общее количество записей для сущности."""
    model = get_entity_model(entity_name)
    if not model:
        logger.warning(f"Модель для сущности '{entity_name}' не найдена.")
        return 0

    with session_scope() as session:
        try:
            # Для Stock считаем rows, для остальных - ID
            if entity_name == 'stock':
                count = session.query(func.count()).select_from(model).scalar() or 0
            else:
                count = session.query(func.count(model.id)).scalar() or 0
            logger.debug(f"Получено количество записей для {entity_name}: {count}")
            return count
        except Exception as e:
            logger.error(f"Ошибка при получении количества записей для {entity_name}: {e}")
            return 0

def get_all_paginated(entity_name: str, offset: int, limit: int) -> list:
    """Получает список записей для сущности с пагинацией."""
    model = get_entity_model(entity_name)
    if not model:
        logger.warning(f"Модель для сущности '{entity_name}' не найдена.")
        return []

    with session_scope() as session:
        try:
            query = session.query(model)

            # Определяем порядок сортировки
            if entity_name == 'stock':
                 query = query.order_by(model.product_id, model.location_id)
            elif hasattr(model, 'name'):
                 query = query.order_by(model.name)
            elif hasattr(model, 'id'):
                 query = query.order_by(model.id) # Fallback сортировка по ID

            items = query.offset(offset).limit(limit).all()
            logger.debug(f"Получены записи для {entity_name} (offset={offset}, limit={limit}): {len(items)} шт.")
            return items
        except Exception as e:
            logger.error(f"Ошибка при получении постраничного списка для {entity_name}: {e}")
            return []

# --- CRUD Операции: Categories ---

def add_category(name: str, parent_id: int | None = None) -> Category | None:
    """Добавляет новую категорию."""
    with session_scope() as session:
        try:
            new_category = Category(name=name, parent_id=parent_id)
            session.add(new_category)
            session.flush()
            session.refresh(new_category) # Получаем актуальный объект после flush
            logger.info(f"Добавлена новая категория: {new_category.name} (ID: {new_category.id})")
            return new_category
        except IntegrityError as e:
            logger.error(f"Ошибка добавления категории '{name}': категория с таким именем уже существует или parent_id некорректен. Детали: {e}")
            session.rollback() # Откатываем изменения при IntegrityError
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при добавлении категории '{name}': {e}")
            session.rollback()
            return None

def get_category_by_id(category_id: int) -> Category | None:
    """Получает категорию по ID."""
    with session_scope() as session:
        try:
            category = session.query(Category).get(category_id)
            if category:
                logger.debug(f"Найдена категория по ID {category_id}: {category.name}")
            else:
                logger.debug(f"Категория с ID {category_id} не найдена.")
            return category
        except Exception as e:
            logger.error(f"Ошибка при получении категории по ID {category_id}: {e}")
            return None

def get_all_categories() -> list[Category]:
     """Получает список всех категорий без пагинации (для использования в handler)."""
     return get_all_paginated('categories', 0, get_entity_count('categories'))

def find_categories_by_name(query: str) -> list[Category]:
    """Ищет категории по названию (частичное совпадение, без учета регистра)."""
    with session_scope() as session:
        try:
            # Используем ilike для поиска без учета регистра в PostgreSQL
            categories = session.query(Category).filter(Category.name.ilike(f'%{query}%')).order_by(Category.name).all()
            logger.debug(f"Найдены категории по запросу '{query}': {len(categories)} шт.")
            return categories
        except Exception as e:
            logger.error(f"Ошибка при поиске категорий по запросу '{query}': {e}")
            return []

def update_category(category_id: int, data: dict) -> Category | None:
    """Обновляет данные категории по ID."""
    with session_scope() as session:
        try:
            category = session.query(Category).filter(Category.id == category_id).one()
            for key, value in data.items():
                if hasattr(category, key):
                    setattr(category, key, value)
                else:
                    logger.warning(f"Попытка обновить несуществующее поле в Category: {key}")
            session.flush()
            session.refresh(category) # Получаем актуальный объект после flush
            logger.info(f"Обновлена категория ID {category_id}. Данные: {data}")
            return category
        except NoResultFound:
            logger.warning(f"Попытка обновить несуществующую категорию ID {category_id}.")
            return None
        except IntegrityError as e:
             logger.error(f"Ошибка целостности при обновлении категории ID {category_id} с данными {data}: {e}")
             session.rollback()
             return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении категории ID {category_id}: {e}")
            session.rollback()
            return None

def delete_category(category_id: int) -> bool:
    """Удаляет категорию по ID."""
    with session_scope() as session:
        try:
            category = session.query(Category).filter(Category.id == category_id).one()
            session.delete(category)
            session.flush()
            logger.info(f"Удалена категория ID {category_id}.")
            return True
        except NoResultFound:
            logger.warning(f"Попытка удалить несуществующую категорию ID {category_id}.")
            return False
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при удалении категории ID {category_id} (связанные записи существуют): {e}")
            session.rollback() # Откатываем изменения
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении категории ID {category_id}: {e}")
            session.rollback()
            return False


# --- CRUD Операции: Manufacturers ---

def add_manufacturer(name: str) -> Manufacturer | None:
    """Добавляет нового производителя."""
    with session_scope() as session:
        try:
            new_manufacturer = Manufacturer(name=name)
            session.add(new_manufacturer)
            session.flush()
            session.refresh(new_manufacturer)
            logger.info(f"Добавлен новый производитель: {new_manufacturer.name} (ID: {new_manufacturer.id})")
            return new_manufacturer
        except IntegrityError as e:
            logger.error(f"Ошибка добавления производителя '{name}': производитель с таким именем уже существует. Детали: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при добавлении производителя '{name}': {e}")
            session.rollback()
            return None

def get_manufacturer_by_id(manufacturer_id: int) -> Manufacturer | None:
    """Получает производителя по ID."""
    with session_scope() as session:
        try:
            manufacturer = session.query(Manufacturer).get(manufacturer_id)
            if manufacturer:
                logger.debug(f"Найден производитель по ID {manufacturer_id}: {manufacturer.name}")
            else:
                 logger.debug(f"Производитель с ID {manufacturer_id} не найден.")
            return manufacturer
        except Exception as e:
            logger.error(f"Ошибка при получении производителя по ID {manufacturer_id}: {e}")
            return None

def get_all_manufacturers() -> list[Manufacturer]:
     """Получает список всех производителей без пагинации."""
     return get_all_paginated('manufacturers', 0, get_entity_count('manufacturers'))

def find_manufacturers_by_name(query: str) -> list[Manufacturer]:
    """Ищет производителей по названию (частичное совпадение, без учета регистра)."""
    with session_scope() as session:
        try:
            manufacturers = session.query(Manufacturer).filter(Manufacturer.name.ilike(f'%{query}%')).order_by(Manufacturer.name).all()
            logger.debug(f"Найдены производители по запросу '{query}': {len(manufacturers)} шт.")
            return manufacturers
        except Exception as e:
            logger.error(f"Ошибка при поиске производителей по запросу '{query}': {e}")
            return []

def update_manufacturer(manufacturer_id: int, data: dict) -> Manufacturer | None:
    """Обновляет данные производителя по ID."""
    with session_scope() as session:
        try:
            manufacturer = session.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).one()
            for key, value in data.items():
                if hasattr(manufacturer, key):
                    setattr(manufacturer, key, value)
                else:
                     logger.warning(f"Попытка обновить несуществующее поле в Manufacturer: {key}")
            session.flush()
            session.refresh(manufacturer)
            logger.info(f"Обновлен производитель ID {manufacturer_id}. Данные: {data}")
            return manufacturer
        except NoResultFound:
            logger.warning(f"Попытка обновить несуществующего производителя ID {manufacturer_id}.")
            return None
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при обновлении производителя ID {manufacturer_id} с данными {data}: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении производителя ID {manufacturer_id}: {e}")
            session.rollback()
            return None

def delete_manufacturer(manufacturer_id: int) -> bool:
    """Удаляет производителя по ID."""
    with session_scope() as session:
        try:
            manufacturer = session.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).one()
            session.delete(manufacturer)
            session.flush()
            logger.info(f"Удален производитель ID {manufacturer_id}.")
            return True
        except NoResultFound:
            logger.warning(f"Попытка удалить несуществующего производителя ID {manufacturer_id}.")
            return False
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при удалении производителя ID {manufacturer_id} (связанные записи существуют): {e}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении производителя ID {manufacturer_id}: {e}")
            session.rollback()
            return False

# --- CRUD Операции: Products ---

def add_product(name: str, description: str | None, price: float | Decimal, category_id: int, manufacturer_id: int) -> Product | None:
    """Добавляет новый товар."""
    with session_scope() as session:
        try:
            # Проверка существования category_id и manufacturer_id
            category = session.query(Category).get(category_id)
            manufacturer = session.query(Manufacturer).get(manufacturer_id)
            if not category:
                logger.warning(f"Не найдена категория с ID {category_id} для добавления товара '{name}'.")
                return None
            if not manufacturer:
                logger.warning(f"Не найден производитель с ID {manufacturer_id} для добавления товара '{name}'.")
                return None

            new_product = Product(
                name=name,
                description=description,
                price=price, # SQLAlchemy преобразует float или Decimal в DECIMAL
                category_id=category_id,
                manufacturer_id=manufacturer_id
            )
            session.add(new_product)
            session.flush()
            session.refresh(new_product)
            logger.info(f"Добавлен новый товар: '{new_product.name}' (ID: {new_product.id})")
            return new_product
        except IntegrityError as e:
             logger.error(f"Ошибка целостности при добавлении товара '{name}'. Детали: {e}")
             session.rollback()
             return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при добавлении товара '{name}': {e}")
            session.rollback()
            return None

def get_product_by_id(product_id: int) -> Product | None:
    """Получает товар по ID."""
    with session_scope() as session:
        try:
            product = session.query(Product).get(product_id)
            if product:
                 logger.debug(f"Найден товар по ID {product_id}: {product.name}")
            else:
                 logger.debug(f"Товар с ID {product_id} не найден.")
            return product
        except Exception as e:
            logger.error(f"Ошибка при получении товара по ID {product_id}: {e}")
            return None

def get_all_products() -> list[Product]:
     """Получает список всех товаров без пагинации."""
     return get_all_paginated('products', 0, get_entity_count('products'))

def find_products_by_name(query: str) -> list[Product]:
    """Ищет товары по названию (частичное совпадение, без учета регистра)."""
    with session_scope() as session:
        try:
            products = session.query(Product).filter(Product.name.ilike(f'%{query}%')).order_by(Product.name).all()
            logger.debug(f"Найдены товары по запросу '{query}': {len(products)} шт.")
            return products
        except Exception as e:
            logger.error(f"Ошибка при поиске товаров по запросу '{query}': {e}")
            return []

def update_product(product_id: int, data: dict) -> Product | None:
    """Обновляет данные товара по ID."""
    with session_scope() as session:
        try:
            product = session.query(Product).filter(Product.id == product_id).one()
            for key, value in data.items():
                if hasattr(product, key):
                    setattr(product, key, value)
                else:
                    logger.warning(f"Попытка обновить несуществующее поле в Product: {key}")
            session.flush()
            session.refresh(product)
            logger.info(f"Обновлен товар ID {product_id}. Данные: {data}")
            return product
        except NoResultFound:
            logger.warning(f"Попытка обновить несуществующий товар ID {product_id}.")
            return None
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при обновлении товара ID {product_id} с данными {data}: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении товара ID {product_id}: {e}")
            session.rollback()
            return None


def delete_product(product_id: int) -> bool:
    """Удаляет товар по ID."""
    with session_scope() as session:
        try:
            product = session.query(Product).filter(Product.id == product_id).one()
            session.delete(product)
            session.flush()
            logger.info(f"Удален товар ID {product_id}.")
            return True
        except NoResultFound:
            logger.warning(f"Попытка удалить несуществующий товар ID {product_id}.")
            return False
        except IntegrityError as e:
            # Это произойдет, если есть связанные остатки и нет ON DELETE CASCADE для product_id в таблице stock
            logger.error(f"Ошибка целостности при удалении товара ID {product_id} (связанные записи в stock существуют): {e}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении товара ID {product_id}: {e}")
            session.rollback()
            return False

# --- CRUD Операции: Locations ---

def add_location(name: str) -> Location | None:
    """Добавляет новое местоположение."""
    with session_scope() as session:
        try:
            new_location = Location(name=name)
            session.add(new_location)
            session.flush()
            session.refresh(new_location)
            logger.info(f"Добавлено новое местоположение: {new_location.name} (ID: {new_location.id})")
            return new_location
        except IntegrityError as e:
            logger.error(f"Ошибка добавления местоположения '{name}': местоположение с таким именем уже существует. Детали: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при добавлении местоположения '{name}': {e}")
            session.rollback()
            return None

def get_location_by_id(location_id: int) -> Location | None:
    """Получает местоположение по ID."""
    with session_scope() as session:
        try:
            location = session.query(Location).get(location_id)
            if location:
                 logger.debug(f"Найдено местоположение по ID {location_id}: {location.name}")
            else:
                 logger.debug(f"Местоположение с ID {location_id} не найдено.")
            return location
        except Exception as e:
            logger.error(f"Ошибка при получении местоположения по ID {location_id}: {e}")
            return None

def get_all_locations() -> list[Location]:
     """Получает список всех местоположений без пагинации."""
     return get_all_paginated('locations', 0, get_entity_count('locations'))

def find_locations_by_name(query: str) -> list[Location]:
    """Ищет местоположения по названию (частичное совпадение, без учета регистра)."""
    with session_scope() as session:
        try:
            locations = session.query(Location).filter(Location.name.ilike(f'%{query}%')).order_by(Location.name).all()
            logger.debug(f"Найдены местоположения по запросу '{query}': {len(locations)} шт.")
            return locations
        except Exception as e:
            logger.error(f"Ошибка при поиске местоположений по запросу '{query}': {e}")
            return []

def update_location(location_id: int, data: dict) -> Location | None:
    """Обновляет данные местоположения по ID."""
    with session_scope() as session:
        try:
            location = session.query(Location).filter(Location.id == location_id).one()
            for key, value in data.items():
                if hasattr(location, key):
                    setattr(location, key, value)
                else:
                     logger.warning(f"Попытка обновить несуществующее поле в Location: {key}")
            session.flush()
            session.refresh(location)
            logger.info(f"Обновлено местоположение ID {location_id}. Данные: {data}")
            return location
        except NoResultFound:
            logger.warning(f"Попытка обновить несуществующее местоположение ID {location_id}.")
            return None
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при обновлении местоположения ID {location_id} с данными {data}: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении местоположения ID {location_id}: {e}")
            session.rollback()
            return None

def delete_location(location_id: int) -> bool:
    """Удаляет местоположение по ID."""
    with session_scope() as session:
        try:
            location = session.query(Location).filter(Location.id == location_id).one()
            session.delete(location)
            session.flush()
            logger.info(f"Удалено местоположение ID {location_id}.")
            return True
        except NoResultFound:
            logger.warning(f"Попытка удалить несуществующее местоположение ID {location_id}.")
            return False
        except IntegrityError as e:
             # Это произойдет, если есть связанные остатки и нет ON DELETE CASCADE для location_id в таблице stock
             logger.error(f"Ошибка целостности при удалении местоположения ID {location_id} (связанные записи в stock существуют): {e}")
             session.rollback()
             return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении местоположения ID {location_id}: {e}")
            session.rollback()
            return False

# --- CRUD Операции: Stock ---

def add_stock(product_id: int, location_id: int, quantity: int) -> Stock | None:
    """Добавляет новую запись об остатке."""
    if quantity < 0:
        logger.warning(f"Попытка добавить остаток с отрицательным количеством ({quantity}) для product_id={product_id}, location_id={location_id}")
        return None

    with session_scope() as session:
        try:
             # Проверка существования product_id и location_id
            product = session.query(Product).get(product_id)
            location = session.query(Location).get(location_id)
            if not product:
                logger.warning(f"Не найдена категория с ID {product_id} для добавления остатка.")
                return None
            if not location:
                logger.warning(f"Не найдено местоположение с ID {location_id} для добавления остатка.")
                return None

            new_stock = Stock(product_id=product_id, location_id=location_id, quantity=quantity)
            session.add(new_stock)
            session.flush()
            session.refresh(new_stock)
            logger.info(f"Добавлена запись остатка: product_id={product_id}, location_id={location_id}, quantity={quantity}")
            return new_stock
        except IntegrityError as e:
            logger.error(f"Ошибка добавления остатка для product_id={product_id}, location_id={location_id}: запись уже существует. Используйте update_stock_quantity. Детали: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при добавлении остатка: {e}")
            session.rollback()
            return None

def get_stock_by_ids(product_id: int, location_id: int) -> Stock | None:
    """Получает запись об остатке по ID товара и ID местоположения."""
    with session_scope() as session:
        try:
            stock_item = session.query(Stock).filter(
                Stock.product_id == product_id,
                Stock.location_id == location_id
            ).one_or_none()
            if stock_item:
                logger.debug(f"Найдена запись остатка для product_id={product_id}, location_id={location_id}")
            else:
                logger.debug(f"Запись остатка для product_id={product_id}, location_id={location_id} не найдена.")
            return stock_item
        except Exception as e:
            logger.error(f"Ошибка при получении остатка по product_id={product_id}, location_id={location_id}: {e}")
            return None

def get_all_stock() -> list[Stock]:
     """Получает список всех записей об остатках без пагинации."""
     return get_all_paginated('stock', 0, get_entity_count('stock'))


def find_stock(product_name_query: str | None = None, location_name_query: str | None = None) -> list[Stock]:
    """
    Ищет записи об остатках по названию товара и/или местоположения
    (частичное совпадение, без учета регистра).
    """
    with session_scope() as session:
        try:
            # Используем join_all для соединения через уже определенные relationship
            query = session.query(Stock).join(Stock.product).join(Stock.location)

            if product_name_query:
                query = query.filter(Product.name.ilike(f'%{product_name_query}%'))
            if location_name_query:
                query = query.filter(Location.name.ilike(f'%{location_name_query}%'))

            query = query.order_by(Stock.product_id, Stock.location_id)

            stock_items = query.all()
            logger.debug(f"Найдены остатки по запросу (товар: '{product_name_query}', локация: '{location_name_query}'): {len(stock_items)} шт.")
            return stock_items
        except Exception as e:
            logger.error(f"Ошибка при поиске остатков (товар: '{product_name_query}', локация: '{location_name_query}'): {e}")
            return []


def update_stock_quantity(product_id: int, location_id: int, quantity: int) -> Stock | None:
    """Обновляет количество остатка для заданной пары product_id/location_id."""
    if quantity < 0:
        logger.warning(f"Попытка установить отрицательное количество ({quantity}) для product_id={product_id}, location_id={location_id}")
        return None

    with session_scope() as session:
        try:
            stock_item = session.query(Stock).filter(
                Stock.product_id == product_id,
                Stock.location_id == location_id
            ).one()
            stock_item.quantity = quantity
            session.flush()
            session.refresh(stock_item)
            logger.info(f"Обновлен остаток для product_id={product_id}, location_id={location_id}. Новое количество: {quantity}")
            return stock_item
        except NoResultFound:
            logger.warning(f"Попытка обновить несуществующую запись остатка для product_id={product_id}, location_id={location_id}.")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении остатка для product_id={product_id}, location_id={location_id}: {e}")
            session.rollback()
            return None

def delete_stock(product_id: int, location_id: int) -> bool:
    """Удаляет запись об остатке по ID товара и ID местоположения."""
    with session_scope() as session:
        try:
            stock_item = session.query(Stock).filter(
                Stock.product_id == product_id,
                Stock.location_id == location_id
            ).one()
            session.delete(stock_item)
            session.flush()
            logger.info(f"Удалена запись остатка для product_id={product_id}, location_id={location_id}.")
            return True
        except NoResultFound:
            logger.warning(f"Попытка удалить несуществующую запись остатка для product_id={product_id}, location_id={location_id}.")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении остатка для product_id={product_id}, location_id={location_id}: {e}")
            session.rollback()
            return False
