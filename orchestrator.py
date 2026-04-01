from classifier import classify_document
from field_extractor import extract_fields_komornicze, extract_fields_universal

def process_document(ocr_text: str) -> dict:
    """
    Główna funkcja orkiestracji.
    Zwraca słownik z klasyfikacją, polami i metadanymi potrzebnymi frontendowi.
    """
    # Krok 1: Klasyfikacja
    classification = classify_document(ocr_text)
    is_komornicze = classification.get('is_komornicze', False)

    if is_komornicze:
        # Stara ścieżka - zachowanie pełnej kompatybilności wstecznej
        extracted = extract_fields_komornicze(ocr_text)
        return {
            "mode": "komornicze",
            "classification": classification,
            "dane": extracted,           # stary format - używany przez stare endpointy
            "fields": None,              # nie używane w trybie komorniczym
        }
    else:
        # Nowa ścieżka - dynamiczne pola
        category = classification.get('category', 'INNE')
        subtype = classification.get('subtype', 'nieznane')
        extracted = extract_fields_universal(ocr_text, category, subtype)
        return {
            "mode": "universal",
            "classification": classification,
            "dane": None,                # nie używane w trybie uniwersalnym
            "fields": extracted.get('fields', []),
            "summary": extracted.get('summary', ''),
            "suggested_response_type": extracted.get('suggested_response_type', 'informacja'),
        }