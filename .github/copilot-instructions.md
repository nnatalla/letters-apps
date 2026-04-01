# Kontekst projektu

Uniwersalna aplikacja Flask do przetwarzania dowolnych pism urzędowych, 
komorniczych, szkolnych, prywatnych i innych (OCR + AI).

## Stack
- Backend: Flask + SQLite (docelowo PostgreSQL przez SQLAlchemy)
- AI: Groq API (llama-3.3-70b-versatile) przez requests
- OCR: Tesseract + pdf2image  
- Frontend: vanilla JS, jeden plik index.html
- Auth: flask-login (planowane)

## Architektura
- classifier.py — klasyfikuje typ pisma (5 kategorii + wolny subtype)
- field_extractor.py — dynamicznie wyciąga pola zależnie od typu pisma
- letter_generator.py — generuje list odpowiedź dopasowany do typu
- orchestrator.py — łączy classifier → extractor → generator
- app.py — Flask API
- database.py — obecny manager bazy (do zastąpienia przez SQLAlchemy)

## Typy pism (klasyfikacja)
- INSTYTUCJA_PUBLICZNA: komornik, sąd, ZUS, US, szkoła, uczelnia, policja...
- FIRMA_PRYWATNA: bank, windykacja, ubezpieczalnia, kontrahent...
- OSOBA_PRYWATNA: znajomy, rodzina, osoba fizyczna
- WEWNETRZNE: HR, zarząd, między działami
- INNE: nierozpoznane

## Dwie ścieżki przetwarzania
1. Pisma komornicze (is_komornicze=true):
   - stary format danych zachowany dla kompatybilności
   - 4 scenariusze: nie pracuje / błędne pismo / zajęcie / zbieg komorniczy
   - specjalna logika zbieg komorniczy (wiele listów)
2. Pozostałe pisma (tryb universal):
   - dynamiczne pola generowane przez AI
   - jeden list odpowiedź

## Zasady przy modyfikacjach
- NIGDY nie zmieniaj istniejącej logiki komorniczej
- Nie usuwaj istniejących endpointów, tylko rozszerzaj
- Nowe endpointy zawsze z @login_required (gdy auth będzie gotowe)
- Obsługa błędów try/except na każdym endpoincie
- Komentarze i komunikaty błędów po polsku
- Przy zmianach w index.html zachowaj istniejący styl CSS (gradient niebieski)