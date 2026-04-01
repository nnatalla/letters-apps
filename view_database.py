#!/usr/bin/env python3
"""
Skrypt do przeglądania danych w bazie SQLite
"""
import sqlite3
import json
from datetime import datetime

def view_database():
    """Wyświetl wszystkie dane z bazy avalon_system.db"""
    
    try:
        # Połącz z bazą danych
        conn = sqlite3.connect('avalon_system.db')
        conn.row_factory = sqlite3.Row  # Umożliwia dostęp do kolumn po nazwach
        cursor = conn.cursor()
        
        print("="*80)
        print("📊 PRZEGLĄDANIE BAZY DANYCH AVALON SYSTEM")
        print("="*80)
        
        # Sprawdź jakie tabele istnieją
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n🗂️  TABELE W BAZIE DANYCH:")
        for table in tables:
            print(f"   • {table[0]}")
        
        # Wyświetl dane z każdej tabeli
        for table in tables:
            table_name = table[0]
            print(f"\n" + "="*60)
            print(f"📋 TABELA: {table_name.upper()}")
            print("="*60)
            
            # Pobierz strukturę tabeli
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("📝 STRUKTURA TABELI:")
            for col in columns:
                print(f"   • {col[1]} ({col[2]}) {'[PRIMARY KEY]' if col[5] else ''}")
            
            # Pobierz wszystkie dane
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()
            
            print(f"\n📊 DANE ({len(rows)} rekordów):")
            
            if rows:
                # Wyświetl nagłówki kolumn
                column_names = [description[0] for description in cursor.description]
                print("   " + " | ".join(f"{col:15}" for col in column_names))
                print("   " + "-" * (len(column_names) * 17))
                
                # Wyświetl dane
                for row in rows:
                    formatted_row = []
                    for value in row:
                        if value is None:
                            formatted_row.append("NULL".ljust(15))
                        else:
                            str_value = str(value)
                            if len(str_value) > 15:
                                str_value = str_value[:12] + "..."
                            formatted_row.append(str_value.ljust(15))
                    print("   " + " | ".join(formatted_row))
            else:
                print("   (Brak danych)")
        
        # Dodatkowe statystyki
        print(f"\n" + "="*60)
        print("📈 STATYSTYKI")
        print("="*60)
        
        # Statystyki komorników
        cursor.execute("SELECT COUNT(*) FROM komornicy WHERE aktywny = 1;")
        active_bailiffs = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM komornicy WHERE plec = 'm' AND aktywny = 1;")
        male_bailiffs = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM komornicy WHERE plec = 'k' AND aktywny = 1;")
        female_bailiffs = cursor.fetchone()[0]
        
        print(f"👨‍⚖️ Aktywni komornicy: {active_bailiffs}")
        print(f"   • Mężczyźni: {male_bailiffs}")
        print(f"   • Kobiety: {female_bailiffs}")
        
        # Statystyki pracowników
        cursor.execute("SELECT COUNT(*) FROM pracownicy;")
        total_employees = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM pracownicy WHERE status_zatrudnienia = 'aktywny';")
        active_employees = cursor.fetchone()[0]
        
        print(f"👥 Pracownicy: {total_employees}")
        print(f"   • Aktywni: {active_employees}")
        print(f"   • Nieaktywni: {total_employees - active_employees}")
        
        # Statystyki postępowań
        cursor.execute("SELECT COUNT(*) FROM postepowania;")
        total_proceedings = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM postepowania WHERE status = 'aktywne';")
        active_proceedings = cursor.fetchone()[0]
        
        print(f"⚖️  Postępowania: {total_proceedings}")
        print(f"   • Aktywne: {active_proceedings}")
        print(f"   • Zakończone: {total_proceedings - active_proceedings}")
        
        print(f"\n🕒 Czas wygenerowania raportu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
    except sqlite3.Error as e:
        print(f"❌ Błąd bazy danych: {e}")
    except Exception as e:
        print(f"❌ Nieoczekiwany błąd: {e}")
    finally:
        if conn:
            conn.close()

def search_by_pesel(pesel):
    """Wyszukaj dane pracownika po PESEL"""
    try:
        conn = sqlite3.connect('avalon_system.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"\n🔍 WYSZUKIWANIE PRACOWNIKA - PESEL: {pesel}")
        print("="*50)
        
        # Sprawdź pracownika
        cursor.execute("SELECT * FROM pracownicy WHERE pesel = ?", (pesel,))
        employee = cursor.fetchone()
        
        if employee:
            print("👤 DANE PRACOWNIKA:")
            for key in employee.keys():
                print(f"   {key}: {employee[key]}")
            
            # Sprawdź postępowania
            cursor.execute("SELECT * FROM postepowania WHERE pesel_dluznika = ?", (pesel,))
            proceedings = cursor.fetchall()
            
            if proceedings:
                print(f"\n⚖️  POSTĘPOWANIA ({len(proceedings)}):")
                for proc in proceedings:
                    print(f"   • ID: {proc['id']}, Komornik: {proc['id_komornika']}, Status: {proc['status']}")
                    print(f"     Sygnatura: {proc['sygnatura_sprawy']}")
            else:
                print("\n⚖️  Brak postępowań dla tego pracownika")
        else:
            print("❌ Nie znaleziono pracownika o podanym PESEL")
            
    except Exception as e:
        print(f"❌ Błąd: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Jeśli podano argument, traktuj jako PESEL do wyszukania
        search_by_pesel(sys.argv[1])
    else:
        # Wyświetl całą bazę
        view_database()
