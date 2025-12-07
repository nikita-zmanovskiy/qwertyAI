"""
Главный модуль FastAPI приложения для анализа сценариев.
Версия для развертывания на VM.
"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import os
import asyncio
import uvicorn
from typing import Optional
import traceback
from pydantic import BaseModel
import torch
import logging
from contextlib import asynccontextmanager

# Импорт модулей проекта
from text_proposal import process_script_file, split_script_into_sentences
from database import get_db, init_db, FileAnalysis, SentenceAnalysis
from phi3_integration import (
    analyze_all_sentences,
    calculate_overall_rating,
    generate_overall_summary,
    calculate_statistics
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Директория для загрузки файлов
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan событий приложения.
    Инициализирует базу данных при старте.
    """
    # Startup
    await init_db()

    # Загружаем модель в фоновом режиме
    try:
        from phi3_integration import phi3_analyzer
        logger.info("🔄 Загрузка модели Phi-3 в фоновом режиме...")
        asyncio.create_task(phi3_analyzer.load_model())
    except Exception as e:
        logger.warning(f"⚠️ Не удалось инициализировать модель: {e}")
        logger.info("💡 Модель загрузится при первом использовании")

    logger.info("✅ Приложение запущено успешно")

    yield

    # Shutdown
    logger.info("🔄 Завершение работы приложения...")


# Инициализация FastAPI приложения
app = FastAPI(
    title="Script Analysis API",
    description="API для автоматического анализа сценариев и определения возрастных рейтингов",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount uploads directory for file access
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Модели для ручек
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    overall_rating: str
    summary: str
    statistics: dict
    status: str = "success"

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    overall_rating: str
    summary: str
    statistics: dict
    status: str = "done"


@app.get("/")
async def root():
    """Корневой endpoint для проверки работы API."""
    return {
        "message": "Script Analysis API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "documentation": "/docs",
            "chat": "/chat",
            "upload": "/upload",
            "files": "/files",
            "analysis": "/extracted-sentences/{file_id}, /full-analysis/{file_id}, /summary-analysis/{file_id}",
            "manual_correction": "/mark-false-positive, /mark-false-negative, /correct-rating, /manual-corrections/{file_id}"
        }
    }


