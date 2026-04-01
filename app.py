import os
import requests
import json
import mimetypes
from flask import Flask, request, jsonify, send_from_directory, send_file
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from groq import Groq
import tempfile
from datetime import datetime
from database import DatabaseManager

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Production/Development environment detection
is_production = os.getenv('FLASK_ENV') == 'production'

if is_production:
    # Production configuration
    load_dotenv('.env.production')
    pytesseract.pytesseract.tesseract_cmd = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')
    poppler_path = os.getenv('POPPLER_PATH', '/usr/bin')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/opt/avalon/temp_uploads')
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/opt/avalon/avalon_system.db')
else:
    # Development configuration
    pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'
    poppler_path = r"C:\Poppler\poppler-23.01.0\Library\bin"
    UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'temp_uploads')
    DATABASE_PATH = 'avalon_system.db'

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database with correct path
db = DatabaseManager(DATABASE_PATH)

# Klucze API
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    print("BŁĄD: Klucz API Groq nie został znaleziony! Upewnij się, że jest w pliku .env")

# Endpointy API
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

@app.route('/')
def serve_index():
    """Endpoint do serwowania pliku index.html."""
    return send_from_directory('.', 'index.html')

@app.route('/logo.png')
def serve_logo():
    """Endpoint do serwowania pliku logo.png."""
    return send_from_directory('static', 'logo.png')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Endpoint do serwowania plików statycznych."""
    return send_from_directory('static', filename)

@app.route('/process-file', methods=['POST'])
def process_file():
    """Endpoint do przetwarzania przesłanego pliku - obsługuje wszystkie typy pism."""
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"error": "Brak pliku w żądaniu lub nazwa pliku jest pusta"}), 400

    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

    try:
        file.save(filepath)
        file_extension = os.path.splitext(file.filename)[1].lower()
        ocr_text = ""

        if file_extension == '.pdf':
            print("Przetwarzanie pliku PDF...")
            try:
                if poppler_path:
                    images = convert_from_path(filepath, poppler_path=poppler_path)
                else:
                    images = convert_from_path(filepath)
                max_pages = min(len(images), 5)
                for i, image in enumerate(images[:max_pages]):
                    page_text = pytesseract.image_to_string(image, lang='pol')
                    ocr_text += f"\n--- STRONA {i+1} ---\n{page_text}\n"
            except Exception as pdf_error:
                return jsonify({"error": f"Błąd przetwarzania PDF: {str(pdf_error)}"}), 500

        elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
            ocr_text = pytesseract.image_to_string(Image.open(filepath), lang='pol')
        else:
            return jsonify({"error": "Nieobsługiwany format pliku."}), 400

        if not ocr_text.strip():
            return jsonify({"error": "Nie udało się wyodrębnić tekstu z pliku."}), 400

        # NOWA LOGIKA: orkiestrator zamiast bezpośredniego wywołania Groq
        from orchestrator import process_document
        result = process_document(ocr_text)

        if result['mode'] == 'komornicze':
            # Stara ścieżka - zwracamy stary format, frontend działa bez zmian
            return jsonify({
                "dane": result['dane'],
                "mode": "komornicze",
                "classification": result['classification']
            })
        else:
            # Nowa ścieżka - zwracamy dynamiczne pola
            return jsonify({
                "mode": "universal",
                "classification": result['classification'],
                "fields": result['fields'],
                "summary": result['summary'],
                "suggested_response_type": result['suggested_response_type']
            })

    except Exception as e:
        return jsonify({"error": f"Wystąpił nieoczekiwany błąd: {e}"}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
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
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
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
        raise ValueError(f"Błąd HTTP podczas ekstrakcji danych (Groq): {e.response.status_code} - {e.response.text}") from e
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Błąd komunikacji z Groq AI: {e}") from e
    except (json.JSONDecodeError, KeyError) as e:
        print(f"!!! DIAGNOSTYKA BŁĘDU GROQ AI !!!")
        print(f"Status Code: {response.status_code}")
        print(f"Surowa odpowiedź: {response.text}")
        print("-------------------------------------")
        raise ValueError(f"Błąd przetwarzania odpowiedzi Groq AI: Otrzymano nieoczekiwany format. {e}") from e
# ... (pozostały kod bez zmian)

@app.route('/generate-letter', methods=['POST'])
def generate_letter():
    """Endpoint do generowania listów za pomocą Groq AI z szablonem HTML."""
    payload = request.get_json()
    
    opcja = payload['option']
    dane = payload['dane']
    company = payload['company']
    
    # Przygotowanie danych dla szablonu
    sender_data = {
        'company': company,
        'address': 'ul. Przykładowa 1, 90-001 Łódź',
        'contact': 'tel: 123456789 / email: biuro@avalon.pl'
    }
    
    recipient_data = {
        'name': dane['komornik']['imieNazwisko'],
        'address': f"{dane['komornik']['adres']}, {dane['komornik']['miasto']}"
    }
    
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
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            return jsonify({"list": generated_content})
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
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            return jsonify({"list": generated_content})
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
            generated_content = generate_letter_with_template(
                content_type, sender_data, recipient_data, dane, specific_content
            )
            return jsonify({"list": generated_content})
        except Exception as e:
            return jsonify({"error": f"Błąd generowania listu: {e}"}), 500

    return jsonify({"error": "Nieobsługiwana opcja."}), 400

@app.route('/generate-zbieg-letters', methods=['POST'])
def generate_zbieg_letters():
    """Endpoint do generowania osobnych listów dla każdego komornika w przypadku zbiegu z szablonem HTML."""
    payload = request.get_json()
    
    dane = payload['dane']
    company = payload['company']
    all_bailiffs = dane['komornicy']
    
    if len(all_bailiffs) < 2:
        return jsonify({"error": "Zbieg komorniczy wymaga co najmniej 2 komorników"}), 400
    
    generated_letters = []
    
    # Przygotowanie danych nadawcy
    sender_data = {
        'company': company,
        'address': 'ul. Przykładowa 1, 90-001 Łódź',
        'contact': 'tel: 123456789 / email: biuro@avalon.pl'
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
                    <strong>{company}</strong><br>
                    ul. Przykładowa 1<br>
                    90-001 Łódź<br>
                    tel: 123456789 / email: biuro@avalon.pl
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
def generate_universal_letter():
    """Endpoint do generowania listów dla dowolnego typu pisma (nie-komorniczego)."""
    try:
        from letter_generator import generate_universal_letter as gen_letter
        payload = request.get_json()

        category = payload.get('category', 'INNE')
        subtype = payload.get('subtype', 'nieznane')
        fields = payload.get('fields', [])
        company = payload.get('company', '')
        scenario = payload.get('scenario', None)

        if not company:
            return jsonify({"error": "Wybierz spółkę"}), 400

        letter_html = gen_letter(
            category=category,
            subtype=subtype,
            extracted_fields=fields,
            company_name=company,
            scenario=scenario
        )

        return jsonify({
            "list": letter_html,
            "title": f"Odpowiedź na pismo: {subtype}"
        })

    except Exception as e:
        return jsonify({"error": f"Błąd generowania listu: {str(e)}"}), 500


@app.route('/api/document-categories', methods=['GET'])
def get_document_categories():
    """Zwraca listę kategorii dokumentów (do ewentualnego użycia w UI)."""
    from classifier import CATEGORIES
    return jsonify({"categories": list(CATEGORIES.keys())})


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    """Endpoint do pobierania listu w formacie PDF używając ConvertAPI (HTML->DOCX->PDF)"""
    try:
        data = request.get_json()
        html_content = data.get('html_content', '')
        filename = data.get('filename', 'list_komornika.pdf')
        
        if not html_content:
            return jsonify({"error": "Brak treści HTML"}), 400
        
        # HTML zoptymalizowany pod konwersję do DOCX
        optimized_html = f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <title>List do Komornika</title>
            <style>
                @page {{
                    margin: 2cm;
                    size: A4;
                    background: white;
                }}
                * {{
                    box-sizing: border-box;
                }}
                body {{
                    font-family: "Times New Roman", serif;
                    font-size: 12pt;
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    background: white !important;
                    color: black !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                .wrapper {{
                    width: 100%;
                    max-width: none;
                    margin: 0;
                    padding: 0;
                    background: white !important;
                }}
                div, p, span, strong, h1, h2, h3, h4, h5, h6 {{
                    background: transparent !important;
                    background-color: transparent !important;
                }}
                .sender, .recipient, .date, .title, .content, .closing, .signature {{
                    background: transparent !important;
                    background-color: transparent !important;
                }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                {html_content}
            </div>
        </body>
        </html>
        """
        
        # Krok 1: Zapisz HTML do tymczasowego pliku
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp_html:
            tmp_html.write(optimized_html)
            html_path = tmp_html.name
        
        try:
            # Krok 2: Konwertuj HTML do DOCX
            with open(html_path, 'rb') as html_file:
                docx_response = requests.post(
                    'https://v2.convertapi.com/convert/html/to/docx',
                    headers={
                        'Authorization': 'Bearer GApx2nuOlCaqNCEhn8uY8KiS0RB0FeE6'
                    },
                    files={
                        'File': html_file
                    },
                    data={
                        'StoreFile': 'true'
                    }
                )
            
            if docx_response.status_code == 200:
                docx_result = docx_response.json()
                docx_url = docx_result['Files'][0]['Url']
                
                # Pobierz DOCX
                docx_download = requests.get(docx_url)
                if docx_download.status_code == 200:
                    # Zapisz DOCX do tymczasowego pliku
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_docx:
                        tmp_docx.write(docx_download.content)
                        docx_path = tmp_docx.name
                    
                    # Krok 3: Konwertuj DOCX do PDF
                    with open(docx_path, 'rb') as docx_file:
                        pdf_response = requests.post(
                            'https://v2.convertapi.com/convert/docx/to/pdf',
                            headers={
                                'Authorization': 'Bearer GApx2nuOlCaqNCEhn8uY8KiS0RB0FeE6'
                            },
                            files={
                                'File': docx_file
                            },
                            data={
                                'StoreFile': 'true'
                            }
                        )
                    
                    if pdf_response.status_code == 200:
                        pdf_result = pdf_response.json()
                        pdf_url = pdf_result['Files'][0]['Url']
                        
                        # Pobierz PDF
                        pdf_download = requests.get(pdf_url)
                        if pdf_download.status_code == 200:
                            # Zapisz PDF do tymczasowego pliku
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                                tmp_pdf.write(pdf_download.content)
                                pdf_path = tmp_pdf.name
                            
                            response = send_file(
                                pdf_path,
                                as_attachment=True,
                                download_name=filename,
                                mimetype='application/pdf'
                            )
                            
                            def remove_files(response):
                                try:
                                    os.unlink(html_path)
                                    os.unlink(docx_path)
                                    os.unlink(pdf_path)
                                except Exception:
                                    pass
                                return response
                            
                            response.call_on_close(remove_files)
                            return response
                        else:
                            return jsonify({"error": "Błąd pobierania PDF z ConvertAPI"}), 500
                    else:
                        return jsonify({"error": f"Błąd konwersji DOCX do PDF: {pdf_response.text}"}), 500
                else:
                    return jsonify({"error": "Błąd pobierania DOCX z ConvertAPI"}), 500
            else:
                return jsonify({"error": f"Błąd konwersji HTML do DOCX: {docx_response.text}"}), 500
                
        finally:
            # Usuń tymczasowe pliki w przypadku błędu
            try:
                os.unlink(html_path)
            except Exception:
                pass
        
    except Exception as e:
        return jsonify({"error": f"Błąd przygotowania pliku PDF: {str(e)}"}), 500

