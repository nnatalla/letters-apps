import os
import sys
from pathlib import Path
import requests
import json
import mimetypes
from flask import Flask, request, jsonify, send_from_directory, send_file, redirect, url_for, render_template
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from groq import Groq
import tempfile
from datetime import datetime
from database import DatabaseManager
from models import init_db, db as orm_db, populate_test_data, Sender, GeneratedLetter, Plan
from auth import auth_bp
from ocr_utils import resolve_poppler_path, resolve_tesseract_cmd

# Wymuszenie UTF-8 na stdout (Windows cp1250 nie obsługuje emoji)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

BASE_DIR = Path(__file__).resolve().parent


def load_environment_files():
    load_dotenv(BASE_DIR / '.env')
    if (os.getenv('FLASK_ENV') or '').strip().lower() == 'production':
        for candidate in (BASE_DIR / '.env.production.new', BASE_DIR / '.env.production'):
            if candidate.exists():
                load_dotenv(candidate, override=True)
                break


# Load environment variables
load_environment_files()

# Production/Development environment detection
is_production = os.getenv('FLASK_ENV') == 'production'

if is_production:
    # Production configuration
    load_dotenv('.env.production')
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()
    poppler_path = resolve_poppler_path()
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/opt/avalon/temp_uploads')
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/opt/avalon/avalon_system.db')
else:
    # Development configuration
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()
    poppler_path = resolve_poppler_path() or r"C:\Poppler\poppler-23.01.0\Library\bin"
    UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'temp_uploads')
    DATABASE_PATH = 'avalon_system.db'

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database with correct path
db = DatabaseManager(DATABASE_PATH)

# ── SQLAlchemy ORM + Flask-Login ──────────────────────────────
init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"

@login_manager.user_loader
def load_user(user_id):
    try:
        from models import User
        return orm_db.session.get(User, int(user_id))
    except Exception:
        return None

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/') or request.path.startswith('/auth/'):
        return jsonify({"error": "Wymagane logowanie.", "code": 401}), 401
    return redirect(url_for('login_page'))

app.register_blueprint(auth_bp)

with app.app_context():
    orm_db.create_all()

    # Migracje SQLite: dodajemy nowe kolumny jeśli nie istnieją
    _new_columns = [
        ("users", "activation_token",       "VARCHAR(64)"),
        ("users", "reset_password_token",    "VARCHAR(64)"),
        ("users", "reset_password_expires",  "DATETIME"),
        ("users", "display_name",            "VARCHAR(100)"),
        ("users", "plan",                    "VARCHAR(10) NOT NULL DEFAULT 'free'"),
        ("users", "letters_used",            "INTEGER NOT NULL DEFAULT 0"),
        ("users", "letters_limit",           "INTEGER NOT NULL DEFAULT 50"),
        ("users", "theme",                   "VARCHAR(10) NOT NULL DEFAULT 'light'"),
        ("users", "email_notifications",     "BOOLEAN NOT NULL DEFAULT 1"),
        ("users", "last_login",              "DATETIME"),
        ("senders", "kategoria",             "VARCHAR(100)"),
    ]
    try:
        from sqlalchemy import text as _text
        with orm_db.engine.connect() as _conn:
            for _table, _col, _type in _new_columns:
                try:
                    _conn.execute(_text(f"ALTER TABLE {_table} ADD COLUMN {_col} {_type}"))
                    _conn.commit()
                except Exception:
                    pass  # Kolumna już istnieje
    except Exception as _e:
        print(f"Migracja kolumn: {_e}")

    # Seed planów (tylko jeśli tabela pusta)
    try:
        from models import Plan as _Plan
        if _Plan.query.count() == 0:
            orm_db.session.add_all([
                _Plan(name="free", display_name="Plan Free",   price=0,     letters_limit=50,  description="Darmowy plan startowy – 50 pism miesięcznie."),
                _Plan(name="S",    display_name="Plan S",      price=10000, letters_limit=50,  description="Plan S – 50 pism miesięcznie, wsparcie email."),
                _Plan(name="M",    display_name="Plan M",      price=20000, letters_limit=110, description="Plan M – 110 pism miesięcznie, priorytetowe wsparcie."),
                _Plan(name="L",    display_name="Plan L",      price=30000, letters_limit=200, description="Plan L – 200 pism miesięcznie, dedykowany opiekun."),
            ])
            orm_db.session.commit()
            print("✅ Plany dodane do bazy")
    except Exception as _e:
        print(f"Seed planów: {_e}")

    try:
        populate_test_data()
    except Exception as e:
        print(f"Seed danych: {e}")
# ─────────────────────────────────────────────────────────────

# Klucze API
GROQ_API_KEY = (os.getenv('GROQ_API_KEY') or '').strip().strip('"').strip("'")
if not GROQ_API_KEY:
    print("BŁĄD: Klucz API Groq nie został znaleziony! Upewnij się, że jest w pliku .env")
elif len(GROQ_API_KEY) < 20:
    print("BŁĄD: Klucz API Groq wygląda na nieprawidłowy lub niepełny.")

# Endpointy API
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

@app.route('/login')
def login_page():
    """Strona logowania — serwuje landing page z wbudowanym modałem logowania."""
    if current_user.is_authenticated:
        return redirect(url_for('serve_index'))
    response = send_from_directory('.', 'landing.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/register')
def register_page():
    """Strona rejestracji — serwuje landing page z otwartym modałem rejestracji."""
    if current_user.is_authenticated:
        return redirect(url_for('serve_index'))
    response = send_from_directory('.', 'landing.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/')
@login_required
def serve_index():
    """Endpoint do serwowania pliku index.html – bez cache po stronie przeglądarki."""
    response = send_from_directory('.', 'index.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/logo.png')
