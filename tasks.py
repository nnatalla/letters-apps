import os
import sys
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv
from ocr_utils import resolve_poppler_path, resolve_tesseract_cmd

BASE_DIR = Path(__file__).resolve().parent


def load_environment_files():
    load_dotenv(BASE_DIR / '.env')
    if (os.getenv('FLASK_ENV') or '').strip().lower() == 'production':
        for candidate in (BASE_DIR / '.env.production.new', BASE_DIR / '.env.production'):
            if candidate.exists():
                load_dotenv(candidate, override=True)
                break


load_environment_files()

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Europe/Warsaw',
    enable_utc=True,
    task_track_started=True,
)

is_production = os.getenv('FLASK_ENV') == 'production'

if is_production:
    load_dotenv('.env.production')
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()
    POPPLER_PATH = resolve_poppler_path()
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/opt/avalon/temp_uploads')
else:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()
    POPPLER_PATH = resolve_poppler_path() or r'C:\Poppler\poppler-23.01.0\Library\bin'
    UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'temp_uploads')


@celery.task(bind=True, name='tasks.process_document_task',
             max_retries=2, soft_time_limit=120, time_limit=180)
def process_document_task(self, filepath, filename):
    """Wykonuje OCR, klasyfikuje pismo i wyciaga pola."""
    from PIL import Image
    from pdf2image import convert_from_path
    from orchestrator import process_document

    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()

    try:
        file_extension = os.path.splitext(filename)[1].lower()
        ocr_text = ''

        if file_extension == '.pdf':
            if POPPLER_PATH:
                images = convert_from_path(filepath, poppler_path=POPPLER_PATH)
            else:
                images = convert_from_path(filepath)
            max_pages = min(len(images), 5)
            for i, image in enumerate(images[:max_pages]):
                page_text = pytesseract.image_to_string(image, lang='pol')
                ocr_text += f'\n--- STRONA {i+1} ---\n{page_text}\n'
        elif file_extension in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'):
            ocr_text = pytesseract.image_to_string(Image.open(filepath), lang='pol')
        else:
            raise ValueError(f'Nieobslugiwany format pliku: {file_extension}')

        if not ocr_text.strip():
            raise ValueError('Nie udalo sie wyodrebnic tekstu z pliku.')

        result = process_document(ocr_text)
        return result

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass


@celery.task(bind=True, name='tasks.generate_letter_task',
             max_retries=1, soft_time_limit=60, time_limit=90)
def generate_letter_task(self, category, subtype, fields, sender, scenario=None):
    """Generuje HTML odpowiedzi na pismo (tryb uniwersalny)."""
    from letter_generator import generate_universal_letter as gen_letter

    company_name = (sender or {}).get('nazwa', '')

    try:
        letter_html = gen_letter(
            category=category,
            subtype=subtype,
            extracted_fields=fields,
            company_name=company_name,
            scenario=scenario,
        )
        return {
            'list': letter_html,
            'title': f'Odpowiedz na pismo: {subtype}',
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=3)
