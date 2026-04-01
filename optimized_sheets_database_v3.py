"""
ULTRASZYBKA wersja GoogleSheetsManager z inteligentnym odświeżaniem cache'u
Obsługuje:
1. Automatyczne odświeżanie przy zmianach
2. Wymuszanie odświeżania na żądanie
3. Konfigurowalne TTL
4. Websocket/polling dla real-time updates
"""

import os
import json
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
import time
from threading import Lock, Thread
import logging
import hashlib

class SmartOptimizedGoogleSheetsManager:
    """
    ULTRASZYBKA klasa z inteligentnym systemem odświeżania cache'u
    """
    
    def __init__(self, credentials_path='google_credentials.json', auto_refresh=True, refresh_interval=300):
        """
        Inicjalizacja z systemem inteligentnego cache'u
        
        Args:
            credentials_path: ścieżka do pliku z danymi uwierzytelniającymi
            auto_refresh: czy automatycznie odświeżać cache (domyślnie True)
            refresh_interval: interwał odświeżania w sekundach (domyślnie 300s = 5 minut)
        """
        self.credentials_path = credentials_path
        self.client = None
        self.auto_refresh = auto_refresh
        self.refresh_interval = refresh_interval
        
        # Cache system with smart invalidation
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_lock = Lock()
        self._data_hashes = {}  # Do wykrywania zmian w danych
        
        # Konfigurowalne TTL dla różnych typów danych
        self.cache_ttl = {
            'employees': 60,      # 1 minuta dla pracowników  
            'proceedings': 30,    # 30 sekund dla postępowań (częściej się zmieniają)
            'bailiffs': 300,      # 5 minut dla komorników (rzadko się zmieniają)
            'default': 60
        }
        
        # High-performance indexed caches O(1) lookup
        self._employee_index = {}  # PESEL -> employee data
        self._proceedings_index = {}  # PESEL -> [proceedings]
        self._bailiff_index = {}  # ID -> bailiff data
        self._index_timestamps = {}
        self._index_hashes = {}  # Do wykrywania zmian w indeksach
        
        # Spreadsheet IDs
        self.komornicy_spreadsheet_id = '1uHTm4Xwmv-V5NUA90TvQA2si8CbDc5ht0tIABUesE_A'
        self.pracownicy_spreadsheet_id = '1vrVjRscPq-Ld-6EuC2k_MunP3GbXrcYhxYTjJ6yy_Ow'
        self.postepowania_spreadsheet_id = '1OlCRU5R_I3bVkUvDwWGJ9hzMyy4A84NnOQBBohd5XDQ'
        
        # Performance tracking
        self.api_call_count = 0
        self.cache_hit_count = 0
        self.refresh_count = 0
        self.last_refresh_time = None
        
        # Auto-refresh thread
        self._refresh_thread = None
        self._stop_refresh = False
        
        self._connect()
        
        if self.auto_refresh:
            self.start_auto_refresh()
        
    def _connect(self):
        """Nawiązanie połączenia z Google Sheets API"""
        try:
            SCOPES = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            if not os.path.exists(self.credentials_path):
                print(f"❌ Brak pliku z danymi uwierzytelniającymi ({self.credentials_path})")
                return False
            
            print(f"🔄 Wczytywanie danych uwierzytelniających z {self.credentials_path}...")
            
            with open(self.credentials_path, 'r', encoding='utf-8') as credentials_file:
                credentials_data = json.load(credentials_file)
            
            credentials = Credentials.from_service_account_info(credentials_data, scopes=SCOPES)
            self.client = gspread.authorize(credentials)
            
            print("✅ Autoryzacja z Google API zakończona sukcesem")
            print(f"🔄 Automatyczne odświeżanie: {'WŁĄCZONE' if self.auto_refresh else 'WYŁĄCZONE'}")
            if self.auto_refresh:
                print(f"⏰ Interwał odświeżania: {self.refresh_interval}s")
            print("🚀 Inicjalizacja SMART CACHE bazy danych Google Sheets zakończona pomyślnie")
            return True
            
        except Exception as e:
            print(f"❌ Błąd połączenia z Google API: {str(e)}")
            return False
    
    def _calculate_data_hash(self, data):
        """Oblicz hash danych do wykrywania zmian"""
        if not data:
            return None
        
        # Konwertuj dane do stabilnego stringa i oblicz hash
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()
    
    def _has_data_changed(self, cache_key, new_data):
        """Sprawdź czy dane się zmieniły od ostatniego pobrania"""
        new_hash = self._calculate_data_hash(new_data)
        old_hash = self._data_hashes.get(cache_key)
        
        if old_hash != new_hash:
            self._data_hashes[cache_key] = new_hash
            if old_hash is not None:  # Nie loguj przy pierwszym pobraniu
                print(f"🔄 Wykryto zmiany w danych: {cache_key}")
            return True
        
        return False
    
    def _is_cache_valid(self, cache_key, data_type='default'):
        """Sprawdź czy cache jest aktualny"""
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[cache_key]
        ttl = self.cache_ttl.get(data_type, self.cache_ttl['default'])
        
        is_valid = (time.time() - cache_time) < ttl
        
        if not is_valid:
            print(f"⏰ Cache wygasł dla {cache_key} (TTL: {ttl}s)")
        
        return is_valid
    
    def _get_cached_data(self, cache_key, data_type='default'):
        """Pobierz dane z cache"""
        with self._cache_lock:
            if cache_key in self._cache and self._is_cache_valid(cache_key, data_type):
                self.cache_hit_count += 1
                print(f"💨 Cache HIT dla {cache_key}")
                return self._cache[cache_key]
        return None
    
    def _cache_data(self, cache_key, data, data_type='default'):
        """Zapisz dane do cache"""
        with self._cache_lock:
            self._cache[cache_key] = data
            self._cache_timestamps[cache_key] = time.time()
            self._has_data_changed(cache_key, data)  # Aktualizuj hash
            print(f"💾 Zapisano do cache: {cache_key} (TTL: {self.cache_ttl.get(data_type, self.cache_ttl['default'])}s)")
    
    def force_refresh_cache(self, cache_type=None):
        """
        Wymuś odświeżenie cache'u
        
        Args:
            cache_type: 'employees', 'proceedings', 'bailiffs' lub None (wszystkie)
        """
        print(f"🔄 Wymuszanie odświeżenia cache: {cache_type or 'ALL'}")
        
        with self._cache_lock:
            if cache_type:
                # Odśwież konkretny typ cache
                keys_to_remove = [k for k in self._cache.keys() if cache_type in k.lower()]
                for key in keys_to_remove:
                    if key in self._cache:
                        del self._cache[key]
                    if key in self._cache_timestamps:
                        del self._cache_timestamps[key]
                    if key in self._data_hashes:
                        del self._data_hashes[key]
            else:
                # Wyczyść wszystko
                self._cache.clear()
                self._cache_timestamps.clear()
                self._data_hashes.clear()
                
                # Wyczyść indeksy
                self._employee_index.clear()
                self._proceedings_index.clear()
                self._bailiff_index.clear()
                self._index_timestamps.clear()
                self._index_hashes.clear()
        
        self.refresh_count += 1
        self.last_refresh_time = datetime.now()
        print(f"✅ Cache odświeżony ({self.refresh_count} odświeżeń)")
    
    def start_auto_refresh(self):
        """Uruchom automatyczne odświeżanie w tle"""
        if self._refresh_thread and self._refresh_thread.is_alive():
            print("🔄 Auto-refresh już działa")
            return
        
        self._stop_refresh = False
        self._refresh_thread = Thread(target=self._auto_refresh_worker, daemon=True)
        self._refresh_thread.start()
        print(f"🚀 Uruchomiono auto-refresh (co {self.refresh_interval}s)")
    
    def stop_auto_refresh(self):
        """Zatrzymaj automatyczne odświeżanie"""
        self._stop_refresh = True
        if self._refresh_thread:
            self._refresh_thread.join(timeout=1)
        print("⏹️ Zatrzymano auto-refresh")
    
    def set_refresh_interval(self, interval_seconds):
        """
        Zmień interwał odświeżania
        
        Args:
            interval_seconds: nowy interwał w sekundach (minimum 10s)
        """
        if interval_seconds < 10:
            print("⚠️ Minimum interwał to 10 sekund")
            interval_seconds = 10
        
        old_interval = self.refresh_interval
        self.refresh_interval = interval_seconds
        
        print(f"⏰ Zmiana interwału odświeżania: {old_interval}s → {interval_seconds}s")
        
        # Restart auto-refresh jeśli był włączony
        if self.auto_refresh and self._refresh_thread and self._refresh_thread.is_alive():
            print("🔄 Restartowanie auto-refresh z nowym interwałem...")
            self.stop_auto_refresh()
            time.sleep(0.5)  # Krótka pauza
            self.start_auto_refresh()
        
        return True
    
    def _auto_refresh_worker(self):
        """Worker thread dla automatycznego odświeżania"""
        while not self._stop_refresh:
            try:
                time.sleep(self.refresh_interval)
                if not self._stop_refresh:
                    self._check_and_refresh_if_needed()
            except Exception as e:
                print(f"❌ Błąd w auto-refresh: {e}")
                time.sleep(5)  # Krótka pauza przed ponowną próbą
    
    def _check_and_refresh_if_needed(self):
        """Sprawdź czy potrzebne jest odświeżenie i odśwież jeśli tak"""
        print("🔍 Sprawdzanie zmian w Google Sheets...")
        
        # Sprawdź każdy typ danych
        for data_type in ['employees', 'proceedings', 'bailiffs']:
            try:
                # Pobierz świeże dane (pomijając cache)
                fresh_data = self._get_fresh_data(data_type)
                cache_key = f"{data_type}_data"
                
                # Sprawdź czy dane się zmieniły
                if self._has_data_changed(cache_key, fresh_data):
                    print(f"🔄 Wykryto zmiany w {data_type}, odświeżanie cache...")
                    self.force_refresh_cache(data_type)
                    
            except Exception as e:
                print(f"❌ Błąd przy sprawdzaniu {data_type}: {e}")
    
    def _get_fresh_data(self, data_type):
        """Pobierz świeże dane bezpośrednio z API (pomijając cache)"""
        if data_type == 'employees':
            return self._get_worksheet_data_direct(self.pracownicy_spreadsheet_id, "auto")
        elif data_type == 'proceedings':
            return self._get_worksheet_data_direct(self.postepowania_spreadsheet_id, "auto")
        elif data_type == 'bailiffs':
            return self._get_worksheet_data_direct(self.komornicy_spreadsheet_id, "auto")
        return None
    
    def _get_worksheet_data_direct(self, spreadsheet_id, worksheet_name="auto"):
        """Pobierz dane bezpośrednio z API (bez cache)"""
        try:
            self.api_call_count += 1
            
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            if worksheet_name == "auto":
                worksheet = spreadsheet.sheet1
            else:
                worksheet = spreadsheet.worksheet(worksheet_name)
            
            data = worksheet.get_all_records()
            print(f"📊 Pobrano {len(data)} rekordów z arkusza (API call #{self.api_call_count})")
            return data
            
        except Exception as e:
            print(f"❌ Błąd pobierania danych z arkusza: {str(e)}")
            return []
    
    def _get_worksheet_data(self, spreadsheet_id, worksheet_name="auto", force_refresh=False, data_type='default'):
        """Pobierz dane z arkusza z inteligentnym cache'owaniem"""
        cache_key = f"{spreadsheet_id}_{worksheet_name}"
        
        # Sprawdź cache (jeśli nie wymuszamy odświeżenia)
        if not force_refresh:
            cached_data = self._get_cached_data(cache_key, data_type)
            if cached_data is not None:
                return cached_data
        
        # Pobierz świeże dane
        print(f"🔄 Pobieranie świeżych danych z arkusza...")
        data = self._get_worksheet_data_direct(spreadsheet_id, worksheet_name)
        
        # Zapisz do cache
        if data:
            self._cache_data(cache_key, data, data_type)
        
        return data
    
    def _build_employee_index(self, employees_data):
        """Buduj ultraszybki indeks pracowników O(1)"""
        print(f"🔨 Budowanie indeksu pracowników ({len(employees_data)} rekordów)...")
        
        new_index = {}
        
        for emp in employees_data:
            pesel = str(emp.get('pesel', '')).strip()
            if pesel and pesel != '':
                new_index[pesel] = emp
        
        # Sprawdź czy indeks się zmienił
        new_hash = self._calculate_data_hash(new_index)
        old_hash = self._index_hashes.get('employees')
        
        if old_hash != new_hash:
            with self._cache_lock:
                self._employee_index = new_index
                self._index_timestamps['employees'] = time.time()
                self._index_hashes['employees'] = new_hash
            
            if old_hash is not None:
                print(f"🔄 Zaktualizowano indeks pracowników ({len(new_index)} wpisów)")
            else:
                print(f"✅ Zbudowano indeks pracowników ({len(new_index)} wpisów)")
        else:
            print(f"✅ Indeks pracowników aktualny ({len(new_index)} wpisów)")
    
    def _build_proceedings_index(self, proceedings_data, bailiffs_data):
        """Buduj ultraszybki indeks postępowań O(1)"""
        print(f"🔨 Budowanie indeksu postępowań ({len(proceedings_data)} rekordów)...")
        
        # Najpierw zbuduj mapę komorników
        bailiff_map = {}
        for bailiff in bailiffs_data:
            bailiff_id = str(bailiff.get('id', '')).strip()
            if bailiff_id:
                bailiff_map[bailiff_id] = bailiff
        
        # Zbuduj indeks postępowań grupowanych po PESEL
        new_index = {}
        
        for proc in proceedings_data:
            pesel = str(proc.get('pesel_pracownika', '')).strip()
            if pesel and pesel != '':
                if pesel not in new_index:
                    new_index[pesel] = []
                
                # Wzbogać postępowanie o dane komornika
                komornik_id = str(proc.get('komornik_id', '')).strip()
                if komornik_id in bailiff_map:
                    proc['komornik_dane'] = bailiff_map[komornik_id]
                
                new_index[pesel].append(proc)
        
        # Sprawdź czy indeks się zmienił
        new_hash = self._calculate_data_hash(new_index)
        old_hash = self._index_hashes.get('proceedings')
        
        if old_hash != new_hash:
            with self._cache_lock:
                self._proceedings_index = new_index
                self._index_timestamps['proceedings'] = time.time()
                self._index_hashes['proceedings'] = new_hash
            
            if old_hash is not None:
                print(f"🔄 Zaktualizowano indeks postępowań ({len(new_index)} unikalnych PESEL)")
            else:
                print(f"✅ Zbudowano indeks postępowań ({len(new_index)} unikalnych PESEL)")
        else:
            print(f"✅ Indeks postępowań aktualny ({len(new_index)} unikalnych PESEL)")
    
    def _ensure_indexes_ready(self, force_refresh=False):
        """Upewnij się że indeksy są gotowe do użycia"""
        
        if force_refresh:
            print("🔄 Wymuszanie przebudowy indeksów...")
        
        # Sprawdź czy indeksy istnieją i są aktualne
        employees_ready = bool(self._employee_index) and not force_refresh
        proceedings_ready = bool(self._proceedings_index) and not force_refresh
        
        if not employees_ready:
            print("🔄 Przebudowywanie indeksu pracowników...")
            employees_data = self._get_worksheet_data(
                self.pracownicy_spreadsheet_id, 
                "auto", 
                force_refresh=force_refresh,
                data_type='employees'
            )
            self._build_employee_index(employees_data)
        
        if not proceedings_ready:
            print("🔄 Przebudowywanie indeksu postępowań...")
            proceedings_data = self._get_worksheet_data(
                self.postepowania_spreadsheet_id, 
                "auto", 
                force_refresh=force_refresh,
                data_type='proceedings'
            )
            bailiffs_data = self._get_worksheet_data(
                self.komornicy_spreadsheet_id, 
                "auto", 
                force_refresh=force_refresh,
                data_type='bailiffs'
            )
            self._build_proceedings_index(proceedings_data, bailiffs_data)
    
    def get_employee_by_pesel_ultrafast(self, pesel, force_refresh=False):
        """ULTRASZYBKIE wyszukiwanie pracownika O(1) z opcją wymuszenia odświeżenia"""
        start_time = time.time()
        
        self._ensure_indexes_ready(force_refresh=force_refresh)
        
        search_pesel = str(pesel).strip()
        employee = self._employee_index.get(search_pesel)
        
        elapsed = time.time() - start_time
        status = "ZNALEZIONY" if employee else "NIE ZNALEZIONY"
        refresh_info = " (FRESH)" if force_refresh else ""
        print(f"⚡ ULTRAFAST wyszukiwanie pracownika: {elapsed:.3f}s ({status}){refresh_info}")
        
        return employee
    
    def get_bailiff_proceedings_ultrafast(self, pesel, force_refresh=False):
        """ULTRASZYBKIE pobieranie postępowań O(1) z opcją wymuszenia odświeżenia"""
        start_time = time.time()
        
        self._ensure_indexes_ready(force_refresh=force_refresh)
        
        search_pesel = str(pesel).strip()
        proceedings = self._proceedings_index.get(search_pesel, [])
        
        elapsed = time.time() - start_time
        refresh_info = " (FRESH)" if force_refresh else ""
        print(f"⚡ ULTRAFAST wyszukiwanie postępowań: {elapsed:.3f}s ({len(proceedings)} postępowań){refresh_info}")
        
        return proceedings
    
    def get_employee_with_conflicts_ultrafast(self, pesel, force_refresh=False):
        """ULTRASZYBKIE zjednoczone wyszukiwanie z opcją wymuszenia odświeżenia"""
        start_time = time.time()
        
        # Upewnij się że indeksy są gotowe
        self._ensure_indexes_ready(force_refresh=force_refresh)
        
        search_pesel = str(pesel).strip()
        
        # O(1) lookup dla pracownika
        employee = self._employee_index.get(search_pesel)
        
        if employee:
            # O(1) lookup dla postępowań
            proceedings = self._proceedings_index.get(search_pesel, [])
            
            conflict_info = {
                'has_conflict': len(proceedings) > 0,
                'proceedings_count': len(proceedings),
                'active_proceedings': [p for p in proceedings if p.get('status', '').lower() == 'aktywne'],
                'all_proceedings': proceedings
            }
            
            employee['conflict_info'] = conflict_info
            
            elapsed = time.time() - start_time
            refresh_info = " (FRESH)" if force_refresh else ""
            print(f"⚡ ULTRAFAST kompletne wyszukiwanie: {elapsed:.3f}s (pracownik + {len(proceedings)} postępowań){refresh_info}")
            
            return employee
        
        elapsed = time.time() - start_time
        refresh_info = " (FRESH)" if force_refresh else ""
        print(f"⚡ ULTRAFAST kompletne wyszukiwanie: {elapsed:.3f}s (pracownik nie znaleziony){refresh_info}")
        return None
    
    def get_performance_stats(self):
        """Pobierz statystyki wydajności i cache'u"""
        with self._cache_lock:
            cache_size = len(self._cache)
            index_info = {
                'employees': len(self._employee_index),
                'proceedings': len(self._proceedings_index),
                'bailiffs': len(self._bailiff_index)
            }
        
        return {
            'api_calls': self.api_call_count,
            'cache_hits': self.cache_hit_count,
            'cache_size': cache_size,
            'refresh_count': self.refresh_count,
            'last_refresh': self.last_refresh_time.isoformat() if self.last_refresh_time else None,
            'auto_refresh_enabled': self.auto_refresh,
            'refresh_interval': self.refresh_interval,
            'index_sizes': index_info,
            'cache_ttl_settings': self.cache_ttl
        }
    
    # === Dodatkowe metody dla kompatybilności ===
    
    def get_all_bailiffs(self):
        """Pobierz wszystkich komorników z cache'owaniem"""
        return self._get_worksheet_data(self.komornicy_spreadsheet_id, "auto", data_type='bailiffs')
    
    def get_bailiff_by_id(self, bailiff_id):
        """Pobiera komornika po ID z cache lub Google Sheets"""
        try:
            bailiffs = self._get_worksheet_data(self.komornicy_spreadsheet_id, "auto", data_type='bailiffs')
            # Konwertuj bailiff_id na string dla porównania
            bailiff_id_str = str(bailiff_id)
            
            for bailiff in bailiffs:
                # Porównaj zarówno jako string jak i oryginalny typ
                if bailiff.get('id') == bailiff_id or str(bailiff.get('id')) == bailiff_id_str:
                    return bailiff
            return None
        except Exception as e:
            print(f"❌ Błąd pobierania komornika {bailiff_id}: {e}")
            return None

    def get_bailiff_by_name(self, name):
        """Pobiera komornika po imieniu i nazwisku"""
        try:
            bailiffs = self._get_worksheet_data(self.komornicy_spreadsheet_id, "auto", data_type='bailiffs')
            for bailiff in bailiffs:
                if bailiff.get('imie_nazwisko') == name or bailiff.get('imieNazwisko') == name:
                    return bailiff
            return None
        except Exception as e:
            print(f"❌ Błąd pobierania komornika po nazwisku {name}: {e}")
            return None

    def clear_cache(self):
        """Wyczyść cache i indeksy (użyj po dodaniu nowych danych)"""
        with self._cache_lock:
            self._cache.clear()
            self._cache_timestamps.clear()
            self._data_hashes.clear()
            self._employee_index.clear()
            self._proceedings_index.clear()
            self._bailiff_index.clear()
            self._index_timestamps.clear()
            self._index_hashes.clear()
        print("🗑️ Cache i indeksy wyczyszczone")
        return True
    
    def get_cache_stats(self):
        """Pobierz statystyki cache i indeksów (alias dla get_performance_stats)"""
        return self.get_performance_stats()
    
    # === Kompatybilność z oryginalnym API ===
    
    def get_employee_by_pesel(self, pesel):
        """Wrapper dla kompatybilności"""
        return self.get_employee_by_pesel_ultrafast(pesel)
    
    def get_employee_with_conflicts_optimized(self, pesel):
        """Wrapper dla kompatybilności z wersją v2 - zwraca strukturę zgodną z API"""
        employee = self.get_employee_with_conflicts_ultrafast(pesel)
        if employee:
            conflict_info = employee.get('conflict_info', {})
            return {
                "employee": employee,
                "bailiff_conflict": conflict_info,
                "found": True
            }
        else:
            return {"found": False, "message": "Pracownik nie został znaleziony w bazie danych"}
    
    def get_bailiff_proceedings(self, pesel):
        """Wrapper dla kompatybilności"""
        return self.get_bailiff_proceedings_ultrafast(pesel)
    
    def detect_bailiff_conflict(self, pesel):
        """Wrapper dla kompatybilności"""
        proceedings = self.get_bailiff_proceedings_ultrafast(pesel)
        return {
            'is_conflict': len(proceedings) > 0,
            'active_proceedings_count': len(proceedings),
            'proceedings': proceedings
        }
    
    def populate_test_data(self):
        """Metoda kompatybilności - dane testowe już są w Google Sheets"""
        print("🔄 Dane testowe już istnieją w Google Sheets, pomijam wypełnianie")
        return True
    
    def set_spreadsheet_ids(self, komornicy_id=None, pracownicy_id=None, postepowania_id=None):
        """
        Ustawia identyfikatory arkuszy dla każdej tabeli.
        
        Args:
            komornicy_id (str): ID arkusza dla komorników
            pracownicy_id (str): ID arkusza dla pracowników
            postepowania_id (str): ID arkusza dla postępowań
        """
        if komornicy_id:
            self.komornicy_spreadsheet_id = self._extract_spreadsheet_id(komornicy_id)
            print(f"✅ Ustawiono arkusz komorników: {self.komornicy_spreadsheet_id}")
        
        if pracownicy_id:
            self.pracownicy_spreadsheet_id = self._extract_spreadsheet_id(pracownicy_id)
            print(f"✅ Ustawiono arkusz pracowników: {self.pracownicy_spreadsheet_id}")
        
        if postepowania_id:
            self.postepowania_spreadsheet_id = self._extract_spreadsheet_id(postepowania_id)
            print(f"✅ Ustawiono arkusz postępowań: {self.postepowania_spreadsheet_id}")
    
    def _extract_spreadsheet_id(self, spreadsheet_id_or_url):
        """
        Wyciąga ID arkusza z URL lub zwraca podany ID.
        
        Args:
            spreadsheet_id_or_url (str): ID lub URL arkusza Google Sheets
            
        Returns:
            str: ID arkusza
        """
        if 'spreadsheets.google.com' in spreadsheet_id_or_url:
            # Wyciągnij ID z URL
            parts = spreadsheet_id_or_url.split('/')
            id_index = parts.index('d') if 'd' in parts else -1
            if id_index >= 0 and id_index + 1 < len(parts):
                return parts[id_index + 1].split('?')[0]
            else:
                raise ValueError(f"Nie można wyciągnąć ID arkusza z URL: {spreadsheet_id_or_url}")
        else:
            return spreadsheet_id_or_url
    
    def init_database(self):
        """Inicjalizacja bazy danych (w Google Sheets to właściwie sprawdzenie czy arkusze istnieją)"""
        print("🔄 Inicjalizacja bazy danych w Google Sheets...")
        
        # Sprawdź dostęp do wszystkich arkuszy
        try:
            # Sprawdź arkusz komorników
            komornicy_spreadsheet = self.client.open_by_key(self.komornicy_spreadsheet_id)
            print(f"✅ Otwarto arkusz komorników: {komornicy_spreadsheet.title}")

            # Sprawdź arkusz pracowników
            pracownicy_spreadsheet = self.client.open_by_key(self.pracownicy_spreadsheet_id)
            print(f"✅ Otwarto arkusz pracowników: {pracownicy_spreadsheet.title}")

            # Sprawdź arkusz postępowań
            postepowania_spreadsheet = self.client.open_by_key(self.postepowania_spreadsheet_id)
            print(f"✅ Otwarto arkusz postępowań: {postepowania_spreadsheet.title}")

            print("✅ Baza danych została zainicjalizowana")
            return True
        except Exception as e:
            print(f"❌ Błąd inicjalizacji bazy danych: {str(e)}")
            return False

    # === Metody do zapisu z automatycznym odświeżaniem cache ===
    
    def add_new_bailiff(self, imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon='', email='', sad_rejonowy=''):
        """Dodaj nowego komornika do bazy danych z automatycznym odświeżeniem cache"""
        try:
            if not self.komornicy_spreadsheet_id:
                print("❌ Brak ustawionego ID arkusza komorników")
                return None

            # Pobierz arkusz komorników
            spreadsheet = self.client.open_by_key(self.komornicy_spreadsheet_id)
            try:
                komornicy_sheet = spreadsheet.worksheet("komornicy")
            except:
                komornicy_sheet = spreadsheet.sheet1
            
            # Generuj nowe ID
            new_id = self._generate_id("komornicy")
            
            # Przygotuj dane
            new_bailiff = {
                'id': new_id,
                'imie_nazwisko': imie_nazwisko,
                'plec': plec,
                'adres': adres,
                'kod_pocztowy': kod_pocztowy,
                'miasto': miasto,
                'telefon': telefon,
                'email': email,
                'sad_rejonowy': sad_rejonowy,
                'aktywny': 1,
                'data_dodania': datetime.now().isoformat()
            }
            
            # Pobierz nagłówki i przygotuj dane w prawidłowej kolejności
            headers = komornicy_sheet.row_values(1)
            row_values = [new_bailiff.get(header, '') for header in headers]
            
            # Dodaj wiersz do arkusza
            komornicy_sheet.append_row(row_values)
            print(f"✅ Dodano nowego komornika: {imie_nazwisko} (ID: {new_id})")
            
            # Odśwież cache dla komorników
            self.force_refresh_cache('bailiffs')
            
            return new_bailiff
            
        except Exception as e:
            print(f"❌ Błąd dodawania komornika: {str(e)}")
            return None
    
    def add_new_proceeding(self, pesel, komornik_data, sygnatura, data_wplywu):
        """Dodaj nowe postępowanie do bazy danych z automatycznym odświeżeniem cache"""
        try:
            if not self.postepowania_spreadsheet_id:
                print("❌ Brak ustawionego ID arkusza postępowań")
                return None

            # Pobierz arkusz postępowań
            spreadsheet = self.client.open_by_key(self.postepowania_spreadsheet_id)
            try:
                postepowania_sheet = spreadsheet.worksheet("postepowania")
            except:
                postepowania_sheet = spreadsheet.sheet1
            
            # Generuj nowe ID
            new_id = self._generate_id("postepowania")
            
            # Przygotuj dane
            new_proceeding = {
                'id': new_id,
                'pesel_pracownika': pesel,
                'komornik_id': komornik_data.get('id', ''),
                'komornik_imie_nazwisko': komornik_data.get('imie_nazwisko', ''),
                'sygnatura': sygnatura,
                'data_wplywu': data_wplywu,
                'status': 'aktywne',
                'data_dodania': datetime.now().isoformat()
            }
            
            # Dodaj wiersz do arkusza
            postepowania_sheet.append_row(list(new_proceeding.values()))
            print(f"✅ Dodano nowe postępowanie: {sygnatura} dla PESEL {pesel}")
            
            # Odśwież cache dla postępowań
            self.force_refresh_cache('proceedings')
            
            return new_proceeding
            
        except Exception as e:
            print(f"❌ Błąd dodawania postępowania: {str(e)}")
            return None
    
    def _generate_id(self, table_type):
        """Generuj nowe ID dla tabeli - sekwencyjna numeracja"""
        try:
            # Mapowanie nazw tabel na odpowiednie arkusze
            sheet_config = {
                'komornicy': {'spreadsheet_id': self.komornicy_spreadsheet_id, 'sheet_name': 'komornicy'},
                'postepowania': {'spreadsheet_id': self.postepowania_spreadsheet_id, 'sheet_name': 'postepowania'},
                'pracownicy': {'spreadsheet_id': self.pracownicy_spreadsheet_id, 'sheet_name': 'pracownicy'}
            }
            
            if table_type not in sheet_config:
                # Fallback do timestamp dla nieznanych typów
                import time
                timestamp = str(int(time.time() * 1000))[-8:]
                return f"X{timestamp}"
            
            config = sheet_config[table_type]
            spreadsheet = self.client.open_by_key(config['spreadsheet_id'])
            
            try:
                worksheet = spreadsheet.worksheet(config['sheet_name'])
            except:
                worksheet = spreadsheet.sheet1
            
            # Pobierz wszystkie wartości z pierwszej kolumny (ID)
            all_values = worksheet.get_all_values()
            if len(all_values) <= 1:  # Tylko nagłówek lub pusty arkusz
                return "1"
            
            # Znajdź najwyższe ID numeryczne
            max_id = 0
            for row in all_values[1:]:  # Pomijamy nagłówek
                if row and row[0]:  # Jeśli jest wartość w pierwszej kolumnie
                    try:
                        # Próbuj przekonwertować na liczbę
                        current_id = int(str(row[0]).strip())
                        if current_id > max_id:
                            max_id = current_id
                    except ValueError:
                        # Ignoruj nie-numeryczne ID
                        continue
            
            # Zwróć następny numer w sekwencji
            return str(max_id + 1)
            
        except Exception as e:
            print(f"❌ Błąd generowania ID dla {table_type}: {str(e)}")
            # Fallback do timestamp w przypadku błędu
            import time
            timestamp = str(int(time.time() * 1000))[-8:]
            return f"ERR{timestamp}"

    def _find_record_index(self, worksheet_name, column, value):
        """Znajdź indeks wiersza na podstawie wartości w kolumnie"""
        # Wybierz odpowiedni arkusz w zależności od nazwy
        if worksheet_name == "komornicy":
            spreadsheet_id = self.komornicy_spreadsheet_id
        elif worksheet_name == "pracownicy":
            spreadsheet_id = self.pracownicy_spreadsheet_id
        elif worksheet_name == "postepowania":
            spreadsheet_id = self.postepowania_spreadsheet_id
        else:
            print(f"❌ Nieznana nazwa arkusza: {worksheet_name}")
            return None
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except:
                worksheet = spreadsheet.sheet1
            
            # Pobierz wszystkie wartości
            all_values = worksheet.get_all_values()
            if not all_values:
                return None
                
            headers = all_values[0]
            
            # Znajdź indeks kolumny
            try:
                col_index = headers.index(column)
            except ValueError:
                print(f"❌ Kolumna '{column}' nie została znaleziona w nagłówkach: {headers}")
                return None
            
            # Szukaj wartości w kolumnie
            for i, row in enumerate(all_values[1:], start=2):  # start=2 bo pomijamy nagłówek i indeksujemy od 1
                if len(row) > col_index and str(row[col_index]).strip() == str(value).strip():
                    print(f"✅ Znaleziono rekord w wierszu {i} dla {column}={value}")
                    return i
            
            print(f"❌ Nie znaleziono rekordu dla {column}={value}")
            return None
            
        except Exception as e:
            print(f"❌ Błąd wyszukiwania rekordu: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def populate_test_data(self):
        """Wypełnienie bazy danych testowymi danymi"""
        # Sprawdź czy dane już istnieją
        try:
            komornicy_spreadsheet = self.client.open_by_key(self.komornicy_spreadsheet_id)
            try:
                komornicy_sheet = komornicy_spreadsheet.worksheet("komornicy")
            except:
                komornicy_sheet = komornicy_spreadsheet.sheet1
            
            records = komornicy_sheet.get_all_records()
            
            if records:
                print("🔄 Dane testowe już istnieją w Google Sheets, pomijam wypełnianie")
                return
            
            print("🔄 Wypełnianie bazy danych testowymi danymi...")
            
            # Dane testowe - skrócona wersja
            komornicy_data = [
                {"id": "K001", "imie_nazwisko": "Adam Niegórski", "plec": "m", "adres": "ul. Piotrkowska 123", "kod_pocztowy": "90-001", "miasto": "Łódź", "telefon": "42-123-45-67", "email": "a.niegorski@komornik.pl", "sad_rejonowy": "Sąd Rejonowy w Łodzi", "aktywny": 1, "data_dodania": datetime.now().isoformat()},
                {"id": "K002", "imie_nazwisko": "Anna Kowalska", "plec": "k", "adres": "ul. Kilińskiego 45", "kod_pocztowy": "00-001", "miasto": "Warszawa", "telefon": "22-987-65-43", "email": "a.kowalska@komornik.pl", "sad_rejonowy": "Sąd Rejonowy w Warszawie", "aktywny": 1, "data_dodania": datetime.now().isoformat()}
            ]
            
            pracownicy_data = [
                {"id": "E001", "imie": "Jan", "nazwisko": "Kowalski", "pesel": "85030512345", "data_urodzenia": "1985-03-05", "adres_zamieszkania": "ul. Mickiewicza 12", "kod_pocztowy": "90-001", "miasto": "Łódź", "telefon": "501-234-567", "email": "jan.kowalski@avalon.pl", "stanowisko": "Kierowca", "spolka": "Avalon Taxi", "data_zatrudnienia": "2020-01-15", "status_zatrudnienia": "aktywny", "aktywny": 1},
                {"id": "E002", "imie": "Piotr", "nazwisko": "Wiśniewski", "pesel": "88111434567", "data_urodzenia": "1988-11-14", "adres_zamieszkania": "ul. Narutowicza 78", "kod_pocztowy": "90-003", "miasto": "Łódź", "telefon": "503-456-789", "email": "piotr.wisniewski@avalon.pl", "stanowisko": "Mechanik", "spolka": "Avalon Cars", "data_zatrudnienia": "2019-06-20", "status_zatrudnienia": "aktywny", "aktywny": 1}
            ]
            
            postepowania_data = [
                {"id": "P001", "pesel_pracownika": "85030512345", "komornik_id": "K001", "komornik_nazwa": "Adam Niegórski", "sygnatura_sprawy": "KM-123/2024", "data_wplywu": "2024-01-15", "status": "aktywne", "typ_postepowania": "zajęcie wynagrodzenia", "kwota_zadluzenia": 5000.00, "opis": "Zadłużenie z tytułu alimentów", "aktywny": 1},
                {"id": "P002", "pesel_pracownika": "88111434567", "komornik_id": "K002", "komornik_nazwa": "Anna Kowalska", "sygnatura_sprawy": "KM-456/2024", "data_wplywu": "2024-02-20", "status": "aktywne", "typ_postepowania": "zajęcie wierzytelności", "kwota_zadluzenia": 12000.00, "opis": "Dług kredytowy", "aktywny": 1}
            ]
            
            # Zapisz dane do arkuszy
            headers = komornicy_sheet.row_values(1)
            for data in komornicy_data:
                row_values = [data.get(header, '') for header in headers]
                komornicy_sheet.append_row(row_values)
            
            # Podobnie dla pracowników i postępowań
            pracownicy_spreadsheet = self.client.open_by_key(self.pracownicy_spreadsheet_id)
            try:
                pracownicy_sheet = pracownicy_spreadsheet.worksheet("pracownicy")
            except:
                pracownicy_sheet = pracownicy_spreadsheet.sheet1
                
            headers = pracownicy_sheet.row_values(1)
            for data in pracownicy_data:
                row_values = [data.get(header, '') for header in headers]
                pracownicy_sheet.append_row(row_values)
            
            postepowania_spreadsheet = self.client.open_by_key(self.postepowania_spreadsheet_id)
            try:
                postepowania_sheet = postepowania_spreadsheet.worksheet("postepowania")
            except:
                postepowania_sheet = postepowania_spreadsheet.sheet1
                
            headers = postepowania_sheet.row_values(1)
            for data in postepowania_data:
                row_values = [data.get(header, '') for header in headers]
                postepowania_sheet.append_row(row_values)
            
            print("✅ Dane testowe zostały dodane do Google Sheets")
            
            # Wymuś odświeżenie cache
            self.force_refresh_cache()
            
        except Exception as e:
            print(f"❌ Błąd wypełniania danymi testowymi: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # === Metody placeholder (do rozszerzenia w przyszłości) ===
    
    def add_bailiff(self, bailiff_data):
        """Wrapper dla add_new_bailiff"""
        return self.add_new_bailiff(
            bailiff_data.get('imie_nazwisko', ''),
            bailiff_data.get('plec', ''),
            bailiff_data.get('adres', ''),
            bailiff_data.get('kod_pocztowy', ''),
            bailiff_data.get('miasto', ''),
            bailiff_data.get('telefon', ''),
            bailiff_data.get('email', ''),
            bailiff_data.get('sad_rejonowy', '')
        )
    
    def add_employee(self, employee_data):
        """Dodawanie pracownika - TODO: implementacja z odświeżeniem cache"""
        print("⚠️ Dodawanie pracowników nie zostało jeszcze zaimplementowane w Smart Cache")
        return {"success": False, "message": "Funkcja w przygotowaniu"}
    
    def add_proceeding(self, proceeding_data):
        """Wrapper dla add_new_proceeding"""
        return self.add_new_proceeding(
            proceeding_data.get('pesel', ''),
            proceeding_data.get('komornik_data', {}),
            proceeding_data.get('sygnatura', ''),
            proceeding_data.get('data_wplywu', '')
        )
    
    def update_bailiff(self, bailiff_id, imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy):
        """Aktualizuj dane komornika w Google Sheets z automatycznym odświeżeniem cache"""
        try:
            if not self.komornicy_spreadsheet_id:
                print("❌ Brak ustawionego ID arkusza komorników")
                return False

            spreadsheet = self.client.open_by_key(self.komornicy_spreadsheet_id)
            try:
                komornicy_sheet = spreadsheet.worksheet("komornicy")
            except:
                komornicy_sheet = spreadsheet.sheet1
            
            # Znajdź wiersz z komornik o danym ID
            all_values = komornicy_sheet.get_all_values()
            if not all_values:
                return False
                
            headers = all_values[0]
            
            # Znajdź wiersz komornika
            row_index = None
            bailiff_id_str = str(bailiff_id)  # Konwertuj na string dla porównania
            
            for i, row in enumerate(all_values[1:], start=2):  # start=2 bo pomijamy header i gspread liczy od 1
                if len(row) > 0 and (row[0] == bailiff_id or str(row[0]) == bailiff_id_str):  # Porównaj oba typy
                    row_index = i
                    break
            
            if not row_index:
                print(f"❌ Nie znaleziono komornika o ID: {bailiff_id}")
                return False
            
            # Przygotuj dane do aktualizacji
            updated_data = {
                'imie_nazwisko': imie_nazwisko,
                'plec': plec,
                'adres': adres,
                'kod_pocztowy': kod_pocztowy,
                'miasto': miasto,
                'telefon': telefon,
                'email': email,
                'sad_rejonowy': sad_rejonowy
            }
            
            # Aktualizuj każdą komórkę
            for header, value in updated_data.items():
                if header in headers:
                    col_index = headers.index(header) + 1  # gspread używa indeksów od 1
                    komornicy_sheet.update_cell(row_index, col_index, value)
            
            print(f"✅ Zaktualizowano komornika {bailiff_id}")
            
            # Wymuś odświeżenie cache dla komorników
            self.force_refresh_cache('bailiffs')
            
            return True
        
        except Exception as e:
            print(f"❌ Błąd aktualizacji komornika: {str(e)}")
            return False
    
    def delete_bailiff(self, bailiff_id):
        """Usuń komornika z bazy danych (soft delete - ustaw aktywny = 0) z automatycznym odświeżeniem cache"""
        try:
            if not self.komornicy_spreadsheet_id:
                print("❌ Brak ustawionego ID arkusza komorników")
                return False

            spreadsheet = self.client.open_by_key(self.komornicy_spreadsheet_id)
            try:
                komornicy_sheet = spreadsheet.worksheet("komornicy")
            except:
                komornicy_sheet = spreadsheet.sheet1
            
            # Znajdź indeks wiersza
            row_index = self._find_record_index("komornicy", "id", bailiff_id)
            
            if row_index:
                # Znajdź indeks kolumny 'aktywny'
                headers = komornicy_sheet.row_values(1)
                active_col_index = headers.index("aktywny") + 1  # gspread używa indeksów od 1
                
                # Ustaw aktywny = 0
                komornicy_sheet.update_cell(row_index, active_col_index, 0)
                print(f"✅ Usunięto komornika o ID: {bailiff_id}")
                
                # Odśwież cache dla komorników
                self.force_refresh_cache('bailiffs')
                
                return True
            
            print(f"❌ Nie znaleziono komornika o ID: {bailiff_id}")
            return False
        
        except Exception as e:
            print(f"❌ Błąd usuwania komornika: {str(e)}")
            return False
    
    def __del__(self):
        """Cleanup przy usuwaniu obiektu"""
        if hasattr(self, '_stop_refresh'):
            self.stop_auto_refresh()
