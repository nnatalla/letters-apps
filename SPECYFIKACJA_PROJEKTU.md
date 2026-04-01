# Specyfikacja Projektu: System Obsługi Pism Komorniczych - Avalon

## 📋 Informacje Ogólne

**Nazwa projektu:** System Obsługi Pism Komorniczych  
**Wersja:** 1.0  
**Data utworzenia:** 2025  
**Firma:** Avalon (Avalon Logistics • Avalon Cars • Avalon Taxi)  
**Typ aplikacji:** Aplikacja webowa (Flask + HTML/CSS/JavaScript)  

---

## 🎯 Cel Projektu

System służy do automatycznego przetwarzania pism komorniczych dla firm grupy Avalon. Aplikacja umożliwia:
- Automatyczne rozpoznawanie tekstu z dokumentów (OCR)
- Inteligentne generowanie odpowiedzi na pisma komornicze
- Obsługę różnych scenariuszy prawnych
- Profesjonalne eksportowanie dokumentów w formatach DOC i PDF

---

## 🏗️ Architektura Systemu

### Backend
- **Framework:** Flask (Python)
- **Baza danych:** SQLite z trzema tabelami (komornicy, pracownicy, postępowania)
- **OCR:** Tesseract-OCR + pytesseract
- **AI:** Groq API (generowanie listów)
- **Konwersja dokumentów:** ConvertAPI (HTML→DOCX→PDF)
- **Przetwarzanie obrazów:** Pillow (PIL)
- **Obsługa PDF:** pdf2image

### Frontend
- **Technologie:** HTML5, CSS3, JavaScript (ES6+)
- **Design:** Responsive design z niebiesko-granatową kolorystyką
- **UI/UX:** Wizard wielokrokowy, modalne okna dialogowe

### Pliki statyczne
- **Logo:** `/static/logo.png` (okrągłe, 100px)
- **Struktura:** Profesjonalna organizacja plików

---

## 🔧 Funkcjonalności

### 1. Upload i Przetwarzanie Dokumentów
- **Obsługiwane formaty:** PDF, JPG, JPEG, PNG
- **Maksymalny rozmiar:** 10MB
- **Wielostronicowe PDF:** Obsługa do 5 stron (zabezpieczenie wydajności)
- **Metody uploadu:** Drag & drop, kliknięcie
- **OCR:** Automatyczne rozpoznawanie tekstu z dokumentów
- **Poppler:** Konwersja PDF→obrazy dla OCR

### 2. Rozpoznawanie Danych
Automatyczne wyciąganie informacji:
- **Komornik:** Imię, nazwisko, adres, miasto, kontakt
- **Dłużnik:** Imię, nazwisko, PESEL
- **Sprawa:** Sygnatura sprawy, numer rachunku bankowego
- **Funkcje:** Kopiowanie do schowka, edycja danych
- **🆕 Integracja z bazą:** Automatyczne wyszukiwanie pracownika po PESEL
- **🆕 Uzupełnianie danych:** Auto-fill brakujących informacji z bazy pracowników

### 3. Weryfikacja Statusu
Cztery scenariusze obsługi:
1. **Osoba NIE PRACUJE** - z datą zakończenia współpracy
2. **Błędne pismo** - wynagrodzenie zamiast zajęcia
3. **Prawidłowe zajęcie** - z rodzajem umowy (zlecenie/najem pojazdu)
4. **Zbieg komorniczy** - wielokomornikowy formularz

**🆕 Automatyczne wykrywanie scenariusza:**
- **Analiza bazy pracowników:** Status zatrudnienia, typ umowy
- **Detekcja zbiegów:** Automatyczne wykrywanie istniejących postępowań
- **Inteligentne sugestie:** Proponowany scenariusz na podstawie danych

