# STYLE & BRANDING SYSTEM — PismaAI

Ten dokument definiuje spójny styl produktu, branding i zasady UI/UX dla całej aplikacji.
Cel: każde narzędzie (AI, frontend, backend, design, code review) ma rozpoznawać i stosować te same reguły.

## 1. Tożsamość marki

- Nazwa produktu: **PismaAI**
- Charakter marki: profesjonalna, nowoczesna, zaufana, prawniczo-urzędowa
- Ton komunikacji: jasny, rzeczowy, pomocny, bez przesadnego marketingu
- Język interfejsu: **polski**

## 2. Kierunek wizualny

- Styl: „legal-tech premium” (czyste powierzchnie + mocne akcenty niebieskie)
- Priorytety: czytelność, kontrast, porządek, przewidywalność
- Komponenty: zaokrąglone rogi, miękkie cienie, subtelne obramowania
- Layout: sidebar + topbar + sekcje kroków (1-4)

## 3. Kolory (design tokens)

Używaj zmiennych CSS zamiast losowych kolorów:

- `--bg`, `--bg2`, `--bg3`
- `--surf`, `--surf-hi`
- `--blue`, `--blue2`, `--blue-dim`
- `--text`, `--text2`
- `--bdr`, `--bdr-mid`

### Tryb ciemny

- Tła: granatowo-grafitowe (`#0c1322`, `#141b2b`, `#191f2f`)
- Tekst główny: jasny (`#dce2f7`)
- Akcent: niebieski (`#3b82f6`, `#60a5fa`)

### Tryb jasny

- Tła: białe/szare (`#ffffff`, `#f9fafb`, `#f3f4f6`)
- Tekst główny: ciemny (`#111827`)
- Akcent: niebieski (`#2563eb`, `#1d4ed8`)

## 4. Typografia

- Branding/nagłówki premium: **Sora**
- Interfejs i treści: **Inter**
- Priorytet: czytelność nad dekoracyjność

## 5. Zasady komponentów

### Sidebar

- Stały po lewej, nowoczesny, zgodny ze Stitch
- Aktywna pozycja: widoczne podświetlenie + akcent koloru
- CTA na dole: wyraźny gradient i jasny komunikat

### Stepper (kroki)

- Kroki: **Skanowanie → Analiza → Weryfikacja → Eksport**
- Etykiety pod ikonami (nie w jednej linii)
- Aktywny krok musi być wizualnie jednoznaczny

### Karty i panele

- Spójne promienie rogów
- Delikatne obramowanie + kontrolowany cień
- Zero przypadkowych styli inline, jeśli można użyć klas

## 6. Reguły kontrastu i dostępności

- Light mode: ciemny tekst na jasnym tle
- Dark mode: jasny tekst na ciemnym tle
- Nie używać niskiego kontrastu dla kluczowych danych
- Elementy klikalne muszą mieć wyraźny hover/focus

## 7. Ikony i symbole

- Preferencja: Material Symbols lub spójny zestaw emoji
- Nie mieszać wielu stylów ikon w obrębie jednego modułu
- Ikona ma wspierać semantykę (np. historia, ustawienia, konto)

## 8. Zasady dla narzędzi i agentów

Każde narzędzie pracujące nad UI powinno:

1. Zachować istniejącą architekturę kroków i endpointów.
2. Stosować design tokens z `:root`.
3. Utrzymywać pełną zgodność light/dark mode.
4. Nie zmieniać logiki komorniczej (tylko UI/UX, jeśli o to chodzi).
5. Nie usuwać istniejących funkcji — tylko rozszerzać.
6. Zachować polskie komunikaty i etykiety.

## 9. Gotowe etykiety produktu (copy)

- Główny tytuł: **System Procesowania Pism**
- Krok 1: **Skanowanie**
- Krok 2: **Analiza**
- Krok 3: **Weryfikacja**
- Krok 4: **Eksport**
- CTA główne: **Nowe pismo** / **Przetwórz pismo**

## 10. Definition of Done dla zmian UI

Zmiana jest ukończona, gdy:

- wygląda spójnie z brandingiem PismaAI,
- działa poprawnie w light i dark mode,
- nie obniża czytelności,
- nie psuje istniejącej logiki biznesowej,
- zachowuje stylistykę całego workflow.