@app.post("/chat", response_model=ChatResponse, tags=["Анализ"])
async def chat_analysis(request: ChatRequest):
    """
    Основная ручка для быстрого анализа текста.
    Принимает текст сценария и возвращает краткий анализ.
    """
    from database import AsyncSessionLocal
    db = AsyncSessionLocal()

    try:
        logger.info(f"🔍 Начинаем анализ текста через /chat")

        # Генерация ID анализа для сохранения в БД
        analysis_id = str(uuid.uuid4())

        # Создаем запись в базе данных
        db_analysis = FileAnalysis(
            file_id=analysis_id,
            filename="chat_input.txt",
            status="processing"
        )
        db.add(db_analysis)
        await db.commit()
        await db.refresh(db_analysis)

        # Этап 1: Разбиваем текст на предложения
        sentences_list = split_script_into_sentences(request.message)
        logger.info(f"📝 Извлечено {len(sentences_list)} предложений")

        if not sentences_list:
            # Если не удалось разбить на предложения, анализируем весь текст как одно предложение
            sentences_list = [request.message]
            logger.info("🔄 Анализируем весь текст как одно предложение")

        # Этап 2: Анализ предложений с помощью нейросети
        sentence_analyses = await analyze_all_sentences(sentences_list)
        logger.info(f"🤖 Проанализировано {len(sentence_analyses)} предложений")

        # Этап 3: Расчет общей статистики и рейтинга
        overall_rating = calculate_overall_rating(sentence_analyses)
        overall_summary = generate_overall_summary(sentence_analyses)
        statistics = calculate_statistics(sentence_analyses)

        logger.info(f"📊 Статистика рассчитана, общий рейтинг: {overall_rating}")

        # Обновляем основную запись анализа
        db_analysis.status = "done"
        db_analysis.overall_rating = overall_rating
        db_analysis.summary = overall_summary
        db_analysis.total_sentences = len(sentences_list)
        db_analysis.statistics = statistics

        # Сохраняем анализ каждого предложения в БД
        for i, (sentence, analysis) in enumerate(zip(sentences_list, sentence_analyses)):
            sentence_db = SentenceAnalysis(
                file_analysis_id=db_analysis.id,
                sentence_id=i + 1,
                sentence_text=sentence,
                has_violence=analysis["has_violence"],
                has_profanity=analysis["has_profanity"],
                has_sexual_content=analysis["has_sexual_content"],
                has_drugs_alcohol=analysis["has_drugs_alcohol"],
                has_fear_elements=analysis["has_fear_elements"],
                violence_level=analysis["violence_level"],
                profanity_level=analysis["profanity_level"],
                sexual_content_level=analysis["sexual_content_level"],
                drugs_alcohol_level=analysis["drugs_alcohol_level"],
                fear_level=analysis["fear_level"],
                violence_severity=analysis["violence_severity"],
                profanity_severity=analysis["profanity_severity"],
                sexual_severity=analysis["sexual_severity"],
                drugs_severity=analysis["drugs_severity"],
                fear_severity=analysis["fear_severity"],
                assigned_rating=analysis["assigned_rating"],
                explanation=analysis["explanation"],
                correction_recommendations=analysis["correction_recommendations"],
                is_problematic=analysis["is_problematic"]
            )
            db.add(sentence_db)

        await db.commit()
        logger.info(f"💾 Анализ сохранен в БД с ID: {analysis_id}")

        return ChatResponse(
            overall_rating=overall_rating,
            summary=overall_summary,
            statistics=statistics,
            status="success"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при анализе текста: {e}")
        # Обновляем статус на ошибку в БД
        try:
            db_analysis.status = "error"
            db_analysis.summary = f"Ошибка обработки: {str(e)}"
            await db.commit()
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )
    finally:
        await db.close()


