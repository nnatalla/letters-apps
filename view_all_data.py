#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pełny przegląd danych w bazie avalon_system.db
"""

import sqlite3
import os
from datetime import datetime

def main():
    db_path = 'avalon_system.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Plik bazy danych '{db_path}' nie istnieje!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("📊 PEŁNY PRZEGLĄD BAZY DANYCH AVALON")
    print("=" * 60)
    
    # === KOMORNICI ===
    print("\n🏛️  KOMORNICI")
    print("-" * 50)
    
    cursor.execute('SELECT COUNT(*) FROM komornicy')
    total_bailiffs = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM komornicy WHERE aktywny = 1')
    active_bailiffs = cursor.fetchone()[0]
    
    print(f"Łączna liczba komorników: {total_bailiffs}")
    print(f"   • Aktywni: {active_bailiffs}")
    print(f"   • Nieaktywni: {total_bailiffs - active_bailiffs}")
    
    cursor.execute('''
        SELECT id, imie_nazwisko, miasto, aktywny 
        FROM komornicy 
        ORDER BY aktywny DESC, id
    ''')
    bailiffs = cursor.fetchall()
    
    print("\nLista komorników:")
    for i, (id_kom, imie_nazwisko, miasto, aktywny) in enumerate(bailiffs, 1):
        status = "✅ AKTYWNY" if aktywny else "❌ NIEAKTYWNY"
        print(f"  {i:2d}. ID:{id_kom:2d} {imie_nazwisko:25s} ({miasto:10s}) {status}")
    
    # === PRACOWNICY ===
    print(f"\n👥 PRACOWNICY")
    print("-" * 50)
    
    cursor.execute('SELECT COUNT(*) FROM pracownicy')
    total_employees = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM pracownicy WHERE aktywny = 1')
    active_employees = cursor.fetchone()[0]
    
    print(f"Łączna liczba pracowników: {total_employees}")
    print(f"   • Aktywni: {active_employees}")
    print(f"   • Nieaktywni: {total_employees - active_employees}")
    
    cursor.execute('''
        SELECT id, imie, nazwisko, spolka, stanowisko, aktywny 
        FROM pracownicy 
        ORDER BY aktywny DESC, id
    ''')
    employees = cursor.fetchall()
    
    print("\nLista pracowników:")
    for i, (id_emp, imie, nazwisko, spolka, stanowisko, aktywny) in enumerate(employees, 1):
        status = "✅ AKTYWNY" if aktywny else "❌ NIEAKTYWNY"
        print(f"  {i:2d}. ID:{id_emp:2d} {imie} {nazwisko:15s} ({spolka:12s}) {stanowisko:15s} {status}")
    
    # === POSTĘPOWANIA ===
    print(f"\n⚖️  POSTĘPOWANIA KOMORNICZE")
    print("-" * 50)
    
    cursor.execute('SELECT COUNT(*) FROM postepowania')
    total_proceedings = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM postepowania WHERE status = "aktywne"')
    active_proceedings = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM postepowania WHERE status = "zakończone"')
    closed_proceedings = cursor.fetchone()[0]
    
    print(f"Łączna liczba postępowań: {total_proceedings}")
    print(f"   • Aktywne: {active_proceedings}")
    print(f"   • Zakończone: {closed_proceedings}")
    
    # Statystyki po PESEL (zbieg komorniczy)
    cursor.execute('''
        SELECT pesel_pracownika, COUNT(*) as liczba_postepowań
        FROM postepowania 
        WHERE status = "aktywne"
        GROUP BY pesel_pracownika
        HAVING COUNT(*) > 1
        ORDER BY liczba_postepowań DESC
    ''')
    conflicts = cursor.fetchall()
    
    if conflicts:
        print(f"\n🚨 ZBIEGI KOMORNICZE (aktywne postępowania):")
        for pesel, count in conflicts:
            # Pobierz imię i nazwisko pracownika
            cursor.execute('''
                SELECT imie, nazwisko FROM pracownicy WHERE pesel = ?
            ''', (pesel,))
            worker = cursor.fetchone()
            
            if worker:
                imie, nazwisko = worker
                print(f"   • {imie} {nazwisko} (PESEL: {pesel}) - {count} komorników")
            else:
                print(f"   • PESEL: {pesel} - {count} komorników (pracownik nie znaleziony)")
    
    conn.close()
    
    print(f"\n🕒 Czas wygenerowania raportu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
