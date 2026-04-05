import sqlite3
import os
import sys
from datetime import datetime, timedelta
import random

# Wymuszenie UTF-8 na stdout (Windows cp1250 nie obsługuje emoji)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class DatabaseManager:
    def __init__(self, db_path='avalon_system.db'):
        self.db_path = db_path
        self.init_database()
        
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Inicjalizacja bazy danych z tabelami"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela komorników
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS komornicy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imie_nazwisko TEXT NOT NULL,
                plec TEXT NOT NULL DEFAULT 'm',
                adres TEXT NOT NULL,
                kod_pocztowy TEXT NOT NULL,
                miasto TEXT NOT NULL,
                telefon TEXT,
                email TEXT,
                sad_rejonowy TEXT,
                aktywny BOOLEAN DEFAULT 1,
                data_dodania TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela pracowników
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pracownicy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imie TEXT NOT NULL,
                nazwisko TEXT NOT NULL,
                pesel TEXT UNIQUE NOT NULL,
                data_urodzenia DATE,
                adres_zamieszkania TEXT,
                kod_pocztowy TEXT,
                miasto TEXT,
                telefon TEXT,
                email TEXT,
                stanowisko TEXT,
                spolka TEXT NOT NULL,
                data_zatrudnienia DATE,
                data_zwolnienia DATE NULL,
                status_zatrudnienia TEXT DEFAULT 'aktywny',
                numer_rachunku TEXT,
                typ_umowy TEXT,
                aktywny BOOLEAN DEFAULT 1,
                data_dodania TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela postępowań komorniczych
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS postepowania (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesel_pracownika TEXT NOT NULL,
                komornik_id INTEGER,
                komornik_nazwa TEXT NOT NULL,
                sygnatura_sprawy TEXT NOT NULL,
                data_wplywu DATE NOT NULL,
                data_zakonczenia DATE NULL,
                status TEXT DEFAULT 'aktywne',
                typ_postepowania TEXT,
                kwota_zadluzenia DECIMAL(10,2),
                opis TEXT,
                aktywny BOOLEAN DEFAULT 1,
                data_dodania TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (komornik_id) REFERENCES komornicy (id),
                FOREIGN KEY (pesel_pracownika) REFERENCES pracownicy (pesel)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[OK] Baza danych zainicjalizowana")
    
    def populate_test_data(self):
        """Wypełnienie bazy danych testowymi danymi"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy dane już istnieją
        cursor.execute("SELECT COUNT(*) FROM komornicy")
        if cursor.fetchone()[0] > 0:
            print("🔄 Dane testowe już istnieją, pomijam wypełnianie")
            conn.close()
            return
        
        # Dane testowe komorników (rozszerzona lista)
        komornicy_data = [
            ("Adam Niegórski", "m", "ul. Piotrkowska 123", "90-001", "Łódź", "42-123-45-67", "a.niegorski@komornik.pl", "Sąd Rejonowy w Łodzi"),
            ("Anna Kowalska", "k", "ul. Kilińskiego 45", "00-001", "Warszawa", "22-987-65-43", "a.kowalska@komornik.pl", "Sąd Rejonowy w Warszawie"),
            ("Marek Nowak", "m", "ul. Słowackiego 67", "30-001", "Kraków", "12-345-67-89", "m.nowak@komornik.pl", "Sąd Rejonowy w Krakowie"),
            ("Katarzyna Wiśniewska", "k", "ul. Mickiewicza 89", "80-001", "Gdańsk", "58-123-45-67", "k.wisniewska@komornik.pl", "Sąd Rejonowy w Gdańsku"),
            ("Tomasz Wójcik", "m", "ul. Sienkiewicza 21", "60-001", "Poznań", "61-234-56-78", "t.wojcik@komornik.pl", "Sąd Rejonowy w Poznaniu"),
            ("Barbara Lewandowska", "k", "ul. Chopina 33", "50-001", "Wrocław", "71-345-67-89", "b.lewandowska@komornik.pl", "Sąd Rejonowy we Wrocławiu"),
            ("Piotr Kowalczyk", "m", "ul. Marszałkowska 156", "00-002", "Warszawa", "22-876-54-32", "p.kowalczyk@komornik.pl", "Sąd Rejonowy w Warszawie"),
            ("Magdalena Szymańska", "k", "ul. Floriańska 12", "31-021", "Kraków", "12-456-78-90", "m.szymanska@komornik.pl", "Sąd Rejonowy w Krakowie"),
            ("Jan Kaczmarek", "m", "ul. Długa 44", "80-827", "Gdańsk", "58-234-56-78", "j.kaczmarek@komornik.pl", "Sąd Rejonowy w Gdańsku"),
            ("Agnieszka Zawadzka", "k", "ul. Półwiejska 47", "61-888", "Poznań", "61-345-67-89", "a.zawadzka@komornik.pl", "Sąd Rejonowy w Poznaniu"),
            ("Robert Jankowski", "m", "ul. Świdnicka 53", "50-068", "Wrocław", "71-456-78-90", "r.jankowski@komornik.pl", "Sąd Rejonowy we Wrocławiu"),
            ("Monika Zielińska", "k", "ul. Żeromskiego 115", "90-549", "Łódź", "42-234-56-78", "m.zielinska@komornik.pl", "Sąd Rejonowy w Łodzi"),
            ("Krzysztof Woźniak", "m", "ul. Nowy Świat 64", "00-357", "Warszawa", "22-765-43-21", "k.wozniak@komornik.pl", "Sąd Rejonowy w Warszawie"),
            ("Ewa Dąbrowska", "k", "ul. Grodzka 29", "31-044", "Kraków", "12-567-89-01", "e.dabrowska@komornik.pl", "Sąd Rejonowy w Krakowie"),
            ("Paweł Mazur", "m", "ul. Wałowa 13", "80-858", "Gdańsk", "58-345-67-89", "p.mazur@komornik.pl", "Sąd Rejonowy w Gdańsku"),
            ("Joanna Pawlak", "k", "ul. Stary Rynek 78", "61-772", "Poznań", "61-456-78-90", "j.pawlak@komornik.pl", "Sąd Rejonowy w Poznaniu"),
            ("Michał Król", "m", "ul. Oławska 19", "50-123", "Wrocław", "71-567-89-01", "m.krol@komornik.pl", "Sąd Rejonowy we Wrocławiu"),
            ("Aleksandra Wróbel", "k", "ul. Narutowicza 88", "90-145", "Łódź", "42-345-67-89", "a.wrobel@komornik.pl", "Sąd Rejonowy w Łodzi"),
            ("Grzegorz Adamczyk", "m", "ul. Krakowskie Przedmieście 26/28", "00-927", "Warszawa", "22-654-32-10", "g.adamczyk@komornik.pl", "Sąd Rejonowy w Warszawie"),
            ("Dorota Sikora", "k", "ul. Karmelicka 45", "31-128", "Kraków", "12-678-90-12", "d.sikora@komornik.pl", "Sąd Rejonowy w Krakowie"),
            ("Łukasz Bąk", "m", "ul. Długie Pobrzeże 67", "80-888", "Gdańsk", "58-456-78-90", "l.bak@komornik.pl", "Sąd Rejonowy w Gdańsku"),
            ("Marta Głowacka", "k", "ul. Roosevelta 122", "60-829", "Poznań", "61-567-89-01", "m.glowacka@komornik.pl", "Sąd Rejonowy w Poznaniu"),
            ("Sebastian Walczak", "m", "ul. Kuźnicza 88", "50-138", "Wrocław", "71-678-90-12", "s.walczak@komornik.pl", "Sąd Rejonowy we Wrocławiu"),
            ("Karolina Dudek", "k", "ul. Rewolucji 1905 r. 45", "90-215", "Łódź", "42-456-78-90", "k.dudek@komornik.pl", "Sąd Rejonowy w Łodzi"),
            ("Marcin Przybylski", "m", "ul. Prosta 89", "00-838", "Warszawa", "22-543-21-09", "m.przybylski@komornik.pl", "Sąd Rejonowy w Warszawie")
        ]
        
        cursor.executemany('''
            INSERT INTO komornicy (imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', komornicy_data)
        
        # Dane testowe pracowników
        pracownicy_data = [
            ("Jan", "Kowalski", "85030512345", "1985-03-05", "ul. Mickiewicza 12", "90-001", "Łódź", "501-234-567", "jan.kowalski@avalon.pl", "Kierowca", "Avalon Taxi", "2020-01-15", None, "aktywny", "PL61109010140000071219812874", "umowa o pracę"),
            ("Anna", "Nowak", "92081823456", "1992-08-18", "ul. Piotrkowska 45", "90-002", "Łódź", "502-345-678", "anna.nowak@avalon.pl", "Dispatcher", "Avalon Logistics", "2021-03-10", None, "aktywny", "PL27114020040000300201355387", "umowa o pracę"),
            ("Piotr", "Wiśniewski", "88111434567", "1988-11-14", "ul. Narutowicza 78", "90-003", "Łódź", "503-456-789", "piotr.wisniewski@avalon.pl", "Mechanik", "Avalon Cars", "2019-06-20", None, "aktywny", "PL83124000050000400069831234", "umowa o pracę"),
            ("Maria", "Wójcik", "90040545678", "1990-04-05", "ul. Żeromskiego 23", "90-004", "Łódź", "504-567-890", "maria.wojcik@avalon.pl", "Księgowa", "Avalon Logistics", "2020-09-01", None, "aktywny", "PL42109024020000220291621234", "umowa o pracę"),
            ("Tomasz", "Kowalczyk", "87070656789", "1987-07-06", "ul. Sienkiewicza 56", "90-005", "Łódź", "505-678-901", "tomasz.kowalczyk@avalon.pl", "Kierowca", "Avalon Taxi", "2018-12-10", None, "aktywny", "PL61109010140000071219812111", "umowa o pracę"),
            ("Katarzyna", "Lewandowska", "94122767890", "1994-12-27", "ul. Chopina 89", "90-006", "Łódź", "506-789-012", "katarzyna.lewandowska@avalon.pl", "Sprzedawca", "Avalon Cars", "2022-02-14", None, "aktywny", "PL27114020040000300201355999", "umowa zlecenie"),
            ("Marcin", "Dąbrowski", "89090878901", "1989-09-08", "ul. Kościuszki 34", "90-007", "Łódź", "507-890-123", "marcin.dabrowski@avalon.pl", "Logistyk", "Avalon Logistics", "2021-07-30", None, "aktywny", "PL83124000050000400069834567", "umowa o pracę"),
            ("Joanna", "Zielińska", "91051989012", "1991-05-19", "ul. Legionów 67", "90-008", "Łódź", "508-901-234", "joanna.zielinska@avalon.pl", "Manager", "Avalon Cars", "2020-04-18", None, "aktywny", "PL42109024020000220291627890", "umowa o pracę"),
            ("Adam", "Szymański", "86031090123", "1986-03-10", "ul. Próchnika 12", "90-009", "Łódź", "509-012-345", "adam.szymanski@avalon.pl", "Kierowca", "Avalon Taxi", "2019-11-05", "2023-08-15", "zwolniony", "PL61109010140000071219815432", "umowa o pracę"),
            ("Ewa", "Mazur", "93062201234", "1993-06-22", "ul. Tuwima 45", "90-010", "Łódź", "510-123-456", "ewa.mazur@avalon.pl", "Analityk", "Avalon Logistics", "2022-01-09", None, "aktywny", "PL27114020040000300201358765", "umowa zlecenie"),
            ("Paweł", "Król", "85121112345", "1985-12-11", "ul. Roosevelta 78", "90-011", "Łódź", "511-234-567", "pawel.krol@avalon.pl", "Kierowca", "Avalon Taxi", "2020-08-22", None, "aktywny", "PL83124000050000400069837654", "najem pojazdu"),
            ("Magdalena", "Pawlak", "90010213456", "1990-01-02", "ul. Wólczańska 23", "90-012", "Łódź", "512-345-678", "magdalena.pawlak@avalon.pl", "Sekretarka", "Avalon Cars", "2021-05-17", None, "aktywny", "PL42109024020000220291629876", "umowa o pracę"),
            ("Krzysztof", "Grabowski", "88080814567", "1988-08-08", "ul. Armii Krajowej 56", "90-013", "Łódź", "513-456-789", "krzysztof.grabowski@avalon.pl", "Dispatcher", "Avalon Logistics", "2019-09-30", None, "aktywny", "PL61109010140000071219819876", "umowa o pracę"),
            ("Beata", "Witkowska", "92040515678", "1992-04-05", "ul. Politechniki 89", "90-014", "Łódź", "514-567-890", "beata.witkowska@avalon.pl", "HR Specialist", "Avalon Cars", "2022-03-12", None, "aktywny", "PL27114020040000300201359999", "umowa o pracę"),
            ("Rafał", "Krawczyk", "87111916789", "1987-11-19", "ul. Jaracza 34", "90-015", "Łódź", "515-678-901", "rafal.krawczyk@avalon.pl", "Kierowca", "Avalon Taxi", "2018-07-25", None, "aktywny", "PL83124000050000400069831111", "najem pojazdu")
        ]
        
        cursor.executemany('''
            INSERT INTO pracownicy (imie, nazwisko, pesel, data_urodzenia, adres_zamieszkania, kod_pocztowy, 
                                    miasto, telefon, email, stanowisko, spolka, data_zatrudnienia, 
                                    data_zwolnienia, status_zatrudnienia, numer_rachunku, typ_umowy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', pracownicy_data)
        
        # Dane testowe postępowań komorniczych (symulujemy różne scenariusze)
        postepowania_data = []
        
        # Scenariusz 1: Pojedyncze postępowania
        single_cases = [
            ("85030512345", 1, "Adam Niegórski", "KM-123/2024", "2024-01-15", None, "aktywne", "zajęcie wynagrodzenia", 5000.00, "Zadłużenie z tytułu alimentów"),
            ("92081823456", 3, "Marek Nowak", "KM-456/2024", "2024-02-20", None, "aktywne", "zajęcie wierzytelności", 12000.00, "Dług kredytowy"),
            ("88111434567", 5, "Tomasz Wójcik", "KM-789/2024", "2024-03-10", "2024-07-15", "zakończone", "zajęcie rachunku", 3000.00, "Kary administracyjne"),
            ("87070656789", 8, "Magdalena Szymańska", "KM-321/2024", "2024-04-05", None, "aktywne", "zajęcie wynagrodzenia", 8000.00, "Zadłużenie podatkowe")
        ]
        
        # Scenariusz 2: Zbieg komorniczy - Jan Kowalski ma dwóch komorników
        zbieg_cases_jan = [
            ("85030512345", 2, "Anna Kowalska", "KM-111/2024", "2024-01-10", None, "aktywne", "zajęcie wynagrodzenia", 15000.00, "Zadłużenie kredytowe bank A"),
            ("85030512345", 7, "Piotr Kowalczyk", "KM-222/2024", "2024-02-05", None, "aktywne", "zajęcie wynagrodzenia", 7500.00, "Zadłużenie kredytowe bank B")
        ]
        
        # Scenariusz 3: Zbieg komorniczy - Piotr Wiśniewski ma trzech komorników  
        zbieg_cases_piotr = [
            ("88111434567", 4, "Katarzyna Wiśniewska", "KM-333/2024", "2024-01-20", None, "aktywne", "zajęcie wierzytelności", 20000.00, "Zadłużenie z tytułu umowy"),
            ("88111434567", 9, "Jan Kaczmarek", "KM-444/2024", "2024-03-01", None, "aktywne", "zajęcie wynagrodzenia", 9000.00, "Zadłużenie alimentacyjne"),
            ("88111434567", 12, "Monika Zielińska", "KM-555/2024", "2024-03-15", None, "aktywne", "zajęcie rachunku", 4500.00, "Kary i grzywny")
        ]
        
        # Scenariusz 4: Historyczne postępowania zakończone
        historical_cases = [
            ("90040545678", 6, "Barbara Lewandowska", "KM-666/2023", "2023-06-15", "2023-12-20", "zakończone", "zajęcie wynagrodzenia", 6000.00, "Spłacone w całości"),
            ("94122767890", 10, "Agnieszka Zawadzka", "KM-777/2023", "2023-08-10", "2024-01-30", "zakończone", "zajęcie rachunku", 2500.00, "Ugoda zawarta")
        ]
        
        # Łączenie wszystkich postępowań
        all_cases = single_cases + zbieg_cases_jan + zbieg_cases_piotr + historical_cases
        postepowania_data.extend(all_cases)
        
        cursor.executemany('''
            INSERT INTO postepowania (pesel_pracownika, komornik_id, komornik_nazwa, sygnatura_sprawy, 
                                      data_wplywu, data_zakonczenia, status, typ_postepowania, 
                                      kwota_zadluzenia, opis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', postepowania_data)
        
        conn.commit()
        conn.close()
        
        print("✅ Baza danych została wypełniona danymi testowymi:")
        print(f"   📋 {len(komornicy_data)} komorników")
        print(f"   👥 {len(pracownicy_data)} pracowników")
        print(f"   ⚖️ {len(postepowania_data)} postępowań komorniczych")
        print("   🔄 Zbiegi komornicze: Jan Kowalski (2 komorników), Piotr Wiśniewski (3 komorników)")
    
    def get_employee_by_pesel(self, pesel):
        """Pobierz dane pracownika na podstawie PESEL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM pracownicy WHERE pesel = ? AND aktywny = 1
        ''', (pesel,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'imie': result[1],
                'nazwisko': result[2],
                'pesel': result[3],
                'data_urodzenia': result[4],
                'adres_zamieszkania': result[5],
                'kod_pocztowy': result[6],
                'miasto': result[7],
                'telefon': result[8],
                'email': result[9],
                'stanowisko': result[10],
                'spolka': result[11],
                'data_zatrudnienia': result[12],
                'data_zwolnienia': result[13],
                'status_zatrudnienia': result[14],
                'numer_rachunku': result[15],
                'typ_umowy': result[16]
            }
        return None
    
    def get_bailiff_proceedings(self, pesel):
        """Pobierz wszystkie postępowania komornicze dla danego PESEL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, k.imie_nazwisko, k.adres, k.miasto, k.telefon, k.email 
            FROM postepowania p
            LEFT JOIN komornicy k ON p.komornik_id = k.id
            WHERE p.pesel_pracownika = ? AND p.aktywny = 1
            ORDER BY p.data_wplywu DESC
        ''', (pesel,))
        
        results = cursor.fetchall()
        conn.close()
        
        proceedings = []
        for result in results:
            proceedings.append({
                'id': result[0],
                'pesel_pracownika': result[1],
                'komornik_id': result[2],
                'komornik_nazwa': result[3],
                'sygnatura_sprawy': result[4],
                'data_wplywu': result[5],
                'data_zakonczenia': result[6],
                'status': result[7],
                'typ_postepowania': result[8],
                'kwota_zadluzenia': result[9],
                'opis': result[10],
                'bailiff_details': {
                    'imie_nazwisko': result[13] if result[13] else result[3],  # k.imie_nazwisko lub komornik_nazwa
                    'adres': result[14] if result[14] else '',                # k.adres
                    'miasto': result[15] if result[15] else '',               # k.miasto
                    'telefon': result[16] if result[16] else '',              # k.telefon
                    'email': result[17] if result[17] else ''                 # k.email
                }
            })
        
        return proceedings
    
    def detect_bailiff_conflict(self, pesel):
        """Wykryj czy istnieje zbieg komorniczy dla danego PESEL"""
        active_proceedings = self.get_bailiff_proceedings(pesel)
        active_count = len([p for p in active_proceedings if p['status'] == 'aktywne'])
        
        return {
            'is_conflict': active_count > 0,
            'active_proceedings_count': active_count,
            'proceedings': active_proceedings
        }
    
    def get_all_bailiffs(self):
        """Pobierz wszystkich aktywnych komorników"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM komornicy WHERE aktywny = 1 ORDER BY imie_nazwisko
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        bailiffs = []
        for result in results:
            bailiffs.append({
                'id': result[0],
                'imie_nazwisko': result[1],
                'plec': result[2],
                'adres': result[3],
                'kod_pocztowy': result[4],
                'miasto': result[5],
                'telefon': result[6],
                'email': result[7],
                'sad_rejonowy': result[8]
            })
        
        return bailiffs
    
    def get_bailiff_by_name(self, imie_nazwisko):
        """Sprawdź czy komornik o danym imieniu i nazwisku już istnieje"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM komornicy WHERE imie_nazwisko = ? AND aktywny = 1
        ''', (imie_nazwisko,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'imie_nazwisko': result[1],
                'plec': result[2],
                'adres': result[3],
                'kod_pocztowy': result[4],
                'miasto': result[5],
                'telefon': result[6],
                'email': result[7],
                'sad_rejonowy': result[8]
            }
        return None
    
    def get_bailiff_by_id(self, bailiff_id):
        """Pobierz komornika po ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM komornicy WHERE id = ? AND aktywny = 1
        ''', (bailiff_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'imie_nazwisko': result[1],
                'plec': result[2],
                'adres': result[3],
                'kod_pocztowy': result[4],
                'miasto': result[5],
                'telefon': result[6],
                'email': result[7],
                'sad_rejonowy': result[8]
            }
        return None
    
    def add_new_bailiff(self, imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon='', email='', sad_rejonowy=''):
        """Dodaj nowego komornika do bazy danych"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO komornicy (imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy))
        
        bailiff_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return bailiff_id
    
    def delete_bailiff(self, bailiff_id):
        """Usuń komornika z bazy danych (soft delete - ustaw aktywny = 0)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE komornicy SET aktywny = 0 WHERE id = ?
        ''', (bailiff_id,))
        
        affected_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected_rows > 0
    
    def update_bailiff(self, bailiff_id, imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy):
        """Aktualizuj dane komornika"""
        print(f"🔧 update_bailiff wywołane z parametrami:")
        print(f"   bailiff_id: {bailiff_id} (typ: {type(bailiff_id)})")
        print(f"   imie_nazwisko: {imie_nazwisko}")
        print(f"   plec: {plec}")
        print(f"   adres: {adres}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy rekord istnieje przed aktualizacją
        cursor.execute('SELECT * FROM komornicy WHERE id = ? AND aktywny = 1', (bailiff_id,))
        existing = cursor.fetchone()
        print(f"🔧 Rekord przed aktualizacją: {existing}")
        
        cursor.execute('''
            UPDATE komornicy 
            SET imie_nazwisko = ?, plec = ?, adres = ?, kod_pocztowy = ?, 
                miasto = ?, telefon = ?, email = ?, sad_rejonowy = ?
            WHERE id = ? AND aktywny = 1
        ''', (imie_nazwisko, plec, adres, kod_pocztowy, miasto, telefon, email, sad_rejonowy, bailiff_id))
        
        affected_rows = cursor.rowcount
        print(f"🔧 Liczba zaktualizowanych wierszy: {affected_rows}")
        
        # Sprawdź czy rekord został zaktualizowany
        cursor.execute('SELECT * FROM komornicy WHERE id = ? AND aktywny = 1', (bailiff_id,))
        updated = cursor.fetchone()
        print(f"🔧 Rekord po aktualizacji: {updated}")
        
        conn.commit()
        conn.close()
        
        return affected_rows > 0
    
    def add_new_proceeding(self, pesel, komornik_data, sygnatura, data_wplywu):
        """Dodaj nowe postępowanie komornicze"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO postepowania (pesel_pracownika, komornik_nazwa, sygnatura_sprawy, data_wplywu, status)
            VALUES (?, ?, ?, ?, 'aktywne')
        ''', (pesel, komornik_data, sygnatura, data_wplywu))
        
        proceeding_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return proceeding_id

# Inicjalizacja globalnej instancji bazy danych
db = DatabaseManager()
