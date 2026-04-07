import os
import requests
import json
import re
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


def _normalize_sender_address_lines(sender: dict, fallback_city: str):
  raw_address = (sender.get('adres', '') or sender.get('ulica', '') or '').strip()
  raw_postal = (sender.get('kod_pocztowy', '') or sender.get('kod', '') or '').strip()
  raw_city = (sender.get('miasto', '') or fallback_city or '').strip()
  postal_re = re.compile(r'\b\d{2}-\d{3}\b')

  parts = [p.strip() for p in raw_address.replace('\n', ',').split(',') if p.strip()]

  postal_city_from_parts = ''
  street_from_parts = ''

  for part in parts:
    if postal_re.search(part) and not postal_city_from_parts:
      postal_city_from_parts = part
      continue
    if not street_from_parts:
      street_from_parts = part

  street = street_from_parts or raw_address
  if postal_re.search(street):
    street = ''

  if raw_postal:
    postal_city = f"{raw_postal} {raw_city}".strip()
  else:
    postal_city = postal_city_from_parts

  if postal_city and raw_city:
    normalized_city = raw_city.lower()
    if normalized_city not in postal_city.lower():
      # Jeżeli OCR rozdzielił kod i miasto, dopnij miasto do linii kodu.
      if postal_re.search(postal_city):
        postal_city = f"{postal_city} {raw_city}".strip()

  if not postal_city and raw_city:
    postal_city = raw_city

  if not raw_city and postal_city:
    city_without_postal = postal_re.sub('', postal_city).strip(', ').strip()
    raw_city = city_without_postal or fallback_city

  return street.strip(), postal_city.strip(), (raw_city or fallback_city).strip()


def generate_universal_letter(category: str, subtype: str, extracted_fields: list,
                               company_name: str, city: str = "Łódź",
                               scenario: str = None,
                               user_instructions: str = "",
                               sender: dict = None) -> str:
    """Generuje list odpowiedź dla dowolnego typu pisma, używając szablonu A4 (identyczny układ jak komornicze)."""
    context = get_context(category, subtype)
    today = get_current_date()

    fields_text = ""
    for field in extracted_fields:
        if field.get('value'):
            fields_text += f"- {field['label']}: {field['value']}\n"

    scenario_text = f"\nScenariusz odpowiedzi: {scenario}" if scenario else ""
    instructions_text = f"\n\nDodatkowe instrukcje (OBOWIĄZKOWE do uwzględnienia):\n{user_instructions}" if user_instructions and user_instructions.strip() else ""

    prompt = f"""Wygeneruj list odpowiedź po polsku. Zwróć WYŁĄCZNIE poprawny JSON (bez markdown, bez komentarzy, bez ```).

Nadawca: {company_name}, miasto: {city}
Typ pisma: {subtype} ({category})
Kontekst: {context}{scenario_text}

Dane z pisma:
{fields_text}{instructions_text}

Zwróć JSON o dokładnie tej strukturze:
{{
  "recipient_lines": ["linia1 adresata", "linia2", "linia3 ulica", "kod i miasto"],
  "title": "TYTUŁ PISMA WIELKIMI LITERAMI",
  "body_paragraphs": ["Szanowna Pani / Szanowny Panie,", "Treść akapitu...", "Kolejny akapit..."],
  "closing": "Z poważaniem,"
}}

Zasady:
- recipient_lines: dane adresata (instytucja, osoba, ulica, kod miasto) — bez HTML, bez tagów
- title: krótki tytuł pisma, WIELKIE LITERY, bez tagów HTML
- body_paragraphs: każdy akapit to osobny element tablicy, BEZ tagów HTML
- closing: zwrot kończący"""

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.05
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    response.raise_for_status()
    raw = response.json()['choices'][0]['message']['content'].strip()

    # Usuń ewentualne bloki ```json ... ```
    if '```' in raw:
        parts_split = raw.split('```')
        for chunk in parts_split:
            chunk = chunk.strip()
            if chunk.startswith('json'):
                chunk = chunk[4:].strip()
            if chunk.startswith('{'):
                raw = chunk
                break

    letter_parts = json.loads(raw)

    # Dane nadawcy z obiektu sender (jeśli przekazano)
    if sender:
        s_street, s_postal_city, sender_city_name = _normalize_sender_address_lines(sender, city)
        s_contact = " / ".join(filter(None, [sender.get('telefon', ''), sender.get('email', '')]))
        s_city = sender_city_name
    else:
        s_street = "ul. Przykładowa 1"
        s_postal_city = city
        s_contact = "tel: 123456789"
        s_city = city

    sender_lines = [line for line in [s_street, s_postal_city] if line]
    sender_address_html = "<br>\n      ".join(sender_lines)

    recipient_lines = letter_parts.get('recipient_lines', ['Adresat'])
    recipient_html = ""
    for i, line in enumerate(recipient_lines):
        line = line.replace('<', '&lt;').replace('>', '&gt;')
        if i == 0:
            recipient_html += f"<strong>{line}</strong><br>\n      "
        else:
            recipient_html += f"{line}<br>\n      "

    body_html = "\n".join(
        f"      <p>{p.replace('<', '&lt;').replace('>', '&gt;')}</p>"
        for p in letter_parts.get('body_paragraphs', [])
    )

    title = letter_parts.get('title', subtype.upper()).replace('<', '&lt;').replace('>', '&gt;')
    closing = letter_parts.get('closing', 'Z poważaniem,').replace('<', '&lt;').replace('>', '&gt;')

    return f"""<style>
  .a4-frame {{
    background: #e8e8e8;
    padding: 20px;
    display: flex;
    justify-content: center;
    font-size: 13px;
  }}
  .wrapper {{
    width: 210mm;
    min-height: 297mm;
    background: white;
    padding: 2cm 2.5cm;
    box-sizing: border-box;
    font-family: "Times New Roman", serif;
    line-height: 1.6;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }}
  .date {{ text-align: right; margin-bottom: 30px; }}
  .sender {{ margin-bottom: 0; color: #000 !important; }}
  .recipient {{ text-align: right; color: #000 !important; }}
  .sender *, .recipient * {{ color: #000 !important; }}
  .spacer {{ flex: 1; }}
  .title {{
    text-align: center;
    font-weight: bold;
    text-transform: uppercase;
    margin-bottom: 30px;
  }}
  .content {{ text-align: justify; }}
  .content p {{ margin: 0 0 12px; }}
  .closing {{ margin-top: 30px; }}
  .signature {{ margin-top: 50px; font-weight: bold; }}
  .bottom-spacer {{ flex: 1; }}
</style>
<div class="a4-frame">
  <div class="wrapper">
    <div class="date">{s_city}, dnia {today} r.</div>
    <div class="sender">
      <strong>{company_name}</strong><br>
      {sender_address_html}<br>
      {s_contact}
    </div>
    <div style="flex: 1.5"></div>
    <div class="recipient">
      {recipient_html}
    </div>
    <div style="flex: 1.5"></div>
    <div class="title">{title}</div>
    <div class="content">
{body_html}
    </div>
    <div class="closing">{closing}</div>
    <div class="signature">
      ...............................................<br>
      [Podpis nadawcy]
    </div>
    <div class="bottom-spacer"></div>
  </div>
</div>"""