### 4. Zbieg Komorniczy (Funkcjonalność Premium)
- **🆕 Baza danych komorników:** 25+ komorników z pełnymi danymi
- **🆕 Automatyczna detekcja:** System sam wykrywa istniejące postępowania
- **Modal wyboru:** Intuicyjny interfejs selekcji z bazy danych
- **Automatyczne uzupełnianie:** Dane komorników z bazy
- **🆕 Preload istniejących:** Auto-ładowanie aktywnych postępowań
- **Wielokrotne listy:** Osobny dokument dla każdego komornika
- **Nawigacja:** Strzałki klawiatury, przyciski poprzedni/następny

### 5. Generowanie Dokumentów
- **AI-powered:** Inteligentne tworzenie treści przez Groq
- **Personalizacja:** Dostosowanie do konkretnej sytuacji prawnej
- **Formatowanie:** Profesjonalne układy dokumentów
- **Status indicator:** "Generuję..." podczas przetwarzania

### 6. Export i Pobieranie
- **Formaty:** DOC (edytowalny) i PDF (gotowy do druku)
- **ConvertAPI:** Profesjonalna konwersja HTML→DOCX→PDF
- **Opcje pobierania:**
  - Pojedyncze dokumenty
  - Wszystkie dokumenty naraz
  - Masowe pobieranie w wybranym formacie

---

## 🎨 Design i UX