@app.route('/download-doc', methods=['POST'])
def download_doc():
    """Endpoint do pobierania listu w formacie DOC używając ConvertAPI"""
    try:
        data = request.get_json()
        html_content = data.get('html_content', '')
        filename = data.get('filename', 'list_komornika.docx')
        
        if not html_content:
            return jsonify({"error": "Brak treści HTML"}), 400
        
        # HTML zoptymalizowany pod konwersję do DOCX
        optimized_html = f"""
        <!DOCTYPE html>
        <html lang="pl">
        <head>
            <meta charset="UTF-8">
            <title>List do Komornika</title>
            <style>
                body {{
                    font-family: "Times New Roman", serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20mm;
                    background: white;
                    color: black;
                }}
                .wrapper {{
                    max-width: 180mm;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                {html_content}
            </div>
        </body>
        </html>
        """
        
        # Zapisz HTML do tymczasowego pliku
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp_html:
            tmp_html.write(optimized_html)
            html_path = tmp_html.name
        
        try:
            # Wywołaj ConvertAPI
            with open(html_path, 'rb') as html_file:
                response = requests.post(
                    'https://v2.convertapi.com/convert/html/to/docx',
                    headers={
                        'Authorization': 'Bearer GApx2nuOlCaqNCEhn8uY8KiS0RB0FeE6'
                    },
                    files={
                        'File': html_file
                    },
                    data={
                        'StoreFile': 'true'
                    }
                )
            
            if response.status_code == 200:
                result = response.json()
                docx_url = result['Files'][0]['Url']
                
                # Pobierz DOCX z URL
                docx_response = requests.get(docx_url)
                if docx_response.status_code == 200:
                    # Zapisz DOCX do tymczasowego pliku
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_docx:
                        tmp_docx.write(docx_response.content)
                        docx_path = tmp_docx.name
                    
                    response = send_file(
                        docx_path,
                        as_attachment=True,
                        download_name=filename,
                        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    )
                    
                    def remove_files(response):
                        try:
                            os.unlink(html_path)
                            os.unlink(docx_path)
                        except Exception:
                            pass
                        return response
                    
                    response.call_on_close(remove_files)
                    return response
                else:
                    return jsonify({"error": "Błąd pobierania DOCX z ConvertAPI"}), 500
            else:
                return jsonify({"error": f"Błąd ConvertAPI: {response.text}"}), 500
                
        finally:
            # Usuń tymczasowy plik HTML w przypadku błędu
            try:
                os.unlink(html_path)
            except Exception:
                pass
        
    except Exception as e:
        return jsonify({"error": f"Błąd przygotowania pliku DOC: {str(e)}"}), 500

@app.route('/api/employee/<pesel>', methods=['GET'])
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
            return jsonify({"found": False, "message": "Pracownik nie został znaleziony w bazie danych"})
    
    except Exception as e:
        return jsonify({"error": f"Błąd wyszukiwania pracownika: {str(e)}"}), 500

@app.route('/api/bailiffs', methods=['GET'])
def get_all_bailiffs():
    """Endpoint do pobierania listy wszystkich komorników"""
    try:
        bailiffs = db.get_all_bailiffs()
        return jsonify({"bailiffs": bailiffs})
    
    except Exception as e:
        return jsonify({"error": f"Błąd pobierania komorników: {str(e)}"}), 500

@app.route('/api/proceedings/<pesel>', methods=['GET'])
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
def initialize_database():
    """Endpoint do inicjalizacji bazy danych z danymi testowymi"""
    try:
        db.populate_test_data()
        return jsonify({"message": "Baza danych została zainicjalizowana pomyślnie", "success": True})
    
    except Exception as e:
        return jsonify({"error": f"Błąd inicjalizacji bazy danych: {str(e)}"}), 500

@app.route('/api/auto-detect-scenario', methods=['POST'])
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
