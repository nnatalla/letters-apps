import os
import requests
import json

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

CATEGORIES = {
    "INSTYTUCJA_PUBLICZNA": "komornik, sąd, urząd (ZUS, US, MOPS, urząd gminy, starostwo), szkoła, uczelnia, policja, prokuratura, NFZ, szpital publiczny",
    "FIRMA_PRYWATNA": "bank, firma windykacyjna, ubezpieczalnia, operator telefoniczny, kontrahent biznesowy, pracodawca prywatny",
    "OSOBA_PRYWATNA": "osoba fizyczna, znajomy, rodzina, sąsiad, anonimowy nadawca",
    "WEWNETRZNE": "pismo wewnętrzne firmy, HR, zarząd, między działami",
    "INNE": "pismo nieprzypadające do żadnej z powyższych kategorii"
}

def classify_document(ocr_text: str) -> dict:
    categories_desc = "\n".join([f"- {k}: {v}" for k, v in CATEGORIES.items()])

    prompt = f"""Przeanalizuj poniższe pismo i zwróć TYLKO JSON (bez żadnego innego tekstu).

Dostępne kategorie:
{categories_desc}

Pismo:
---
{ocr_text[:3000]}
---

Zwróć dokładnie ten format JSON:
{{
  "category": "jedna z 5 kategorii z listy powyżej",
  "subtype": "własny opis podtypu np. komornik sądowy / urząd skarbowy / uczelnia wyższa / bank komercyjny",
  "confidence": 0.95,
  "is_komornicze": true,
  "detected_entities": {{
    "nadawca": "nazwa nadawcy lub null",
    "odbiorca": "nazwa odbiorcy lub null",
    "temat": "temat pisma w 1 zdaniu",
    "pilnosc": "wysoka lub srednia lub niska",
    "termin": "termin odpowiedzi jeśli jest lub null"
  }}
}}

Pole "is_komornicze" ustaw na true TYLKO jeśli to pismo od komornika sądowego."""

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