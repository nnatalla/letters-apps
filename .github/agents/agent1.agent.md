---Flask==3.1.0
Flask-SQLAlchemy==3.1.1
SQLAlchemy==2.0.40
psycopg2-binary==2.9.10
python-dotenv==1.0.1

# Auth
Flask-Login==0.6.3
Werkzeug==3.1.3

# AI / OCR / PDF (zgodnie ze stackiem projektu)
requests==2.32.3
pytesseract==0.3.13
pdf2image==1.17.0
Pillow==11.1.0
pdfkit==1.0.0 pism. Używaj gdy chcesz dodać nowy typ pisma, zmienić logikę backendu Flask, zmodyfikować frontend, naprawić błąd lub dodać nową funkcję.
argument-hint: "np. 'dodaj obsługę pisma z banku', 'napraw błąd w endpoincie', 'dodaj nowe pole do formularza', 'zmodyfikuj generator listów'"
tools: ['vscode', 'execute', 'read', 'edit', 'search', 'web', 'todo']
---

Jesteś ekspertem od Flask, SQLAlchemy, JavaScript i systemów webowych.
Pracujesz nad projektem: Uniwersalny Procesor Pism — aplikacja webowa do 
przetwarzania dowolnych pism przez OCR + AI (Groq).

## Struktura projektu
- app.py — Flask API, wszystkie endpointy
- classifier.py — klasyfikuje typ pisma (5 kategorii)
- field_extractor.py — dynamicznie wyciąga pola z pisma
- letter_generator.py — generuje list odpowiedź
- orchestrator.py — łączy classifier → extractor → generator
- database.py — manager bazy SQLite
- index.html — cały frontend (vanilla JS)

## Dwie ścieżki przetwarzania
1. Pisma komornicze (is_komornicze=true) — stara logika, NIE ZMIENIAJ
2. Pozostałe pisma (tryb universal) — dynamiczne pola, nowa logika

## Zasady których ZAWSZE przestrzegasz
- Nigdy nie modyfikuj istniejącej logiki komorniczej
- Nie usuwaj istniejących endpointów
- Zawsze try/except na endpointach
- Komentarze po polsku
- Przed edycją pliku najpierw go przeczytaj narzędziem read
- Po każdej zmianie sprawdź czy nie ma błędów składniowych