### Kolorystyka
- **Podstawowe:** Odcienie niebieskiego i granatowego (#1e3c72, #2a5298)
- **Akcenty:** Białe tło, przezroczyste elementy
- **Status:** Zielone powiadomienia sukcesu

### Elementy UI
- **Logo:** Okrągłe, 100px, z cieniem i ramką
- **Przyciski:** Gradientowe, hover effects
- **Progress bar:** Wizualny wskaźnik postępu
- **Modalne okna:** Nowoczesne dialogi wyboru
- **Responsive:** Dostosowanie do różnych urządzeń

### Interakcje
- **Copy-to-clipboard:** Kliknięcie w pole = kopiowanie
- **Keyboard navigation:** Strzałki do nawigacji między listami
- **Drag & drop:** Intuicyjny upload plików
- **Auto-fill:** Automatyczne uzupełnianie formularzy

---

## 📊 Przepływ Pracy (Workflow)

### Krok 1: Upload Dokumentu
1. Wybór spółki (Avalon Logistics/Cars/Taxi)
2. Upload pliku (PDF/JPG)
3. Automatyczne przetwarzanie OCR

### Krok 2: Weryfikacja Danych
1. Wyświetlenie rozpoznanych danych
2. Możliwość kopiowania i edycji
3. Sprawdzenie poprawności informacji

### Krok 3: Wybór Scenariusza
1. Wybór jednej z 4 opcji weryfikacji
2. Uzupełnienie dodatkowych danych (jeśli wymagane)
3. Specjalna obsługa zbiegu komorniczego

### Krok 4: Generowanie i Pobieranie
1. AI generuje odpowiednie dokumenty
2. Podgląd wygenerowanych listów
3. Export w formatach DOC/PDF

---

## 🔗 Integracje

### Zewnętrzne API
1. **Groq API** - generowanie treści AI
2. **ConvertAPI** - konwersja dokumentów (HTML→DOCX→PDF)
3. **Tesseract-OCR** - rozpoznawanie tekstu z obrazów

### Klucze API (wymagane)
- `GROQ_API_KEY` - dostęp do modeli językowych
- `CONVERTAPI_SECRET` - konwersja dokumentów

---

## 📁 Struktura Projektu

```
avalon_test/
├── app.py                      # Główna aplikacja Flask
├── index.html                  # Interfejs użytkownika
├── static/
│   └── logo.png               # Logo firmy (100px, okrągłe)
├── temp_uploads/              # Tymczasowe przesyłane pliki
├── __pycache__/               # Cache Pythona
├── .env                       # Zmienne środowiskowe (klucze API)
├── .venv/                     # Wirtualne środowisko Python
└── SPECYFIKACJA_PROJEKTU.md   # Ten dokument
```

---

## 💻 Wymagania Techniczne

### Serwer
- **Python:** 3.8+
- **System:** Windows/Linux/macOS
- **RAM:** 2GB minimum, 4GB zalecane
- **Dysk:** 1GB wolnego miejsca

### Zależności Python
```
flask
requests
groq
pillow
pytesseract
pdf2image
python-dotenv
```

### Dodatkowe oprogramowanie
- **Tesseract-OCR:** C:/Program Files/Tesseract-OCR/tesseract.exe
- **Poppler:** C:\Poppler\poppler-23.01.0\Library\bin (konwersja PDF)
- **Poppler wymogi:** Wymagany dla wielostronicowych dokumentów PDF

### Przeglądarki
- **Zalecane:** Chrome 90+, Firefox 90+, Safari 14+, Edge 90+
- **Funkcje:** JavaScript ES6+, File API, Clipboard API

---

## 🚀 Instalacja i Uruchomienie

### 1. Klonowanie projektu
```bash
git clone [repository_url]
cd avalon_test
```

### 2. Środowisko wirtualne
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### 3. Instalacja zależności
```bash
pip install flask requests groq pillow pytesseract pdf2image python-dotenv
```

### 4. Konfiguracja
- Utwórz plik `.env` z kluczami API
- Zainstaluj Tesseract-OCR
- Sprawdź ścieżkę do tesseract.exe w app.py

### 5. Uruchomienie
```bash
python app.py
```
Aplikacja dostępna pod: http://localhost:5000

---

## 🔒 Bezpieczeństwo

### Dane wrażliwe
- Klucze API przechowywane w `.env`
- Tymczasowe pliki w `temp_uploads/`
- Brak trwałego przechowywania danych osobowych

### Walidacja
- Ograniczenia rozmiaru plików (10MB)
- Sprawdzanie typów MIME
- Sanityzacja nazw plików

---

## 📈 Możliwości Rozwoju

### Planowane ulepszenia
1. **Baza danych:** Przechowywanie historii spraw
2. **Autentykacja:** System logowania użytkowników
3. **Kolejka zadań:** Przetwarzanie w tle
4. **API REST:** Integracja z innymi systemami
5. **Backup:** Automatyczne kopie zapasowe
6. **Monitoring:** Logi i metryki wydajności

### Skalowanie
- **Docker:** Konteneryzacja aplikacji
- **Load balancer:** Obsługa większego ruchu
- **Cloud deployment:** AWS/Azure/GCP
- **CDN:** Szybsze ładowanie plików statycznych

---

## 📞 Wsparcie Techniczne

### Rozwiązywanie problemów
1. **OCR nie działa:** Sprawdź instalację Tesseract-OCR
2. **Błąd API:** Zweryfikuj klucze w `.env`
3. **Błędy konwersji:** Sprawdź połączenie z ConvertAPI
4. **Logo nie ładuje się:** Sprawdź ścieżkę `/static/logo.png`

### Kontakt
- **Dokumentacja:** Ten plik specyfikacji
- **Logi:** Sprawdź konsolę Flask dla debugowania
- **GitHub Issues:** [jeśli projekt na GitHub]

---

## 📝 Changelog

### v1.0 (Aktualna)
- ✅ Pełny przepływ przetwarzania dokumentów
- ✅ Integracja z Groq AI
- ✅ Export do DOC/PDF via ConvertAPI
- ✅ Zbieg komorniczy z bazą 20 komorników
- ✅ Responsive design w odcieniach niebieskiego
- ✅ Logo 100px w folderze static/
- ✅ Radio buttons dla rodzaju umowy
- ✅ Enhanced copy functionality
- ✅ Status indicator "Generuję..."

---

**© 2025 Avalon Group - System Obsługi Pism Komorniczych**  
*Dokumentacja wygenerowana automatycznie na podstawie analizy kodu źródłowego*