@app.post("/upload", response_model=UploadResponse, tags=["управление данными"])
async def upload_and_analyze_file(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db)
):
    """
    Загрузка файла для анализа с immediate возвратом краткого анализа.
    Сохраняет все данные в базу данных.
    """
    try:
        # Валидация формата файла
        if not file.filename:
            return JSONResponse({"error": "No filename provided"}, status_code=400)

        if not file.filename.lower().endswith(('.pdf', '.docx', '.txt')):
            return JSONResponse({"error": "Only PDF, DOCX, and TXT allowed"}, status_code=400)

        # Генерация уникального ID для файла
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

        # Сохранение файла на диск
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Создание записи в базе данных
        db_analysis = FileAnalysis(
            file_id=file_id,
            filename=file.filename,
            status="processing"
        )
        db.add(db_analysis)
        await db.commit()
        await db.refresh(db_analysis)

        # Немедленная обработка файла и получение результатов
        logger.info(f"🔍 Начинаем немедленную обработку файла {file_id}")

        # Этап 1: Извлечение текста из файла
        sentences_list = process_script_file(file_path, file.filename)
        logger.info(f"📝 Извлечено {len(sentences_list)} предложений")

        if not sentences_list:
            raise HTTPException(status_code=400, detail="Не удалось извлечь предложения из файла")

        # Этап 2: Анализ предложений с помощью нейросети
        sentence_analyses = await analyze_all_sentences(sentences_list)
        logger.info(f"🤖 Проанализировано {len(sentence_analyses)} предложений")

        # Этап 3: Расчет общей статистики и рейтинга
        overall_rating = calculate_overall_rating(sentence_analyses)
        overall_summary = generate_overall_summary(sentence_analyses)
        statistics = calculate_statistics(sentence_analyses)

        logger.info(f"📊 Статистика рассчитана, общий рейтинг: {overall_rating}")

        # Обновление основной записи файла
        db_analysis.status = "done"
        db_analysis.overall_rating = overall_rating
        db_analysis.summary = overall_summary
        db_analysis.total_sentences = len(sentences_list)
        db_analysis.statistics = statistics

        # Сохранение анализа каждого предложения
        for i, (sentence, analysis) in enumerate(zip(sentences_list, sentence_analyses)):
            sentence_db = SentenceAnalysis(
                file_analysis_id=db_analysis.id,
                sentence_id=i + 1,
                sentence_text=sentence,
                has_violence=analysis["has_violence"],
                has_profanity=analysis["has_profanity"],
                has_sexual_content=analysis["has_sexual_content"],
                has_drugs_alcohol=analysis["has_drugs_alcohol"],
                has_fear_elements=analysis["has_fear_elements"],
                violence_level=analysis["violence_level"],
                profanity_level=analysis["profanity_level"],
                sexual_content_level=analysis["sexual_content_level"],
                drugs_alcohol_level=analysis["drugs_alcohol_level"],
                fear_level=analysis["fear_level"],
                violence_severity=analysis["violence_severity"],
                profanity_severity=analysis["profanity_severity"],
                sexual_severity=analysis["sexual_severity"],
                drugs_severity=analysis["drugs_severity"],
                fear_severity=analysis["fear_severity"],
                assigned_rating=analysis["assigned_rating"],
                explanation=analysis["explanation"],
                correction_recommendations=analysis["correction_recommendations"],
                is_problematic=analysis["is_problematic"]
            )
            db.add(sentence_db)

        await db.commit()
        logger.info(f"✅ Анализ файла {file_id} завершен и сохранен в БД")

        # Возвращаем immediate результат
        return UploadResponse(
            file_id=file_id,
            filename=file.filename,
            overall_rating=overall_rating,
            summary=overall_summary,
            statistics=statistics,
            status="done"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке и анализе файла: {e}")

        # Обновляем статус ошибки в БД
        try:
            db_analysis.status = "error"
            db_analysis.summary = f"Ошибка обработки: {str(e)}"
            await db.commit()
        except:
            pass

        return JSONResponse(
            {"error": f"Internal server error: {str(e)}"},
            status_code=500
        )


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@app.get("/extracted-sentences/{file_id}", tags=["Анализ"])
async def get_extracted_sentences(file_id: str, db: AsyncSession = Depends(get_db)):
    """Возвращает текст файла, разбитый на предложения без анализа."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    db_analysis = result.scalar_one_or_none()

    if not db_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    if db_analysis.status == "processing":
        return {"status": "processing", "message": "Файл все еще обрабатывается"}

    if db_analysis.status == "error":
        return {"status": "error", "message": db_analysis.summary}

    # Получение всех предложений файла из базы данных
    sentence_result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == db_analysis.id)
        .order_by(SentenceAnalysis.sentence_id)
    )
    sentences = sentence_result.scalars().all()

    return {
        "status": "done",
        "filename": db_analysis.filename,
        "total_sentences": len(sentences),
        "sentences": [
            {
                "sentence_id": s.sentence_id,
                "sentence_text": s.sentence_text
            }
            for s in sentences
        ]
    }


@app.get("/full-analysis/{file_id}", tags=["Анализ"])
async def get_full_analysis(file_id: str, db: AsyncSession = Depends(get_db)):
    """Возвращает полный детальный анализ каждого предложения."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    db_analysis = result.scalar_one_or_none()

    if not db_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    if db_analysis.status == "processing":
        return {"status": "processing", "message": "Файл все еще обрабатывается"}

    if db_analysis.status == "error":
        return {"status": "error", "message": db_analysis.summary}

    # Получение всех предложений с анализом
    sentence_result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == db_analysis.id)
        .order_by(SentenceAnalysis.sentence_id)
    )
    sentences = sentence_result.scalars().all()

    # Фильтрация проблемных предложений
    problematic_sentences = [s for s in sentences if s.is_problematic]

    return {
        "status": "done",
        "filename": db_analysis.filename,
        "overall_rating": db_analysis.overall_rating,
        "summary": db_analysis.summary,
        "total_sentences": db_analysis.total_sentences,
        "problematic_sentences_count": len(problematic_sentences),
        "created_at": db_analysis.created_at.isoformat(),
        "sentences_analysis": [
            {
                "sentence_id": s.sentence_id,
                "sentence_text": s.sentence_text,
                "assigned_rating": s.assigned_rating,
                "is_problematic": s.is_problematic,
                "violations": {
                    "violence": {
                        "present": s.has_violence,
                        "level": s.violence_level,
                        "severity": s.violence_severity
                    },
                    "profanity": {
                        "present": s.has_profanity,
                        "level": s.profanity_level,
                        "severity": s.profanity_severity
                    },
                    "sexual_content": {
                        "present": s.has_sexual_content,
                        "level": s.sexual_content_level,
                        "severity": s.sexual_severity
                    },
                    "drugs_alcohol": {
                        "present": s.has_drugs_alcohol,
                        "level": s.drugs_alcohol_level,
                        "severity": s.drugs_severity
                    },
                    "fear_elements": {
                        "present": s.has_fear_elements,
                        "level": s.fear_level,
                        "severity": s.fear_severity
                    }
                },
                "explanation": s.explanation,
                "correction_recommendations": s.correction_recommendations,
                "is_false_positive": s.is_false_positive,
                "is_false_negative": s.is_false_negative,
                "user_correction_rating": s.user_correction_rating,
                "user_notes": s.user_notes
            }
            for s in sentences
        ],
        "problematic_sentences": [
            {
                "sentence_id": s.sentence_id,
                "sentence_text": s.sentence_text,
                "assigned_rating": s.assigned_rating,
                "explanation": s.explanation,
                "correction_recommendations": s.correction_recommendations
            }
            for s in problematic_sentences
        ]
    }


