import os
import requests
import json
from datetime import datetime

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

RESPONSE_CONTEXTS = {
    "INSTYTUCJA_PUBLICZNA": {
        "default": "Piszesz oficjalną odpowiedź w imieniu spółki na pismo instytucji publicznej. Ton: formalny, uprzejmy, rzeczowy.",
        "komornik sądowy": "Piszesz odpowiedź prawną w imieniu spółki na pismo komornicze. Ton: bardzo formalny, prawniczy, precyzyjny.",
        "urząd skarbowy": "Piszesz odpowiedź w imieniu spółki do urzędu skarbowego. Ton: formalny, zgodny z przepisami.",
        "szkoła": "Piszesz odpowiedź w imieniu spółki/rodzica do szkoły. Ton: uprzejmy, współpracujący.",
        "uczelnia wyższa": "Piszesz odpowiedź do uczelni. Ton: formalny akademicki.",
        "sąd": "Piszesz pismo procesowe lub odpowiedź do sądu. Ton: bardzo formalny, prawniczy."
    },
    "FIRMA_PRYWATNA": "Piszesz odpowiedź biznesową w imieniu spółki. Ton: profesjonalny, konkretny.",
    "OSOBA_PRYWATNA": "Piszesz odpowiedź na pismo osoby prywatnej. Ton: uprzejmy, bezpośredni, ludzki.",
    "WEWNETRZNE": "Piszesz odpowiedź na pismo wewnętrzne. Ton: profesjonalny, rzeczowy.",
    "INNE": "Piszesz odpowiedź na pismo. Ton: neutralny, uprzejmy."
}


def get_context(category: str, subtype: str) -> str:
    ctx = RESPONSE_CONTEXTS.get(category, RESPONSE_CONTEXTS["INNE"])
    if isinstance(ctx, dict):
        # Sprawdź czy subtype pasuje do któregoś klucza (case insensitive)
        for key, value in ctx.items():
            if key.lower() in subtype.lower() or subtype.lower() in key.lower():
                return value
        return ctx.get("default", RESPONSE_CONTEXTS["INNE"])
    return ctx


def get_current_date():
    return datetime.now().strftime('%d.%m.%Y')


def generate_universal_letter(category: str, subtype: str, extracted_fields: list,
                               company_name: str, city: str = "Łódź",
                               scenario: str = None) -> str:
    """Generuje list odpowiedź dla dowolnego typu pisma."""
    context = get_context(category, subtype)
    today = get_current_date()

    # Buduj opis pól dla AI
    fields_text = ""
    for field in extracted_fields:
        if field.get('value'):
            fields_text += f"- {field['label']}: {field['value']}\n"

    scenario_text = f"\nScenariusz odpowiedzi: {scenario}" if scenario else ""

    prompt = f"""Wygeneruj kompletny, gotowy do wysłania list odpowiedź w języku polskim.

Nadawca (spółka): {company_name}
Miasto nadawcy: {city}
Data: {today}
Typ pisma na które odpowiadamy: {subtype} ({category})
Kontekst: {context}{scenario_text}

Dane wyciągnięte z pisma:
{fields_text}

Wymagania dotyczące formatu listu:
- Nagłówek z danymi nadawcy (spółka, adres: ul. Przykładowa 1, {city}, tel: 123456789)
- Data po prawej stronie: {city}, dnia {today} r.
- Dane adresata po prawej stronie
- Tytuł pisma (wielkimi literami, wycentrowany)
- Treść listu (zwrot grzecznościowy + treść + zakończenie)
- Podpis

Wygeneruj TYLKO treść listu w formacie HTML (bez DOCTYPE, bez <html>, <head>, <body>).
Użyj inline CSS. Styl: Times New Roman, font-size 12pt, marginesy.
Nie dodawaj żadnych komentarzy ani wyjaśnień."""

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']