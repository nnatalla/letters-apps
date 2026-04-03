import re
from dataclasses import dataclass, field
from typing import Any, Optional
from .document_classifier import ClassificationResult, DocumentCategory


@dataclass
class ExtractedDocument:
    """Uniwersalna struktura danych dla każdego pisma"""
    
    # Pola wspólne dla WSZYSTKICH pism
    raw_text: str
    classification: ClassificationResult
    
    # Nadawca
    sender_name: Optional[str] = None
    sender_address: Optional[str] = None
    sender_institution: Optional[str] = None
    sender_phone: Optional[str] = None
    sender_email: Optional[str] = None
    
    # Odbiorca
    recipient_name: Optional[str] = None
    recipient_address: Optional[str] = None
    
    # Metadane pisma
    document_date: Optional[str] = None
    document_number: Optional[str] = None
    subject: Optional[str] = None
    deadline: Optional[str] = None
    
    # Pola DYNAMICZNE - różne dla każdego typu
    dynamic_fields: dict[str, Any] = field(default_factory=dict)
    
    # Sugerowana odpowiedź
    suggested_response_tone: str = "formalny"  # formalny | półformalny | nieformalny
    suggested_response_points: list[str] = field(default_factory=list)


class DynamicFieldExtractor:
    """
    Wyciąga pola z dokumentu dynamicznie w zależności od jego typu.
    Każda kategoria ma własny zestaw ekstraktorów.
    """

    def extract(self, text: str, classification: ClassificationResult) -> ExtractedDocument:
        doc = ExtractedDocument(
            raw_text=text,
            classification=classification
        )
        
        # 1. Wyciągnij pola wspólne
        self._extract_common_fields(text, doc)
        
        # 2. Wyciągnij pola specyficzne dla kategorii
        extractor_map = {
            DocumentCategory.KOMORNICZE:     self._extract_komornicze,
            DocumentCategory.URZEDOWE:       self._extract_urzedowe,
            DocumentCategory.SZKOLNE:        self._extract_szkolne,
            DocumentCategory.BANKOWE:        self._extract_bankowe,
            DocumentCategory.PODATKOWE:      self._extract_podatkowe,
            DocumentCategory.MEDYCZNE:       self._extract_medyczne,
            DocumentCategory.PRAWNE:         self._extract_prawne,
            DocumentCategory.PRYWATNE:       self._extract_prywatne,
        }
        
        extractor = extractor_map.get(classification.category)
        if extractor:
            extractor(text, doc)
        
        # 3. Ustaw ton odpowiedzi
        self._set_response_tone(doc)
        
        return doc

    # ─────────────────────────────────────────────
    # POLA WSPÓLNE
    # ─────────────────────────────────────────────

    def _extract_common_fields(self, text: str, doc: ExtractedDocument):
        # Data dokumentu
        date_patterns = [
            r'\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b',
            r'\b(\d{1,2}\s+\w+\s+\d{4})\b',
            r'\b(\d{4}-\d{2}-\d{2})\b'
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                doc.document_date = match.group(1)
                break
        
        # Numer pisma / znak sprawy
        ref_patterns = [
            r'(?:znak sprawy|nr|sygn\.?|ref\.?)[\s:]+([A-Z0-9/\-\.]+)',
            r'(?:KM|Km)\s*/\s*(\d+/\d+)',
            r'sprawa\s+nr\s+([A-Z0-9/\-]+)'
        ]
        for pattern in ref_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doc.document_number = match.group(1)
                break
        
        # Telefon
        phone_match = re.search(
            r'(?:tel\.?|telefon)[\s:]*([+\d\s\-()]{9,15})', text, re.IGNORECASE
        )
        if phone_match:
            doc.sender_phone = phone_match.group(1).strip()
        
        # Email
        email_match = re.search(r'[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}', text)
        if email_match:
            doc.sender_email = email_match.group(0)
        
        # Termin
        deadline_patterns = [
            r'(?:w terminie|do dnia|termin)\s+(\d{1,2}[./]\d{1,2}[./]\d{4})',
            r'(?:w ciągu|niezwłocznie\s+(?:tj\.)?)\s*(\d+\s*(?:dni|tygodni))',
        ]
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doc.deadline = match.group(1)
                break

    # ─────────────────────────────────────────────
    # KOMORNICZE
    # ─────────────────────────────────────────────

    def _extract_komornicze(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Imię i nazwisko komornika
        komornik_match = re.search(
            r'Komornik\s+Sądowy\s+(?:przy\s+\S+\s+)?([A-ZŁÓŚŹĆŃ][a-złóśźćń]+\s+[A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
            text
        )
        fields["komornik_imie_nazwisko"] = komornik_match.group(1) if komornik_match else None
        
        # Kwota zadłużenia
        kwota_match = re.search(
            r'(?:kwota|zadłużenie|dług|należność)[\s:]+(\d[\d\s,.]+)\s*(?:zł|PLN)',
            text, re.IGNORECASE
        )
        fields["kwota_zadluzenia"] = kwota_match.group(1) if kwota_match else None
        
        # Wierzyciel
        wierzyciel_match = re.search(
            r'(?:wierzyciel|na rzecz)[\s:]+([^\n,]+)', text, re.IGNORECASE
        )
        fields["wierzyciel"] = wierzyciel_match.group(1).strip() if wierzyciel_match else None
        
        # Sygnatura KM
        km_match = re.search(r'(?:KM|Km)\s*/?\s*(\d+/\d+)', text)
        fields["sygnatura_km"] = km_match.group(0) if km_match else None
        
        # Tytuł wykonawczy
        tytul_match = re.search(
            r'tytuł\s+wykonawczy[\s:]+([^\n]+)', text, re.IGNORECASE
        )
        fields["tytul_wykonawczy"] = tytul_match.group(1).strip() if tytul_match else None
        
        # Rodzaj zajęcia
        if "wynagrodzenie" in text.lower():
            fields["rodzaj_zajecia"] = "zajęcie wynagrodzenia"
        elif "rachunek" in text.lower():
            fields["rodzaj_zajecia"] = "zajęcie rachunku bankowego"
        elif "nieruchomość" in text.lower():
            fields["rodzaj_zajecia"] = "zajęcie nieruchomości"
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie otrzymania wezwania",
            "Odniesienie do sygnatury sprawy",
            "Wniosek o rozłożenie na raty lub umorzenie",
            "Powołanie się na trudną sytuację materialną (jeśli dotyczy)",
            "Prośba o wstrzymanie egzekucji"
        ]

    # ─────────────────────────────────────────────
    # URZĘDOWE
    # ─────────────────────────────────────────────

    def _extract_urzedowe(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Nazwa urzędu
        urzad_patterns = [
            r'(Urząd\s+\w+(?:\s+\w+)*)',
            r'(Starostwo\s+\w+(?:\s+\w+)*)',
            r'(Ministerstwo\s+\w+(?:\s+\w+)*)',
            r'(Gmina\s+\w+(?:\s+\w+)*)',
        ]
        for pattern in urzad_patterns:
            match = re.search(pattern, text)
            if match:
                fields["nazwa_urzedu"] = match.group(1)
                doc.sender_institution = match.group(1)
                break
        
        # Podstawa prawna
        podstawa_match = re.search(
            r'(?:na podstawie|zgodnie z)[\s:]+([^\n]+)', text, re.IGNORECASE
        )
        fields["podstawa_prawna"] = podstawa_match.group(1).strip() if podstawa_match else None
        
        # Wydział
        wydzial_match = re.search(r'Wydział\s+([^\n,]+)', text, re.IGNORECASE)
        fields["wydzial"] = wydzial_match.group(1).strip() if wydzial_match else None
        
        # Numer decyzji
        decyzja_match = re.search(
            r'(?:decyzja|postanowienie)\s+(?:nr)?\s*([A-Z0-9/\-.]+)',
            text, re.IGNORECASE
        )
        fields["numer_decyzji"] = decyzja_match.group(1) if decyzja_match else None
        
        # Wymagane dokumenty (lista po "należy przedłożyć" itp.)
        docs_match = re.search(
            r'(?:należy przedłożyć|wymagane dokumenty|dołączyć)[\s:]+(.+?)(?:\n\n|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        fields["wymagane_dokumenty"] = docs_match.group(1).strip() if docs_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie odbioru decyzji/wezwania",
            "Odniesienie do numeru decyzji i znaku sprawy",
            "Ustosunkowanie się do meritum sprawy",
            "Wniosek o przedłużenie terminu (jeśli potrzeba)",
            "Odwołanie od decyzji (jeśli dotyczy)"
        ]

    # ─────────────────────────────────────────────
    # SZKOLNE
    # ─────────────────────────────────────────────

    def _extract_szkolne(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Nazwa szkoły
        szkola_match = re.search(
            r'((?:Szkoła\s+(?:Podstawowa|Średnia|Ponadpodstawowa)|Liceum|Technikum|Gimnazjum)\s+[^\n]+)',
            text, re.IGNORECASE
        )
        fields["nazwa_szkoly"] = szkola_match.group(1).strip() if szkola_match else None
        
        # Imię i nazwisko ucznia
        uczen_patterns = [
            r'(?:uczeń|uczennica|dot\.? ucznia?)[\s:]+([A-ZŁÓŚŹĆŃ][a-złóśźćń]+\s+[A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
            r'(?:Pana|Pani)\s+dziecka\s+–\s*([A-ZŁÓŚŹĆŃ][a-złóśźćń]+\s+[A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
        ]
        for pattern in uczen_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fields["imie_ucznia"] = match.group(1)
                break
        
        # Klasa
        klasa_match = re.search(r'klasy?\s+([0-9]+\s*[a-zA-Z]?)', text, re.IGNORECASE)
        fields["klasa"] = klasa_match.group(1) if klasa_match else None
        
        # Wychowawca
        wychowawca_match = re.search(
            r'(?:wychowawc[ay]|nauczyciel[a]?)[\s:]+([A-ZŁÓŚŹĆŃ][a-złóśźćń]+\s+[A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
            text, re.IGNORECASE
        )
        fields["wychowawca"] = wychowawca_match.group(1) if wychowawca_match else None
        
        # Powód pisma
        if "nieobecność" in text.lower() or "absencja" in text.lower():
            fields["powod"] = "nieobecność ucznia"
        elif "zachowanie" in text.lower():
            fields["powod"] = "zachowanie ucznia"
        elif "oceny" in text.lower() or "wyniki" in text.lower():
            fields["powod"] = "wyniki w nauce"
        elif "zebranie" in text.lower():
            fields["powod"] = "zebranie rodziców"
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie zapoznania się z pismem",
            "Ustosunkowanie do opisanej sytuacji",
            "Prośba o spotkanie/wyjaśnienie (jeśli potrzeba)",
            "Deklaracja współpracy ze szkołą",
        ]

    # ─────────────────────────────────────────────
    # BANKOWE
    # ─────────────────────────────────────────────

    def _extract_bankowe(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Nazwa banku
        bank_match = re.search(
            r'((?:Bank|PKO|PKN|mBank|ING|Santander|Pekao|BNP|Alior)\s*\w*(?:\s+\w+)?)',
            text, re.IGNORECASE
        )
        fields["nazwa_banku"] = bank_match.group(1).strip() if bank_match else None
        
        # Numer umowy kredytowej
        umowa_match = re.search(
            r'(?:umowa|nr umowy|numer umowy)[\s:]+([A-Z0-9/\-]+)', text, re.IGNORECASE
        )
        fields["numer_umowy"] = umowa_match.group(1) if umowa_match else None
        
        # Kwota zaległości
        zaleglosc_match = re.search(
            r'(?:zaległość|zadłużenie|do zapłaty)[\s:]+(\d[\d\s,.]+)\s*(?:zł|PLN)',
            text, re.IGNORECASE
        )
        fields["kwota_zaleglosci"] = zaleglosc_match.group(1) if zaleglosc_match else None
        
        # Numer konta do wpłaty
        konto_match = re.search(r'\b(\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4})\b', text)
        fields["numer_konta"] = konto_match.group(1) if konto_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie odbioru pisma",
            "Prośba o restrukturyzację zadłużenia",
            "Wniosek o ugodę",
            "Odniesienie do numeru umowy",
        ]

    # ─────────────────────────────────────────────
    # PODATKOWE
    # ─────────────────────────────────────────────

    def _extract_podatkowe(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Urząd Skarbowy
        us_match = re.search(r'(Urząd Skarbowy\s+\w+(?:\s+\w+)*)', text)
        fields["nazwa_urzedu_skarbowego"] = us_match.group(1) if us_match else None
        
        # NIP
        nip_match = re.search(r'NIP[\s:]+(\d{10}|\d{3}-\d{3}-\d{2}-\d{2})', text)
        fields["nip"] = nip_match.group(1) if nip_match else None
        
        # Rok podatkowy
        rok_match = re.search(r'(?:rok podatkowy|za rok)[\s:]+(\d{4})', text, re.IGNORECASE)
        fields["rok_podatkowy"] = rok_match.group(1) if rok_match else None
        
        # Kwota zaległości/nadpłaty
        kwota_match = re.search(
            r'(?:zaległość|nadpłata|do zapłaty|do zwrotu)[\s:]+(\d[\d\s,.]+)\s*(?:zł|PLN)',
            text, re.IGNORECASE
        )
        fields["kwota"] = kwota_match.group(1) if kwota_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie odbioru pisma z US",
            "Odwołanie od decyzji podatkowej (jeśli dotyczy)",
            "Wniosek o rozłożenie zaległości na raty",
            "Wyjaśnienie rozbieżności w rozliczeniu",
        ]

    # ─────────────────────────────────────────────
    # MEDYCZNE
    # ─────────────────────────────────────────────

    def _extract_medyczne(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        placowka_match = re.search(
            r'((?:Szpital|Przychodnia|Centrum Medyczne|Klinika)\s+[^\n]+)',
            text, re.IGNORECASE
        )
        fields["nazwa_placowki"] = placowka_match.group(1).strip() if placowka_match else None
        
        lekarz_match = re.search(
            r'(?:lekarz prowadzący|dr|lek\.|lekarz)[\s:]+([A-ZŁÓŚŹĆŃ][a-złóśźćń]+\s+[A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
            text, re.IGNORECASE
        )
        fields["lekarz"] = lekarz_match.group(1) if lekarz_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie terminu wizyty",
            "Prośba o zmianę terminu",
            "Pytanie o wyniki badań",
        ]

    # ─────────────────────────────────────────────
    # PRAWNE
    # ─────────────────────────────────────────────

    def _extract_prawne(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        sad_match = re.search(r'(Sąd\s+\w+(?:\s+\w+)*)', text)
        fields["nazwa_sadu"] = sad_match.group(1) if sad_match else None
        
        sygnatura_match = re.search(
            r'(?:sygnatura|sygn\.?|akt)[\s:]+([A-Z0-9\s/]+(?:\s+\d+/\d+)?)',
            text, re.IGNORECASE
        )
        fields["sygnatura_akt"] = sygnatura_match.group(1).strip() if sygnatura_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Potwierdzenie odbioru pisma sądowego",
            "Odpowiedź na pozew",
            "Wniosek o odroczenie terminu rozprawy",
            "Ustosunkowanie do zarzutów",
        ]

    # ─────────────────────────────────────────────
    # PRYWATNE
    # ─────────────────────────────────────────────

    def _extract_prywatne(self, text: str, doc: ExtractedDocument):
        fields = {}
        
        # Imię nadawcy (pierwsze zdanie lub podpis)
        imie_match = re.search(
            r'(?:pozdrawiam|z poważaniem|twój|twoja)[,\s]+([A-ZŁÓŚŹĆŃ][a-złóśźćń]+)',
            text, re.IGNORECASE
        )
        fields["imie_nadawcy"] = imie_match.group(1) if imie_match else None
        
        # Ton pisma
        if any(w in text.lower() for w in ["cześć", "hej", "witaj"]):
            fields["ton"] = "nieformalny"
        else:
            fields["ton"] = "półformalny"
        
        # Temat/prośba
        prosba_match = re.search(
            r'(?:proszę cię|chciałem|chciałam|czy mógłbyś|czy mogłabyś)[\s,]+([^\n.]+)',
            text, re.IGNORECASE
        )
        fields["prosba"] = prosba_match.group(1).strip() if prosba_match else None
        
        doc.dynamic_fields = fields
        doc.suggested_response_points = [
            "Odpowiedź na prośbę/pytanie",
            "Ustosunkowanie się do sprawy",
            "Propozycja rozwiązania",
        ]

    def _set_response_tone(self, doc: ExtractedDocument):
        tone_map = {
            DocumentCategory.PRYWATNE: "nieformalny",
            DocumentCategory.SZKOLNE: "półformalny",
            DocumentCategory.KOMORNICZE: "formalny",
            DocumentCategory.URZEDOWE: "formalny",
            DocumentCategory.BANKOWE: "formalny",
            DocumentCategory.PODATKOWE: "formalny",
            DocumentCategory.PRAWNE: "formalny",
            DocumentCategory.MEDYCZNE: "półformalny",
        }
        sender_type = doc.classification.sender_type
        if sender_type == "osoba_prywatna":
            doc.suggested_response_tone = "nieformalny"
        else:
            doc.suggested_response_tone = tone_map.get(
                doc.classification.category, "formalny"
            )