@app.get("/summary-analysis/{file_id}", tags=["Анализ"])
async def get_summary_analysis(file_id: str, db: AsyncSession = Depends(get_db)):
    """Возвращает краткий анализ с общей статистикой для фронтенда."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    db_analysis = result.scalar_one_or_none()

    if not db_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    if db_analysis.status == "processing":
        return {"status": "processing", "message": "Файл все еще обрабатывается"}

    if db_analysis.status == "error":
        return {"status": "error", "message": db_analysis.summary}

    # Получение статистики из базы данных
    statistics = db_analysis.statistics

    # Если статистика не сохранена в базе, вычисляем ее заново
    if statistics is None:
        sentence_result = await db.execute(
            select(SentenceAnalysis)
            .where(SentenceAnalysis.file_analysis_id == db_analysis.id)
            .order_by(SentenceAnalysis.sentence_id)
        )
        sentences = sentence_result.scalars().all()

        statistics = calculate_statistics([
            {
                "has_violence": s.has_violence,
                "has_profanity": s.has_profanity,
                "has_sexual_content": s.has_sexual_content,
                "has_drugs_alcohol": s.has_drugs_alcohol,
                "has_fear_elements": s.has_fear_elements,
                "is_problematic": s.is_problematic
            }
            for s in sentences
        ])

    return {
        "status": "done",
        "filename": db_analysis.filename,
        "overall_rating": db_analysis.overall_rating,
        "summary": db_analysis.summary,
        "statistics": statistics
    }


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@app.get("/files", tags=["управление данными"])
async def get_all_files(
        skip: int = Query(0, ge=0),
        limit: int = Query(10, ge=1, le=100),
        status: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    """Получение списка всех файлов с пагинацией и фильтрацией."""
    query = select(FileAnalysis)

    if status:
        query = query.where(FileAnalysis.status == status)

    query = query.order_by(FileAnalysis.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    files = result.scalars().all()

    return {
        "files": [
            {
                "file_id": file.file_id,
                "filename": file.filename,
                "status": file.status,
                "overall_rating": file.overall_rating,
                "total_sentences": file.total_sentences,
                "created_at": file.created_at.isoformat(),
            }
            for file in files
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": len(files)
        }
    }


@app.get("/files/{file_id}", tags=["управление данными"])
async def get_file(file_id: str, db: AsyncSession = Depends(get_db)):
    """Получение детальной информации о конкретном файле."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "file": {
            "file_id": file_analysis.file_id,
            "filename": file_analysis.filename,
            "status": file_analysis.status,
            "overall_rating": file_analysis.overall_rating,
            "summary": file_analysis.summary,
            "total_sentences": file_analysis.total_sentences,
            "statistics": file_analysis.statistics,
            "created_at": file_analysis.created_at.isoformat(),
        }
    }


