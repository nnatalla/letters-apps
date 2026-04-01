import os
import requests
import json

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Dla pism komorniczych - zachowujemy dokładnie stare pola (kompatybilność wsteczna)
KOMORNICZE_PROMPT = """Wyciągnij dane z pisma komorniczego. Zwróć TYLKO JSON:
{
  "komornik": {
    "imieNazwisko": "imię i nazwisko komornika lub null",
    "adres": "adres bez kodu i miasta lub null",
    "miasto": "kod pocztowy i miasto lub null",
    "telefon": "telefon lub null",
    "email": "email lub null",
    "plec": "M lub K na podstawie imienia"
  },
  "dluznik": {
    "imieNazwisko": "imię i nazwisko dłużnika lub null",
    "pesel": "PESEL dłużnika lub null"
  },
  "sprawa": {
    "sygnaturaSprawy": "sygnatura sprawy lub null",
    "numerRachunku": "numer rachunku bankowego lub null"
  }
}"""

# Dla pozostałych typów - AI samo decyduje jakie pola wyciągnąć
UNIVERSAL_PROMPT = """Wyciągnij z pisma WSZYSTKIE istotne informacje.
Typ pisma: {category} / {subtype}

Zwróć TYLKO JSON w formacie:
{{
  "fields": [
    {{
      "id": "unikalny_klucz_bez_spacji",
      "label": "Czytelna nazwa pola po polsku",
      "value": "wartość lub null",
      "required": true,
      "type": "osoba|data|adres|numer|kwota|tekst"
    }}
  ],
  "summary": "Krótkie podsumowanie pisma w 2 zdaniach",
  "suggested_response_type": "odmowa|potwierdzenie|wyjaśnienie|informacja|prośba_o_dane"
}}

Zawsze uwzględnij pola: nadawca, adres nadawcy, temat, termin odpowiedzi (jeśli jest).
Dodaj wszystkie inne pola które są istotne dla odpowiedzi na to pismo."""


def extract_fields_komornicze(ocr_text: str) -> dict:
    """Ekstrakcja pól dla pism komorniczych - zachowanie starego formatu."""
    prompt = f"{KOMORNICZE_PROMPT}\n\nPismo:\n---\n{ocr_text[:3000]}\n---"

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    response.raise_for_status()
    raw = response.json()['choices'][0]['message']['content']
    raw = raw.strip().strip('`').strip()
    if raw.startswith('json'):
        raw = raw[4:].strip()
    return json.loads(raw)


def extract_fields_universal(ocr_text: str, category: str, subtype: str) -> dict:
    """Ekstrakcja pól dla dowolnego pisma - AI samo decyduje o polach."""
    prompt_header = UNIVERSAL_PROMPT.format(category=category, subtype=subtype)
    prompt = f"{prompt_header}\n\nPismo:\n---\n{ocr_text[:3000]}\n---"

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    response.raise_for_status()
    raw = response.json()['choices'][0]['message']['content']
    raw = raw.strip().strip('`').strip()
    if raw.startswith('json'):
        raw = raw[4:].strip()
    return json.loads(raw)