def serve_logo():
    """Endpoint do serwowania pliku logo.png."""
    return send_from_directory('static', 'logo.png')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Endpoint do serwowania plików statycznych."""
    return send_from_directory('static', filename)

@app.route('/process-file', methods=['POST'])
@login_required
def process_file():
    """Endpoint do przetwarzania przeslanego pliku.
    Próbuje kolejkować przez Celery; jeśli Redis jest niedostępny, przetwarza synchronicznie.
    """
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"error": "Brak pliku w zadaniu lub nazwa pliku jest pusta"}), 400

    file = request.files['file']
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(file.filename)
    if not safe_name:
        return jsonify({"error": "Nieprawidlowa nazwa pliku"}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)

    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({"error": f"Nie udalo sie zapisac pliku: {e}"}), 500

    # Próba async przez Celery + Redis
    try:
        from tasks import process_document_task
        task = process_document_task.delay(filepath, safe_name)
        return jsonify({"task_id": task.id})
    except Exception:
        pass  # Redis niedostępny – fallback do przetwarzania synchronicznego

    # Fallback: synchroniczne OCR + analiza (gdy Redis/Celery niedostępny)
    try:
        import pytesseract
        from PIL import Image
        from pdf2image import convert_from_path
        from orchestrator import process_document

        pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd()
        poppler_path = resolve_poppler_path() or r'C:\Poppler\poppler-23.01.0\Library\bin'

        file_extension = os.path.splitext(safe_name)[1].lower()
        ocr_text = ''

        if file_extension == '.pdf':
            images = convert_from_path(filepath, poppler_path=poppler_path)
            for i, image in enumerate(images[:5]):
                page_text = pytesseract.image_to_string(image, lang='pol')
                ocr_text += f'\n--- STRONA {i+1} ---\n{page_text}\n'
        elif file_extension in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'):
            ocr_text = pytesseract.image_to_string(Image.open(filepath), lang='pol')
        else:
            raise ValueError(f'Nieobslugiwany format pliku: {file_extension}')

        if not ocr_text.strip():
            raise ValueError('Nie udalo sie wyodrebnic tekstu z pliku.')

        result = process_document(ocr_text)
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": f"Blad przetwarzania: {e}"}), 500
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass
@login_required
def task_status(task_id):
    """Sprawdza status zadania Celery i zwraca wynik gdy gotowy."""
    try:
        from tasks import celery as celery_app
        task = celery_app.AsyncResult(task_id)
        if task.state == 'PENDING':
            return jsonify({"status": "PENDING"})
        elif task.state == 'STARTED':
            return jsonify({"status": "STARTED"})
        elif task.state == 'SUCCESS':
            return jsonify({"status": "SUCCESS", "result": task.result})
        elif task.state == 'FAILURE':
            return jsonify({"status": "FAILURE", "error": str(task.info)})
        return jsonify({"status": task.state})
    except Exception as e:
        return jsonify({"error": f"Blad pobierania statusu zadania: {e}"}), 500
def extract_data_with_groq(ocr_text):
    """Funkcja używająca Groq do ekstrakcji danych ze zdeskturyzowanego tekstu."""
    if not ocr_text or ocr_text.strip() == "":
        return {
            "komornik": {"imieNazwisko": None, "adres": None, "miasto": None, "telefon": None, "email": None, "plec": "M"},
            "dluznik": {"imieNazwisko": None, "pesel": None},
            "sprawa": {"sygnaturaSprawy": None, "numerRachunku": None}
        }
    
    prompt = f"""
    Jesteś inteligentnym asystentem do analizy pism komorniczych.
    Twoim zadaniem jest wyodrębnienie kluczowych danych z poniższego tekstu, który został rozpoznany za pomocą OCR.
    Zwróć dane w formacie JSON z następującymi kluczami:
    {{
        "komornik": {{
            "imieNazwisko": "imię i nazwisko komornika",
            "adres": "adres bez kodu i miasta",
            "miasto": "kod pocztowy i miasto",
            "telefon": "numer telefonu",
            "email": "adres e-mail",
            "plec": "M lub K - na podstawie imienia komornika"
        }},
        "dluznik": {{
            "imieNazwisko": "imię i nazwisko dłużnika",
            "pesel": "numer PESEL dłużnika"
        }},
        "sprawa": {{
            "sygnaturaSprawy": "sygnatura sprawy",
            "numerRachunku": "numer rachunku bankowego"
        }}
    }}
    
    WAŻNE: W polu "plec" wpisz:
    - "M" jeśli komornik to mężczyzna (na podstawie imienia jak Jan, Piotr, Tomasz, Adam, itp.)
    - "K" jeśli komornik to kobieta (na podstawie imienia jak Anna, Maria, Katarzyna, Monika, itp.)
    
    Jeśli dane pole nie jest dostępne w tekście, przypisz mu wartość "null".
    
    Tekst do analizy:
    ---
    {ocr_text}
    ---
    
    Twój output musi być czystym JSON-em, bez dodatkowego tekstu ani formatowania.
    """
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data)
        response.raise_for_status()
        groq_result = response.json()
        
        json_string = groq_result['choices'][0]['message']['content']
        
        # Nowe linie kodu: usunięcie znaków markdown przed parsowaniem JSON
        cleaned_json_string = json_string.strip().strip('`').strip()
        cleaned_json_string = cleaned_json_string.replace('json', '', 1).strip()
        
        return json.loads(cleaned_json_string)
    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, 'status_code', None)
        response_text = getattr(e.response, 'text', '')
        if status_code == 401:
            raise ValueError(
                "Autoryzacja Groq odrzucona (401). Sprawdź wartość GROQ_API_KEY w pliku .env, "
                "czy nie ma spacji/cudzysłowów i czy klucz jest aktywny."
            ) from e
        raise ValueError(f"Błąd HTTP podczas ekstrakcji danych (Groq): {status_code} - {response_text}") from e
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Błąd komunikacji z Groq AI: {e}") from e
    except (json.JSONDecodeError, KeyError) as e:
        print(f"!!! DIAGNOSTYKA BŁĘDU GROQ AI !!!")
        print(f"Status Code: {response.status_code}")
        print(f"Surowa odpowiedź: {response.text}")
        print("-------------------------------------")
        raise ValueError(f"Błąd przetwarzania odpowiedzi Groq AI: Otrzymano nieoczekiwany format. {e}") from e
# ... (pozostały kod bez zmian)
def _check_letter_limit_and_save(user, title, document_type, subtype, html_content, sender_name, recipient_name):
    """Sprawdza limit pism i zapisuje do historii. Zwraca (True, None) lub (False, response)."""
    if user.letters_used >= user.letters_limit:
        return False, (jsonify({"error": f"Przekroczono miesięczny limit pism ({user.letters_limit}). Zmień plan lub poczekaj do następnego miesiąca."}), 429)
    letter = GeneratedLetter(
        user_id=user.id,
        title=title,
        document_type=document_type,
        subtype=subtype,
        html_content=html_content,
        sender_name=sender_name,
        recipient_name=recipient_name,
    )
    orm_db.session.add(letter)
    user.letters_used = (user.letters_used or 0) + 1
    orm_db.session.commit()
    return True, letter

@app.route('/generate-letter', methods=['POST'])
@login_required
def generate_letter():
    """Endpoint do generowania listów za pomocą Groq AI z szablonem HTML."""
    payload = request.get_json()
    
    opcja = payload['option']
    dane = payload['dane']
    company = payload['company']
    sender = payload.get('sender') or {}
    user_instructions = payload.get('user_instructions', '')

    sender_company = (sender.get('nazwa') or company or '').strip()
    sender_street = (sender.get('adres') or '').strip()
    sender_postal = (sender.get('kod_pocztowy') or sender.get('kod') or '').strip()
    sender_city = (sender.get('miasto') or '').strip()
    sender_phone = (sender.get('telefon') or '').strip()
    sender_email = (sender.get('email') or '').strip()

    sender_city_line = " ".join(part for part in [sender_postal, sender_city] if part).strip()
    sender_address = ", ".join(part for part in [sender_street, sender_city_line] if part) or 'ul. Przykładowa 1, 90-001 Łódź'
    sender_contact = " / ".join(part for part in [sender_phone, sender_email] if part) or 'tel: 123456789 / email: biuro@avalon.pl'
    
    # Przygotowanie danych dla szablonu
    sender_data = {
        'company': sender_company or company,
        'address': sender_address,
        'contact': sender_contact
    }
    
    recipient_data = {
        'name': dane['komornik']['imieNazwisko'],
        'address': f"{dane['komornik']['adres']}, {dane['komornik']['miasto']}"
    }
    
    _opcja_labels = {
        1: "osoba nie pracuje",
        2: "błędne pismo",
        3: "zajęcie wierzytelności",
        4: "zbieg komorniczy",
    }
    _subtype_label = _opcja_labels.get(opcja, f"opcja {opcja}")
    _recipient_name = dane['komornik'].get('imieNazwisko', '')

    if opcja == 1:
        content_type = "INFORMACJA O ZAKOŃCZENIU WSPÓŁPRACY Z FIRMĄ"
        bailiff_greeting = get_bailiff_greeting(dane['komornik'].get('plec', 'M'))
        specific_content = f"""
        <p>{bailiff_greeting},</p>
        <p>Informuję, iż <strong>{dane['dluznik']['imieNazwisko']}</strong> PESEL: <strong>{dane['dluznik']['pesel']}</strong>,
        zakończyła współpracę z naszą firmą w dniu <strong>{dane.get('dataZakonczenia', 'nie podano')}</strong>.</p>
        <p>W związku z powyższym, osoba ta nie jest już naszym pracownikiem/współpracownikiem.</p>
        """

        try:
            specific_content = apply_user_instructions_to_content(
                specific_content, user_instructions, content_type
            )
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            ok, result = _check_letter_limit_and_save(
                current_user,
                title=f"Odpowiedź na pismo komornicze – {_subtype_label}",
                document_type="KOMORNICZE",
                subtype=_subtype_label,
                html_content=generated_content,
                sender_name=sender_data['company'],
                recipient_name=_recipient_name,
            )
            if not ok:
                return result
            return jsonify({"list": generated_content, "letter_id": result.id})
        except Exception as e:
            return jsonify({"error": f"Błąd generowania listu: {e}"}), 500

    elif opcja == 2:
        content_type = "INFORMACJA O BŁĘDNYM CHARAKTERZE PISMA"
        bailiff_greeting = get_bailiff_greeting(dane['komornik'].get('plec', 'M'))
        specific_content = f"""
        <p>{bailiff_greeting},</p>
        <p>W odpowiedzi na otrzymane pismo, informujemy że <strong>{dane['dluznik']['imieNazwisko']}</strong>
        PESEL: <strong>{dane['dluznik']['pesel']}</strong> rzeczywiście pracuje w naszej spółce.</p>
        <p>Otrzymane pismo dotyczy wynagrodzenia za pracę, podczas gdy osoba ta jest aktualnie zatrudniona.
        Prosimy o wyjaśnienie charakteru pisma lub przesłanie właściwego dokumentu dotyczącego zajęcia wierzytelności.</p>
        """

        try:
            specific_content = apply_user_instructions_to_content(
                specific_content, user_instructions, content_type
            )
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            ok, result = _check_letter_limit_and_save(
                current_user,
                title=f"Odpowiedź na pismo komornicze – {_subtype_label}",
                document_type="KOMORNICZE",
                subtype=_subtype_label,
                html_content=generated_content,
                sender_name=sender_data['company'],
                recipient_name=_recipient_name,
            )
            if not ok:
                return result
            return jsonify({"list": generated_content, "letter_id": result.id})
        except Exception as e:
            return jsonify({"error": f"Błąd generowania listu: {e}"}), 500

    elif opcja == 3:
        umowy_tekst = []
        if dane['umowy']['zlecenie']:
            umowy_tekst.append("umowa zlecenie")
        if dane['umowy']['najem']:
            umowy_tekst.append("umowa najmu pojazdu")

        umowy_str = " i ".join(umowy_tekst) if umowy_tekst else "umowa współpracy"

        content_type = "POTWIERDZENIE ZATRUDNIENIA I ZAJĘCIA WIERZYTELNOŚCI"
        bailiff_greeting = get_bailiff_greeting(dane['komornik'].get('plec', 'M'))
        specific_content = f"""
        <p>{bailiff_greeting},</p>
        <p>Potwierdzamy, że <strong>{dane['dluznik']['imieNazwisko']}</strong> PESEL: <strong>{dane['dluznik']['pesel']}</strong>
        pracuje w naszej spółce na podstawie: <strong>{umowy_str}</strong>.</p>
        <p>Otrzymane pismo dotyczące zajęcia wierzytelności jest prawidłowe. Jesteśmy gotowi do wykonania postanowień
        zawartych w piśmie zgodnie z obowiązującymi przepisami.</p>
        <p>Sygnatura sprawy: <strong>{dane['sprawa']['sygnaturaSprawy']}</strong></p>
        """

        try:
            specific_content = apply_user_instructions_to_content(
                specific_content, user_instructions, content_type
            )
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            ok, result = _check_letter_limit_and_save(
                current_user,
                title=f"Odpowiedź na pismo komornicze – {_subtype_label}",
                document_type="KOMORNICZE",
                subtype=_subtype_label,
                html_content=generated_content,
                sender_name=sender_data['company'],
                recipient_name=_recipient_name,
            )
            if not ok:
                return result
            return jsonify({"list": generated_content, "letter_id": result.id})
        except Exception as e:
            return jsonify({"error": f"Błąd generowania listu: {e}"}), 500

    return jsonify({"error": "Nieobsługiwana opcja."}), 400

@app.route('/generate-zbieg-letters', methods=['POST'])
@login_required
def generate_zbieg_letters():
    """Endpoint do generowania osobnych listów dla każdego komornika w przypadku zbiegu z szablonem HTML."""
    payload = request.get_json()
    
    dane = payload['dane']
    company = payload['company']
    sender = payload.get('sender') or {}
    user_instructions = payload.get('user_instructions', '')
    all_bailiffs = dane['komornicy']

    sender_company = (sender.get('nazwa') or company or '').strip()
    sender_street = (sender.get('adres') or '').strip()
    sender_postal = (sender.get('kod_pocztowy') or sender.get('kod') or '').strip()
    sender_city = (sender.get('miasto') or '').strip()
    sender_phone = (sender.get('telefon') or '').strip()
    sender_email = (sender.get('email') or '').strip()

    sender_city_line = " ".join(part for part in [sender_postal, sender_city] if part).strip()
    sender_address = ", ".join(part for part in [sender_street, sender_city_line] if part) or 'ul. Przykładowa 1, 90-001 Łódź'
    sender_contact = " / ".join(part for part in [sender_phone, sender_email] if part) or 'tel: 123456789 / email: biuro@avalon.pl'
    
    if len(all_bailiffs) < 2:
        return jsonify({"error": "Zbieg komorniczy wymaga co najmniej 2 komorników"}), 400
    
    generated_letters = []
    
    # Przygotowanie danych nadawcy
    sender_data = {
        'company': sender_company or company,
        'address': sender_address,
        'contact': sender_contact
    }
    
    for i, recipient_bailiff in enumerate(all_bailiffs):
        # Pozostali komornicy (wszyscy oprócz adresata)
        other_bailiffs = [b for j, b in enumerate(all_bailiffs) if i != j]
        
        # Przygotowanie danych adresata
        recipient_data = {
            'name': recipient_bailiff['imieNazwisko'],
            'address': f"{recipient_bailiff['adres']}, {recipient_bailiff['miasto']}",
            'plec': recipient_bailiff.get('plec', 'M')
        }
        
        # Tworzenie listy pozostałych komorników w formacie z wcięciem
        other_bailiffs_list = '<div style="text-align: left; margin: 20px 0;">'
        for other in other_bailiffs:
            other_bailiffs_list += f"""
            <div style="margin-bottom: 15px; text-align: left;">
                <span style="margin-left: 20px;">• <strong>{other['imieNazwisko']}</strong></span><br>
                <span style="margin-left: 60px;">Adres: {other['adres']}, {other['miasto']}</span><br>
                <span style="margin-left: 60px;">Sygnatura sprawy: {other['sygnaturaSprawy']}</span><br>
                <span style="margin-left: 60px;">Data wpływu pisma: {other['dataWplywu']}</span>
            </div>
            """
        other_bailiffs_list += "</div>"
        
        # Określ płeć komornika - najpierw sprawdź w bazie danych
        bailiff_gender = recipient_bailiff.get('plec', None)
        if not bailiff_gender or bailiff_gender == 'null':
            # Pobierz płeć z bazy danych na podstawie imienia i nazwiska
            bailiff_from_db = db.get_bailiff_by_name(recipient_bailiff['imieNazwisko'])
            if bailiff_from_db:
                bailiff_gender = bailiff_from_db.get('plec', 'M')
                print(f"Pobrano płeć z bazy dla {recipient_bailiff['imieNazwisko']}: {bailiff_gender}")
            else:
                # Jeśli nie ma w bazie, spróbuj określić na podstawie imienia
                first_name = recipient_bailiff['imieNazwisko'].split()[0].lower()
                female_names = ['anna', 'maria', 'katarzyna', 'monika', 'barbara', 'agnieszka', 'magdalena', 'małgorzata', 'beata', 'dorota', 'joanna', 'aleksandra', 'ewa', 'marta', 'karolina']
                bailiff_gender = 'k' if first_name in female_names else 'm'
                print(f"Określono płeć na podstawie imienia dla {recipient_bailiff['imieNazwisko']}: {bailiff_gender}")
        
        bailiff_greeting = get_bailiff_greeting(bailiff_gender)
        
        content_type = "INFORMACJA O ZBIEGU KOMORNICZYM"
        specific_content = f"""
        <p>{bailiff_greeting},</p>
        <p>Niniejszym informujemy, że w sprawie egzekucyjnej dotyczącej dłużnika <strong>{dane['dluznik']['imieNazwisko']}</strong> 
        (PESEL: <strong>{dane['dluznik']['pesel']}</strong>), sygnatura Państwa sprawy: <strong>{recipient_bailiff['sygnaturaSprawy']}</strong>, 
        wystąpił zbieg egzekucji komorniczej.</p>
        
        <p>Pisma egzekucyjne w tej samej sprawie wpłynęły również od następujących komorników sądowych:</p>
        {other_bailiffs_list}
        
        <p>Zgodnie z obowiązującymi przepisami, prosimy o podjęcie odpowiednich działań w związku z zaistniałym zbiegiem egzekucji.</p>
        
        <p>W przypadku pytań, pozostajemy do dyspozycji.</p>
        """
        
        try:
            specific_content = apply_user_instructions_to_content(
                specific_content, user_instructions, content_type
            )
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            
            letter_title = f"List do komornika {recipient_bailiff['imieNazwisko']}"
            
            generated_letters.append({
                "title": letter_title,
                "content": generated_content,
                "bailiff": recipient_bailiff
            })
            
        except Exception as e:
            print(f"Błąd podczas generowania listu dla komornika {recipient_bailiff['imieNazwisko']}: {e}")
            
            # Fallback - użyj podstawowego szablonu
            basic_content = f"""
            <!DOCTYPE html>
            <html lang="pl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pismo do Komornika</title>
                <style>
                    body {{ font-family: "Times New Roman", serif; line-height: 1.6; margin: 40px; }}
                    .date {{ text-align: right; margin-bottom: 40px; }}
                    .sender {{ margin-bottom: 80px; }}
                    .recipient {{ text-align: right; margin-bottom: 20px; }}
                    .title {{ text-align: center; font-weight: bold; margin-bottom: 40px; text-transform: uppercase; }}
                    .content {{ text-align: justify; margin-bottom: 40px; }}
                    .closing {{ margin-top: 40px; }}
                    .signature {{ margin-top: 60px; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="date">Łódź, dnia {get_current_date()} r.</div>
                
                <div class="sender">
                    <strong>{sender_data.get('company', company)}</strong><br>
                    {sender_data.get('address', '')}<br>
                    {sender_data.get('contact', '')}
                </div>

                <div class="recipient">
                    Komornik Sądowy przy<br>
                    <strong>Sąd Rejonowy w Łodzi</strong><br>
                    {recipient_bailiff['imieNazwisko']}<br>
                    {recipient_bailiff['adres']}<br>
                    {recipient_bailiff['miasto']}
                </div>

                <div class="title">INFORMACJA O ZBIEGU KOMORNICZYM</div>

                <div class="content">
                    {specific_content}
                </div>

                <div class="closing">Z poważaniem,</div>
                
                <div class="signature">
                    ...............................................<br>
                    [Podpis nadawcy]
                </div>
            </body>
            </html>
            """
            
            generated_letters.append({
                "title": f"List do komornika {recipient_bailiff['imieNazwisko']}",
                "content": basic_content,
                "bailiff": recipient_bailiff
            })
    
    return jsonify({"listy": generated_letters})

def load_html_template():
    """Wczytuje szablon HTML z pliku szablon komornik.html"""
    template_path = os.path.join(os.path.dirname(__file__), 'szablon komornik.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Uwaga: Nie znaleziono pliku szablonu HTML w: {template_path}")
        return None

def get_current_date():
    """Zwraca aktualną datę w formacie polskim."""
    from datetime import datetime
    return datetime.now().strftime('%d.%m.%Y')

def get_bailiff_greeting(gender):
    """Zwraca odpowiedni nagłówek na podstawie płci komornika"""
    if gender and gender.upper() == 'K':
        return "Szanowna Pani Komornik"
    else:
        return "Szanowny Panie Komorniku"

def apply_user_instructions_to_content(base_html, user_instructions, content_type):
    """Modyfikuje treść akapitów zgodnie z instrukcjami użytkownika bez dodawania sekcji 'Uwagi dodatkowe'."""
    instructions = (user_instructions or '').strip()
    if not instructions:
        return base_html

    prompt = f"""
Przepisz treść pisma (HTML) zgodnie z instrukcjami użytkownika.

WYMAGANIA:
- Zwróć wyłącznie HTML akapitów (np. <p>...</p>), bez markdown i bez komentarzy.
- Zachowaj formalny styl urzędowy.
- Zachowaj kluczowe fakty i dane (imiona, PESEL, sygnatura, itp.), chyba że instrukcja wyraźnie każe inaczej.
- NIE dodawaj osobnej sekcji typu "Uwagi dodatkowe".
- Zachowaj poprawność językową i logiczny układ.

Typ pisma: {content_type}
Instrukcje użytkownika:
{instructions}

Treść wejściowa HTML:
{base_html}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=45)
        response.raise_for_status()
        out = response.json()['choices'][0]['message']['content'].strip()

        if '```' in out:
            parts = out.split('```')
            for chunk in parts:
                chunk = chunk.strip()
                if chunk.startswith('html'):
                    chunk = chunk[4:].strip()
                if '<p' in chunk:
                    out = chunk
                    break

        return out or base_html
    except Exception:
        return base_html
def generate_letter_with_template(content_type, sender_data, recipient_data, case_data, specific_content):
    """Generuje list na podstawie szablonu HTML poprzez proste zastępowanie tekstu"""
    template = load_html_template()
    
    if not template:
        # Fallback na podstawowy szablon
        return f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Pismo do Komornika</title>
            <style>
                body {{ font-family: "Times New Roman", serif; line-height: 1.6; margin: 40px; }}
                .date {{ text-align: right; margin-bottom: 40px; }}
                .sender {{ margin-bottom: 80px; }}
                .recipient {{ text-align: right; margin-bottom: 20px; }}
                .sender, .sender *, .recipient, .recipient * {{ color: #000 !important; }}
                .title {{ text-align: center; font-weight: bold; margin-bottom: 40px; text-transform: uppercase; }}
                .content {{ text-align: justify; margin-bottom: 40px; }}
                .closing {{ margin-top: 40px; }}
                .signature {{ margin-top: 60px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="date">Łódź, dnia {get_current_date()} r.</div>
            <div class="sender">
                <strong>{sender_data.get('company', 'Firma')}</strong><br>
                {sender_data.get('address', 'ul. Przykładowa 123')}<br>
                {sender_data.get('contact', 'tel/email')}
            </div>
            <div class="recipient">
                Komornik Sądowy przy<br>
                <strong>Sąd Rejonowy w Łodzi</strong><br>
                {recipient_data.get('name', 'Nieznany')}<br>
                {recipient_data.get('address', '')}
            </div>
            <div class="title">{content_type}</div>
            <div class="content">
                {specific_content}
            </div>
            <div class="closing">Z poważaniem,</div>
            <div class="signature">
                ...............................................<br>
                [Podpis nadawcy]
            </div>
        </body>
        </html>
        """
    
    # Użyj prostego zastępowania tekstu zamiast AI
    current_date = get_current_date()
    
    # Zastąp dane w szablonie
    filled_template = template
    
    # Zastąp datę
    filled_template = filled_template.replace(
        'Łódź, dnia 26 sierpnia 2025 r.',
        f'Łódź, dnia {current_date} r.'
    )
    
    # Zastąp dane firmy
    filled_template = filled_template.replace(
        'Firma Przykladowa',
        sender_data.get('company', 'Firma')
    )
    filled_template = filled_template.replace(
        'ul. Przykladowa 123',
        sender_data.get('address', 'ul. Przykładowa 123')
    )
    filled_template = filled_template.replace(
        '123456789 / firma@przykladowa.pl',
        sender_data.get('contact', 'tel/email')
    )
    
    # Zastąp dane komornika
    filled_template = filled_template.replace(
        'Jan Kowalski',
        recipient_data.get('name', 'Nieznany')
    )
    filled_template = filled_template.replace(
        'ul. Piotrkowska 123',
        recipient_data.get('address', '')
    )
    
    # Zastąp tytuł pisma
    filled_template = filled_template.replace(
        'INFORMACJA O ZAKOŃCZENIU WSPÓŁPRACY Z FIRMĄ',
        content_type
    )
    
    # Zastąp treść pisma wraz z nagłówkiem
    filled_template = filled_template.replace(
        '<p>Szanowny Panie Komorniku,</p>\n            <p>Informuję, iż Anna Nowak PESEL: 85010112345, zakończyła współpracę z naszą firmą.</p>',
        specific_content
    )
    
    # Dodatkowa obsługa dla przypadków gdy szablon ma inną strukturę
    filled_template = filled_template.replace(
        '<p>Szanowny Panie Komorniku,</p>',
        f'<p>{get_bailiff_greeting(recipient_data.get("plec", "M"))},</p>'
    )
 
    
    return filled_template


@app.route('/generate-universal-letter', methods=['POST'])
@login_required
def generate_universal_letter():
    """Endpoint do generowania listów dla dowolnego typu pisma (nie-komorniczego)."""
    try:
        from letter_generator import generate_universal_letter as gen_letter
        payload = request.get_json()

        category = payload.get('category', 'INNE')
        subtype = payload.get('subtype', 'nieznane')
        fields = payload.get('fields', [])
        company = payload.get('company', '')
        recipient_name = payload.get('recipient_name', '')
        sender = payload.get('sender', None)
        scenario = payload.get('scenario', None)
        user_instructions = payload.get('user_instructions', '')

        if not company:
            return jsonify({"error": "Wybierz spółkę"}), 400

        letter_html = gen_letter(
            category=category,
            subtype=subtype,
            extracted_fields=fields,
            company_name=company,
            scenario=scenario,
            user_instructions=user_instructions,
            sender=sender
        )

        ok, result = _check_letter_limit_and_save(
            current_user,
            title=f"Odpowiedź na pismo: {subtype}",
            document_type=category,
            subtype=subtype,
            html_content=letter_html,
            sender_name=company,
            recipient_name=recipient_name,
        )
        if not ok:
            return result

        return jsonify({
            "list": letter_html,
            "title": f"Odpowiedź na pismo: {subtype}",
            "letter_id": result.id,
        })
    except Exception as e:
        return jsonify({"error": f"Błąd generowania pisma uniwersalnego: {str(e)}"}), 500


@app.route('/api/document-categories', methods=['GET'])
@login_required
def get_document_categories():
    """Zwraca listę kategorii dokumentów (do ewentualnego użycia w UI)."""
    from classifier import CATEGORIES
    return jsonify({"categories": list(CATEGORIES.keys())})


# ── HISTORIA PISM ─────────────────────────────────────────────────────────────

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    """Zwraca listę wygenerowanych pism zalogowanego użytkownika."""
    try:
        letters = (
            GeneratedLetter.query
            .filter_by(user_id=current_user.id)
            .order_by(GeneratedLetter.created_at.desc())
            .limit(100)
            .all()
        )
        return jsonify({
            "history": [
                {
                    "id": l.id,
                    "title": l.title,
                    "document_type": l.document_type,
                    "subtype": l.subtype,
                    "sender_name": l.sender_name,
                    "recipient_name": l.recipient_name,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                    "has_pdf": bool(l.file_pdf),
                    "has_doc": bool(l.file_doc),
                }
                for l in letters
            ]
        })
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania historii: {str(e)}"}), 500

@app.route('/api/history/<int:letter_id>', methods=['GET'])
@login_required
def get_history_item(letter_id):
    """Zwraca pełne dane pisma wraz z html_content."""
    try:
        letter = orm_db.session.get(GeneratedLetter, letter_id)
        if not letter or letter.user_id != current_user.id:
            return jsonify({"error": "Pismo nie zostało znalezione."}), 404
        return jsonify({"letter": letter.to_dict()})
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania pisma: {str(e)}"}), 500


@app.route('/api/history/<int:letter_id>/title', methods=['PUT'])
@login_required
def update_history_title(letter_id):
    """Aktualizuje nazwę (tytuł) pisma w historii."""
    try:
        letter = orm_db.session.get(GeneratedLetter, letter_id)
        if not letter or letter.user_id != current_user.id:
            return jsonify({"error": "Pismo nie zostało znalezione."}), 404

        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()

        if len(title) < 2:
            return jsonify({"error": "Nazwa pisma musi mieć co najmniej 2 znaki."}), 400
        if len(title) > 180:
            return jsonify({"error": "Nazwa pisma może mieć maksymalnie 180 znaków."}), 400

        letter.title = title
        orm_db.session.commit()
        return jsonify({"success": True, "id": letter.id, "title": letter.title})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd aktualizacji nazwy pisma: {str(e)}"}), 500


@app.route('/api/history/<int:letter_id>', methods=['DELETE'])
@login_required
def delete_history_item(letter_id):
    """Usuwa pismo z historii."""
    try:
        letter = orm_db.session.get(GeneratedLetter, letter_id)
        if not letter or letter.user_id != current_user.id:
            return jsonify({"error": "Pismo nie zostało znalezione."}), 404
        orm_db.session.delete(letter)
        orm_db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd usuwania pisma: {str(e)}"}), 500


@app.route('/api/history/<int:letter_id>/download-pdf', methods=['POST'])
@login_required
def history_download_pdf(letter_id):
    """Generuje i zwraca PDF z zapisanego pisma."""
    try:
        letter = orm_db.session.get(GeneratedLetter, letter_id)
        if not letter or letter.user_id != current_user.id:
            return jsonify({"error": "Pismo nie zostało znalezione."}), 404
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in letter.title)[:60]
        filename = f"{safe_title}.pdf"
        return _generate_pdf_response(letter.html_content, filename)
    except Exception as e:
        return jsonify({"error": f"Błąd generowania PDF: {str(e)}"}), 500


@app.route('/api/history/<int:letter_id>/download-doc', methods=['POST'])
@login_required
def history_download_doc(letter_id):
    """Generuje i zwraca DOCX z zapisanego pisma."""
    try:
        letter = orm_db.session.get(GeneratedLetter, letter_id)
        if not letter or letter.user_id != current_user.id:
            return jsonify({"error": "Pismo nie zostało znalezione."}), 404
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in letter.title)[:60]
        filename = f"{safe_title}.docx"
        return _generate_docx_response(letter.html_content, filename)
    except Exception as e:
        return jsonify({"error": f"Błąd generowania DOCX: {str(e)}"}), 500


# ── Helpery generowania plików (reużywane przez endpointy i historię) ──────────

CONVERTAPI_TOKEN = 'MX6Frilh3wiPvR3BvAwlbWCCRxPNLrGn'

def _extract_letter_body(html_content):
    """Ekstrahuje czystą treść listu (bez screen-only wrapperów i stylów)."""
    import re as _re

    # Zamień flex-spacers na zwykłe marginesy przed parseowaniem
    content = html_content
    content = content.replace('<div style="flex: 1.5"></div>', '<div style="height:40px"></div>')
    content = content.replace('<div style="flex: 1"></div>', '<div style="height:20px"></div>')

    # Przypadek 1: pełny dokument HTML (komornicze — szablon komornik.html)
    if _re.search(r'<!DOCTYPE|<html\b', content, _re.IGNORECASE):
        m = _re.search(r'<body[^>]*>([\s\S]*?)</body>', content, _re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return content

    # Przypadek 2: fragment z <style>...<div class="a4-frame"><div class="wrapper">
    # Usuń blok <style>
    content = _re.sub(r'<style[\s\S]*?</style>', '', content, flags=_re.IGNORECASE).strip()

    # Usuń otwierający tag .a4-frame i zamykający go </div> na końcu
    content = _re.sub(r'^\s*<div\s[^>]*class="a4-frame"[^>]*>\s*', '', content)
    # Usuń ostatni </div> (zamknięcie .a4-frame)
    content = _re.sub(r'\s*</div>\s*$', '', content)

    # Zostawia .wrapper div wewnątrz — to jest potrzebne dla zachowania klas CSS
    return content.strip()


def _wrap_html_for_export(html_content, for_pdf=False):
    """Opakowuje treść listu w pełny dokument HTML gotowy do konwersji na DOCX/PDF."""
    body_content = _extract_letter_body(html_content)
    page_style = "@page { margin:2cm 2.5cm; size:A4; } " if for_pdf else ""
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="UTF-8"><title>Pismo</title>
<style>
{page_style}
body {{ font-family:"Times New Roman",serif; font-size:12pt; line-height:1.6;
  margin:0; padding:2cm 2.5cm; background:white; color:black; }}
/* Reset layoutu ekranowego — Word nie obsługuje flex */
.a4-frame {{ display:block!important; background:white!important; padding:0!important; }}
.wrapper {{ display:block!important; width:auto!important; min-height:0!important;
  padding:0!important; background:white!important; box-shadow:none!important; }}
/* Kolory i tła */
div,p,span,strong,em,h1,h2,h3,h4,h5,h6,table,td,tr {{ background:transparent!important; color:black!important; }}
/* Elementy listu */
.date {{ text-align:right; margin-bottom:24px; }}
.sender {{ margin-bottom:48px; }}
.recipient {{ text-align:right; margin-bottom:24px; }}
.title {{ text-align:center; font-weight:bold; text-transform:uppercase; margin:0 0 28px; }}
.content {{ text-align:justify; }}
.content p {{ margin:0 0 10px; }}
.closing {{ margin-top:28px; }}
.signature {{ margin-top:48px; font-weight:bold; }}
</style></head><body>{body_content}</body></html>"""


def _generate_docx_response(html_content, filename):
    """Konwertuje HTML → DOCX przez ConvertAPI i zwraca jako send_file."""
    optimized_html = _wrap_html_for_export(html_content)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp:
        tmp.write(optimized_html)
        html_path = tmp.name
    try:
        with open(html_path, 'rb') as f:
            resp = requests.post(
                'https://v2.convertapi.com/convert/html/to/docx',
                headers={'Authorization': f'Bearer {CONVERTAPI_TOKEN}'},
                files={'File': f},
                data={'StoreFile': 'true'},
                timeout=60,
            )
        if resp.status_code != 200:
            return jsonify({"error": f"Błąd ConvertAPI: {resp.text}"}), 500
        docx_url = resp.json()['Files'][0]['Url']
        docx_bytes = requests.get(docx_url, timeout=60).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_d:
            tmp_d.write(docx_bytes)
            docx_path = tmp_d.name
        response = send_file(
            docx_path, as_attachment=True, download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        @response.call_on_close
        def _cleanup():
            for p in (html_path, docx_path):
                try: os.unlink(p)
                except Exception: pass
        return response
    except Exception:
        try: os.unlink(html_path)
        except Exception: pass
        raise


def _generate_pdf_response(html_content, filename):
    """Konwertuje HTML → DOCX → PDF przez ConvertAPI i zwraca jako send_file."""
    optimized_html = _wrap_html_for_export(html_content, for_pdf=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp:
        tmp.write(optimized_html)
        html_path = tmp.name
    try:
        with open(html_path, 'rb') as f:
            resp = requests.post(
                'https://v2.convertapi.com/convert/html/to/docx',
                headers={'Authorization': f'Bearer {CONVERTAPI_TOKEN}'},
                files={'File': f},
                data={'StoreFile': 'true'},
                timeout=60,
            )
        if resp.status_code != 200:
            return jsonify({"error": f"Błąd ConvertAPI (HTML→DOCX): {resp.text}"}), 500
        docx_url = resp.json()['Files'][0]['Url']
        docx_bytes = requests.get(docx_url, timeout=60).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_d:
            tmp_d.write(docx_bytes)
            docx_path = tmp_d.name
        with open(docx_path, 'rb') as f:
            resp2 = requests.post(
                'https://v2.convertapi.com/convert/docx/to/pdf',
                headers={'Authorization': f'Bearer {CONVERTAPI_TOKEN}'},
                files={'File': f},
                data={'StoreFile': 'true'},
                timeout=60,
            )
        if resp2.status_code != 200:
            return jsonify({"error": f"Błąd ConvertAPI (DOCX→PDF): {resp2.text}"}), 500
        pdf_url = resp2.json()['Files'][0]['Url']
        pdf_bytes = requests.get(pdf_url, timeout=60).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_p:
            tmp_p.write(pdf_bytes)
            pdf_path = tmp_p.name
        response = send_file(
            pdf_path, as_attachment=True, download_name=filename,
            mimetype='application/pdf',
        )
        @response.call_on_close
        def _cleanup():
            for p in (html_path, docx_path, pdf_path):
                try: os.unlink(p)
                except Exception: pass
        return response
    except Exception:
        try: os.unlink(html_path)
        except Exception: pass
        raise


@app.route('/download-pdf', methods=['POST'])
@login_required
def download_pdf():
    """Endpoint do pobierania listu w formacie PDF używając ConvertAPI (HTML->DOCX->PDF)"""
    try:
        data = request.get_json()
        html_content = data.get('html_content', '')
        filename = data.get('filename', 'list_komornika.pdf')
        
        if not html_content:
            return jsonify({"error": "Brak treści HTML"}), 400

        return _generate_pdf_response(html_content, filename)

    except Exception as e:
        return jsonify({"error": f"Błąd przygotowania pliku PDF: {str(e)}"}), 500


@app.route('/download-doc', methods=['POST'])
@login_required
def download_doc():
    """Endpoint do pobierania listu w formacie DOC używając ConvertAPI"""
    try:
        data = request.get_json()
        html_content = data.get('html_content', '')
        filename = data.get('filename', 'list_komornika.docx')
        
        if not html_content:
            return jsonify({"error": "Brak treści HTML"}), 400

        return _generate_docx_response(html_content, filename)

    except Exception as e:
        return jsonify({"error": f"Błąd przygotowania pliku DOC: {str(e)}"}), 500


@app.route('/api/employee/<pesel>', methods=['GET'])
@login_required
def get_employee_by_pesel(pesel):
    """Endpoint do pobierania danych pracownika na podstawie PESEL"""
    try:
        employee = db.get_employee_by_pesel(pesel)
        if employee:
            # Sprawdź czy istnieje zbieg komorniczy
            conflict_info = db.detect_bailiff_conflict(pesel)
            
            return jsonify({
                "employee": employee,
                "bailiff_conflict": conflict_info,
                "found": True
            })
        else:
            return jsonify({
                "employee": None,
                "bailiff_conflict": None,
                "found": False
            })
    except Exception as e:
        return jsonify({"error": f"Błąd wyszukiwania pracownika: {str(e)}"}), 500

@app.route('/api/bailiffs', methods=['GET'])
@login_required
def get_all_bailiffs():
    """Endpoint do pobierania listy wszystkich komorników"""
    try:
        bailiffs = db.get_all_bailiffs()
        return jsonify({"bailiffs": bailiffs})
    
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania komorników: {str(e)}"}), 500

@app.route('/api/proceedings/<pesel>', methods=['GET'])
@login_required
def get_bailiff_proceedings(pesel):
    """Endpoint do pobierania postępowań komorniczych dla danego PESEL"""
    try:
        proceedings = db.get_bailiff_proceedings(pesel)
        conflict_info = db.detect_bailiff_conflict(pesel)
        
        return jsonify({
            "proceedings": proceedings,
            "conflict_info": conflict_info
        })
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania postępowań: {str(e)}"}), 500

@app.route('/api/initialize-database', methods=['POST'])
@login_required
def initialize_database():
    """Endpoint do inicjalizacji bazy danych z danymi testowymi"""
    try:
        db.populate_test_data()
        return jsonify({"message": "Baza danych została zainicjalizowana pomyślnie", "success": True})
    
    except Exception as e:
        return jsonify({"error": f"Błąd inicjalizacji bazy danych: {str(e)}"}), 500

@app.route('/api/auto-detect-scenario', methods=['POST'])
@login_required
def auto_detect_scenario():
    """Endpoint do automatycznego wykrywania scenariusza na podstawie danych OCR"""
    try:
        data = request.get_json()
        pesel = data.get('pesel', '').strip()
        
        if not pesel:
            return jsonify({"error": "PESEL jest wymagany"}), 400
        
        # Pobierz dane pracownika
        employee = db.get_employee_by_pesel(pesel)
        
        if not employee:
            return jsonify({
                "scenario": 1,  # Osoba nie pracuje
                "reason": "Pracownik nie został znaleziony w bazie danych",
                "employee_found": False
            })
        
        # Sprawdź status zatrudnienia
        if employee['status_zatrudnienia'] == 'zwolniony' or employee['data_zwolnienia']:
            return jsonify({
                "scenario": 1,  # Osoba nie pracuje
                "reason": "Pracownik jest zwolniony",
                "employee_found": True,
                "employee": employee,
                "end_date": employee['data_zwolnienia']
            })
        
        # Sprawdź zbieg komorniczy
        conflict_info = db.detect_bailiff_conflict(pesel)
        
        if conflict_info['is_conflict']:
            # Jeśli już istnieją aktywne postępowania - zbieg komorniczy
            return jsonify({
                "scenario": 4,  # Zbieg komorniczy
                "reason": f"Wykryto {conflict_info['active_proceedings_count']} aktywnych postępowań komorniczych",
                "employee_found": True,
                "employee": employee,
                "existing_proceedings": conflict_info['proceedings']
            })
        
        # Sprawdź typ umowy dla scenariusza 3
        if employee['typ_umowy'] in ['umowa zlecenie', 'najem pojazdu']:
            return jsonify({
                "scenario": 3,  # Zajęcie wierzytelności
                "reason": f"Pracownik aktywny, typ umowy: {employee['typ_umowy']}",
                "employee_found": True,
                "employee": employee,
                "contract_type": employee['typ_umowy']
            })
        
        # Domyślnie scenariusz 3 dla aktywnych pracowników
        return jsonify({
            "scenario": 3,  # Zajęcie wierzytelności
            "reason": "Pracownik aktywny, standardowa umowa o pracę",
            "employee_found": True,
            "employee": employee
        })
    
    except Exception as e:
        return jsonify({"error": f"Błąd automatycznego wykrywania scenariusza: {str(e)}"}), 500

@app.route('/api/add-bailiff', methods=['POST'])
@login_required
def add_bailiff():
    """Endpoint do dodawania nowego komornika"""
    try:
        data = request.get_json()
        
        # Walidacja wymaganych pól
        required_fields = ['imie_nazwisko', 'adres', 'kod_pocztowy', 'miasto', 'plec']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Pole '{field}' jest wymagane"}), 400
        
        # Sprawdź czy komornik już istnieje
        existing_bailiff = db.get_bailiff_by_name(data['imie_nazwisko'])
        if existing_bailiff:
            return jsonify({"error": "Komornik o takim imieniu i nazwisku już istnieje w bazie"}), 400
        
        # Dodaj komornika
        bailiff_id = db.add_new_bailiff(
            imie_nazwisko=data['imie_nazwisko'],
            plec=data['plec'].lower(),
            adres=data['adres'],
            kod_pocztowy=data['kod_pocztowy'],
            miasto=data['miasto'],
            telefon=data.get('telefon', ''),
            email=data.get('email', ''),
            sad_rejonowy=data.get('sad_rejonowy', '')
        )
        
        return jsonify({
            "message": "Komornik został dodany pomyślnie",
            "success": True,
            "bailiff_id": bailiff_id
        })
    
    except Exception as e:
        return jsonify({"error": f"Błąd dodawania komornika: {str(e)}"}), 500

@app.route('/api/delete-bailiff', methods=['DELETE'])
@login_required
def delete_bailiff():
    """Endpoint do usuwania komornika"""
    try:
        data = request.get_json()
        bailiff_id = data.get('bailiff_id')
        confirmation = data.get('confirmation', '').strip().lower()
        
        if not bailiff_id:
            return jsonify({"error": "ID komornika jest wymagane"}), 400
            
        if confirmation != 'potwierdzam':
            return jsonify({"error": "Nieprawidłowe potwierdzenie. Wpisz dokładnie 'potwierdzam'"}), 400
        
        # Sprawdź czy komornik istnieje
        bailiff = db.get_bailiff_by_id(bailiff_id)
        if not bailiff:
            return jsonify({"error": "Komornik o podanym ID nie istnieje"}), 404
        
        # Usuń komornika (soft delete)
        success = db.delete_bailiff(bailiff_id)
        
        if success:
            return jsonify({
                "message": f"Komornik {bailiff['imie_nazwisko']} został usunięty pomyślnie",
                "success": True
            })
        else:
            return jsonify({"error": "Nie udało się usunąć komornika"}), 500
    
    except Exception as e:
        return jsonify({"error": f"Błąd usuwania komornika: {str(e)}"}), 500

@app.route('/api/test-connection', methods=['GET'])
@login_required
def test_connection():
    """Test endpoint do sprawdzenia połączenia"""
    import time
    timestamp = time.time()
    print(f"🧪 TEST CONNECTION - timestamp: {timestamp}")
    return jsonify({
        "message": f"Połączenie działa! Timestamp: {timestamp}",
        "timestamp": timestamp
    })

@app.route('/api/update-bailiff', methods=['PUT'])
@login_required
def update_bailiff():
    """Endpoint do aktualizacji danych komornika"""
    try:
        data = request.get_json()
        bailiff_id = data.get('bailiff_id')
        
        print(f"🔧 Aktualizacja komornika - ID: {bailiff_id} (typ: {type(bailiff_id)})")
        print(f"🔧 Dane do aktualizacji: {data}")
        
        if not bailiff_id:
            return jsonify({"error": "ID komornika jest wymagane"}), 400
        
        # Sprawdź czy komornik istnieje
        existing_bailiff = db.get_bailiff_by_id(bailiff_id)
        if not existing_bailiff:
            return jsonify({"error": "Komornik o podanym ID nie istnieje"}), 404
        
        # Walidacja wymaganych pól
        required_fields = ['imie_nazwisko', 'plec', 'adres', 'kod_pocztowy', 'miasto']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Pole {field} jest wymagane"}), 400
        
        # Walidacja płci
        if data.get('plec') not in ['m', 'k']:
            return jsonify({"error": "Płeć musi być 'm' lub 'k'"}), 400
        
        # Aktualizuj komornika
        success = db.update_bailiff(
            bailiff_id=bailiff_id,
            imie_nazwisko=data.get('imie_nazwisko'),
            plec=data.get('plec'),
            adres=data.get('adres'),
            kod_pocztowy=data.get('kod_pocztowy'),
            miasto=data.get('miasto'),
            telefon=data.get('telefon', ''),
            email=data.get('email', ''),
            sad_rejonowy=data.get('sad_rejonowy', '')
        )
        
        if success:
            # Pobierz zaktualizowane dane komornika
            updated_bailiff = db.get_bailiff_by_id(bailiff_id)
            if updated_bailiff:
                return jsonify({
                    "message": "Dane komornika zostały zaktualizowane pomyślnie",
                    "success": True,
                    "bailiff": {
                        "id": updated_bailiff['id'],
                        "imie_nazwisko": updated_bailiff['imie_nazwisko'],
                        "plec": updated_bailiff['plec'],
                        "adres": updated_bailiff['adres'],
                        "kod_pocztowy": updated_bailiff['kod_pocztowy'],
                        "miasto": updated_bailiff['miasto'],
                        "telefon": updated_bailiff['telefon'],
                        "email": updated_bailiff['email'],
                        "sad_rejonowy": updated_bailiff['sad_rejonowy']
                    }
                })
            else:
                return jsonify({"error": "Nie udało się pobrać zaktualizowanych danych komornika"}), 500
        else:
            return jsonify({"error": "Nie udało się zaktualizować danych komornika"}), 500
    
    except Exception as e:
        return jsonify({"error": f"Błąd aktualizacji komornika: {str(e)}"}), 500

# ── Zarządzanie nadawcami ────────────────────────────────────────────────────

@app.route('/api/senders', methods=['GET'])
@login_required
def get_senders():
    """Lista nadawców zalogowanego użytkownika"""
    try:
        senders = Sender.query.filter_by(user_id=current_user.id).order_by(Sender.nazwa).all()
        return jsonify([s.to_dict() for s in senders])
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania nadawców: {str(e)}"}), 500


@app.route('/api/senders', methods=['POST'])
@login_required
def add_sender():
    """Dodaj nowego nadawcę"""
    try:
        data = request.get_json()
        if not data or not data.get('nazwa'):
            return jsonify({"error": "Pole nazwa jest wymagane"}), 400
        sender = Sender(
            user_id=current_user.id,
            nazwa=data.get('nazwa'),
            adres=data.get('adres', ''),
            miasto=data.get('miasto', ''),
            kod_pocztowy=data.get('kod_pocztowy', ''),
            telefon=data.get('telefon', ''),
            email=data.get('email', ''),
            kategoria=data.get('kategoria', '')
        )
        orm_db.session.add(sender)
        orm_db.session.commit()
        return jsonify(sender.to_dict()), 201
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd dodawania nadawcy: {str(e)}"}), 500


@app.route('/api/senders/<int:sender_id>', methods=['PUT'])
@login_required
def update_sender(sender_id):
    """Edytuj nadawcę (tylko właściciela)"""
    try:
        sender = Sender.query.get(sender_id)
        if not sender:
            return jsonify({"error": "Nadawca nie istnieje"}), 404
        if sender.user_id != current_user.id:
            return jsonify({"error": "Brak uprawnień"}), 403
        data = request.get_json()
        if not data or not data.get('nazwa'):
            return jsonify({"error": "Pole nazwa jest wymagane"}), 400
        sender.nazwa = data.get('nazwa')
        sender.adres = data.get('adres', sender.adres)
        sender.miasto = data.get('miasto', sender.miasto)
        sender.kod_pocztowy = data.get('kod_pocztowy', sender.kod_pocztowy)
        sender.telefon = data.get('telefon', sender.telefon)
        sender.email = data.get('email', sender.email)
        sender.kategoria = data.get('kategoria', sender.kategoria)
        orm_db.session.commit()
        return jsonify(sender.to_dict())
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd aktualizacji nadawcy: {str(e)}"}), 500


@app.route('/api/senders/<int:sender_id>', methods=['DELETE'])
@login_required
def delete_sender(sender_id):
    """Usuń nadawcę (tylko właściciela)"""
    try:
        sender = Sender.query.get(sender_id)
        if not sender:
            return jsonify({"error": "Nadawca nie istnieje"}), 404
        if sender.user_id != current_user.id:
            return jsonify({"error": "Brak uprawnień"}), 403
        orm_db.session.delete(sender)
        orm_db.session.commit()
        return jsonify({"message": "Nadawca usunięty"})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd usuwania nadawcy: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# USTAWIENIA UŻYTKOWNIKA
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/settings/profile', methods=['GET'])
@login_required
def settings_profile():
    """Zwróć dane profilu zalogowanego użytkownika."""
    try:
        return jsonify({
            "display_name": current_user.display_name,
            "email": current_user.email,
            "plan": current_user.plan,
            "letters_used": current_user.letters_used,
            "letters_limit": current_user.letters_limit,
            "theme": current_user.theme,
            "email_notifications": current_user.email_notifications,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        })
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania profilu: {str(e)}"}), 500


@app.route('/api/settings/display-name', methods=['POST'])
@login_required
def settings_display_name():
    """Zmień wyświetlaną nazwę użytkownika."""
    try:
        data = request.get_json(silent=True) or {}
        display_name = (data.get('display_name') or '').strip()

        if len(display_name) < 2:
            return jsonify({"error": "Nazwa musi mieć co najmniej 2 znaki"}), 400
        if len(display_name) > 50:
            return jsonify({"error": "Nazwa może mieć maksymalnie 50 znaków"}), 400

        current_user.display_name = display_name
        orm_db.session.commit()
        return jsonify({"success": True, "display_name": display_name})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd zapisu nazwy: {str(e)}"}), 500


@app.route('/api/settings/change-password', methods=['POST'])
@login_required
def settings_change_password():
    """Zmień hasło użytkownika – wymaga podania aktualnego hasła."""
    try:
        from werkzeug.security import check_password_hash, generate_password_hash

        data = request.get_json(silent=True) or {}
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({"error": "Aktualne hasło jest nieprawidłowe"}), 400

        if len(new_password) < 8:
            return jsonify({"error": "Nowe hasło musi mieć co najmniej 8 znaków"}), 400
        if not any(c.isdigit() for c in new_password):
            return jsonify({"error": "Nowe hasło musi zawierać co najmniej jedną cyfrę"}), 400
        if new_password != confirm_password:
            return jsonify({"error": "Hasła nie są identyczne"}), 400

        current_user.password_hash = generate_password_hash(new_password)
        orm_db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd zmiany hasła: {str(e)}"}), 500


@app.route('/api/settings/theme', methods=['POST'])
@login_required
def settings_theme():
    """Zapisz preferowany motyw (light/dark)."""
    try:
        data = request.get_json(silent=True) or {}
        theme = data.get('theme', '')

        if theme not in ('light', 'dark'):
            return jsonify({"error": "Dozwolone wartości: light, dark"}), 400

        current_user.theme = theme
        orm_db.session.commit()
        return jsonify({"success": True, "theme": theme})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd zapisu motywu: {str(e)}"}), 500


@app.route('/api/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    """Włącz lub wyłącz powiadomienia e-mail."""
    try:
        data = request.get_json(silent=True) or {}
        value = data.get('email_notifications')

        if not isinstance(value, bool):
            return jsonify({"error": "Pole email_notifications musi być true lub false"}), 400

        current_user.email_notifications = value
        orm_db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        orm_db.session.rollback()
        return jsonify({"error": f"Błąd zapisu ustawień powiadomień: {str(e)}"}), 500


@app.route('/api/settings/plans', methods=['GET'])
@login_required
def settings_plans():
    """Zwróć listę dostępnych planów z oznaczeniem aktywnego planu użytkownika."""
    try:
        plans = Plan.query.order_by(Plan.price).all()
        result = []
        for p in plans:
            d = p.to_dict()
            d['is_current'] = (p.name == current_user.plan)
            result.append(d)
        return jsonify({"plans": result, "current_plan": current_user.plan})
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania planów: {str(e)}"}), 500


if __name__ == '__main__':
    # Inicjalizuj bazę danych przy starcie aplikacji
    try:
        db.populate_test_data()
        print("🚀 Aplikacja uruchomiona z bazą danych")
    except Exception as e:
        print(f"⚠️ Ostrzeżenie: Problem z bazą danych: {e}")
    
    # Production vs Development server configuration
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=not is_production)