@app.delete("/files/{file_id}", tags=["управление данными"])
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)):
    """Удаление файла и всех связанных с ним данных."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    # Удаление физического файла
    import glob
    file_pattern = os.path.join(UPLOAD_DIR, f"{file_id}_*")
    existing_files = glob.glob(file_pattern)
    for file_path in existing_files:
        try:
            os.remove(file_path)
        except OSError:
            pass

    # Удаление записи из базы данных
    await db.delete(file_analysis)
    await db.commit()

    return {"message": f"File {file_id} and all related data deleted successfully"}


@app.get("/database/stats", tags=["управление данными"])
async def get_database_stats(db: AsyncSession = Depends(get_db)):
    """Получение общей статистики по базе данных."""
    # Статистика по файлам
    files_result = await db.execute(select(FileAnalysis))
    all_files = files_result.scalars().all()

    total_files = len(all_files)
    processing_files = sum(1 for f in all_files if f.status == "processing")
    completed_files = sum(1 for f in all_files if f.status == "done")
    error_files = sum(1 for f in all_files if f.status == "error")

    # Статистика по предложениям
    sentences_result = await db.execute(select(SentenceAnalysis))
    all_sentences = sentences_result.scalars().all()

    total_sentences = len(all_sentences)
    problematic_sentences = sum(1 for s in all_sentences if s.is_problematic)

    return {
        "files": {
            "total": total_files,
            "processing": processing_files,
            "completed": completed_files,
            "error": error_files
        },
        "sentences": {
            "total": total_sentences,
            "problematic": problematic_sentences,
            "problematic_percentage": round(
                (problematic_sentences / total_sentences * 100) if total_sentences > 0 else 0, 1)
        }
    }


# =============================================================================
# MANUAL CORRECTION ENDPOINTS
# =============================================================================

class FalsePositiveRequest(BaseModel):
    file_id: str
    sentence_id: int
    notes: Optional[str] = None


class FalseNegativeRequest(BaseModel):
    file_id: str
    sentence_id: int
    violation_type: str
    user_rating: str
    notes: Optional[str] = None


class RatingCorrectionRequest(BaseModel):
    file_id: str
    sentence_id: int
    corrected_rating: str
    notes: Optional[str] = None


@app.post("/mark-false-positive", tags=["Ручная корректировка"])
async def mark_false_positive(
        request: FalsePositiveRequest,
        db: AsyncSession = Depends(get_db)
):
    """Пометка ложноположительного срабатывания."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == request.file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == file_analysis.id)
        .where(SentenceAnalysis.sentence_id == request.sentence_id)
    )
    sentence = result.scalar_one_or_none()

    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")

    sentence.is_false_positive = True
    sentence.user_notes = request.notes

    await db.commit()
    await recalculate_file_rating(request.file_id, db)

    return {"message": "Предложение помечено как ложноположительное"}


