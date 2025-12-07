"""
Модуль для работы с базой данных.
Содержит модели данных, настройку подключения и утилиты для работы с БД.
Использует SQLAlchemy с асинхронным драйвером aiosqlite для SQLite.
"""

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import os

# Базовый класс для всех моделей SQLAlchemy
Base = declarative_base()


class FileAnalysis(Base):
    """
    Модель для хранения общей информации о анализе файла.
    """
    __tablename__ = "file_analyses"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="processing")
    overall_rating = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    total_sentences = Column(Integer, default=0)
    statistics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Связь один-ко-многим с таблицей предложений
    sentences = relationship("SentenceAnalysis", back_populates="file_analysis", cascade="all, delete-orphan")


class SentenceAnalysis(Base):
    """
    Модель для хранения анализа каждого отдельного предложения.
    """
    __tablename__ = "sentence_analyses"

    id = Column(Integer, primary_key=True, index=True)
    file_analysis_id = Column(Integer, ForeignKey("file_analyses.id"), nullable=False)
    sentence_id = Column(Integer, nullable=False)
    sentence_text = Column(Text, nullable=False)

    # Флаги наличия нарушений
    has_violence = Column(Boolean, default=False)
    has_profanity = Column(Boolean, default=False)
    has_sexual_content = Column(Boolean, default=False)
    has_drugs_alcohol = Column(Boolean, default=False)
    has_fear_elements = Column(Boolean, default=False)

    # Уровни нарушений (0.0 - 1.0)
    violence_level = Column(Float, default=0.0)
    profanity_level = Column(Float, default=0.0)
    sexual_content_level = Column(Float, default=0.0)
    drugs_alcohol_level = Column(Float, default=0.0)
    fear_level = Column(Float, default=0.0)

    # Уровни серьезности нарушений
    violence_severity = Column(String, default="None")
    profanity_severity = Column(String, default="None")
    sexual_severity = Column(String, default="None")
    drugs_severity = Column(String, default="None")
    fear_severity = Column(String, default="None")

    # Результаты анализа
    assigned_rating = Column(String, nullable=False, default="0+")
    explanation = Column(Text, nullable=True)
    correction_recommendations = Column(JSON, nullable=True)
    is_problematic = Column(Boolean, default=False)

    # Новые поля для ручной корректировки
    is_false_positive = Column(Boolean, default=False)  # Ложноположительное срабатывание
    is_false_negative = Column(Boolean, default=False)  # Ложноотрицательное срабатывание
    user_correction_rating = Column(String, nullable=True)  # Ручная корректировка рейтинга
    user_notes = Column(Text, nullable=True)  # Пользовательские заметки

    created_at = Column(DateTime, default=func.now())

    # Связь многие-к-одному с родительским файлом
    file_analysis = relationship("FileAnalysis", back_populates="sentences")


# URL подключения к базе данных
DATABASE_URL = "sqlite+aiosqlite:///./script_analyzer.db"

# Создание асинхронного движка базы данных
engine = create_async_engine(DATABASE_URL, echo=False)

# Фабрика сессий для работы с базой данных
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """
    Инициализация базы данных.
    Создает все таблицы, если они не существуют.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных инициализирована")


async def get_db():
    """
    Dependency для FastAPI, предоставляющая сессию базы данных.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()