@app.post("/mark-false-negative", tags=["Ручная корректировка"])
async def mark_false_negative(
        request: FalseNegativeRequest,
        db: AsyncSession = Depends(get_db)
):
    """Пометка ложноотрицательного случая."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == request.file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == file_analysis.id)
        .where(SentenceAnalysis.sentence_id == request.sentence_id)
    )
    sentence = result.scalar_one_or_none()

    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")

    sentence.is_false_negative = True
    sentence.user_correction_rating = request.user_rating
    sentence.user_notes = request.notes

    violation_field_map = {
        "violence": "has_violence",
        "profanity": "has_profanity",
        "sexual_content": "has_sexual_content",
        "drugs_alcohol": "has_drugs_alcohol",
        "fear_elements": "has_fear_elements"
    }

    if request.violation_type in violation_field_map:
        setattr(sentence, violation_field_map[request.violation_type], True)

    await db.commit()
    await recalculate_file_rating(request.file_id, db)

    return {"message": "Добавлено ручное нарушение"}


@app.post("/correct-rating", tags=["Ручная корректировка"])
async def correct_rating(
        request: RatingCorrectionRequest,
        db: AsyncSession = Depends(get_db)
):
    """Ручная корректировка рейтинга предложения."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == request.file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == file_analysis.id)
        .where(SentenceAnalysis.sentence_id == request.sentence_id)
    )
    sentence = result.scalar_one_or_none()

    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")

    sentence.user_correction_rating = request.corrected_rating
    sentence.user_notes = request.notes

    await db.commit()
    await recalculate_file_rating(request.file_id, db)

    return {"message": "Рейтинг скорректирован"}


@app.get("/manual-corrections/{file_id}", tags=["Ручная корректировка"])
async def get_manual_corrections(
        file_id: str,
        db: AsyncSession = Depends(get_db)
):
    """Получение всех ручных корректировок для файла."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        raise HTTPException(status_code=404, detail="File not found")

    result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == file_analysis.id)
        .where(
            (SentenceAnalysis.is_false_positive == True) |
            (SentenceAnalysis.is_false_negative == True) |
            (SentenceAnalysis.user_correction_rating.isnot(None))
        )
        .order_by(SentenceAnalysis.sentence_id)
    )
    corrected_sentences = result.scalars().all()

    return {
        "file_id": file_id,
        "filename": file_analysis.filename,
        "corrected_sentences": [
            {
                "sentence_id": s.sentence_id,
                "sentence_text": s.sentence_text,
                "is_false_positive": s.is_false_positive,
                "is_false_negative": s.is_false_negative,
                "user_correction_rating": s.user_correction_rating,
                "user_notes": s.user_notes,
                "original_rating": s.assigned_rating,
                "current_rating": s.user_correction_rating or s.assigned_rating
            }
            for s in corrected_sentences
        ]
    }


async def recalculate_file_rating(file_id: str, db: AsyncSession):
    """Пересчитывает общий рейтинг файла с учетом ручных корректировок."""
    result = await db.execute(
        select(FileAnalysis).where(FileAnalysis.file_id == file_id)
    )
    file_analysis = result.scalar_one_or_none()

    if not file_analysis:
        return

    result = await db.execute(
        select(SentenceAnalysis)
        .where(SentenceAnalysis.file_analysis_id == file_analysis.id)
    )
    sentences = result.scalars().all()

    ratings = []
    rating_scores = {"0+": 0, "6+": 1, "12+": 2, "16+": 3, "18+": 4}

    for sentence in sentences:
        if sentence.is_false_positive:
            continue

        effective_rating = sentence.user_correction_rating or sentence.assigned_rating
        ratings.append(effective_rating)

    if ratings:
        max_rating = max(ratings, key=lambda x: rating_scores.get(x, 0))
        file_analysis.overall_rating = max_rating
        await db.commit()


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint для мониторинга."""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time()
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Отключаем reload для продакшена
    )