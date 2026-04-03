import os
import sqlite3
from datetime import datetime, date
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# =========================
# Konfiguracja bazy
# =========================
def get_database_uri() -> str:
    """DATABASE_URL -> PostgreSQL, fallback -> SQLite."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url
    return "sqlite:///avalon_system.db"


def get_engine_options() -> dict:
    """Connection pooling tylko dla PostgreSQL."""
    database_url = os.getenv("DATABASE_URL", "").lower()
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        return {
            "pool_size": 10,
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
    return {"connect_args": {"check_same_thread": False}}


def init_db(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = get_engine_options()
    db.init_app(app)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    """Włączenie FK dla SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# =========================
# Modele
# =========================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Profil
    display_name = db.Column(db.String(100), nullable=True)

    # Plan / limity
    plan = db.Column(db.String(10), nullable=False, default="free")
    letters_used = db.Column(db.Integer, nullable=False, default=0)
    letters_limit = db.Column(db.Integer, nullable=False, default=50)

    # Ustawienia
    theme = db.Column(db.String(10), nullable=False, default="light")
    email_notifications = db.Column(db.Boolean, nullable=False, default=True)

    # Konto
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    activation_token = db.Column(db.String(64), nullable=True, unique=True, index=True)
    reset_password_token = db.Column(db.String(64), nullable=True, unique=True, index=True)
    reset_password_expires = db.Column(db.DateTime, nullable=True)

    senders = db.relationship("Sender", back_populates="user", cascade="all, delete-orphan")
    generated_letters = db.relationship("GeneratedLetter", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "plan": self.plan,
            "letters_used": self.letters_used,
            "letters_limit": self.letters_limit,
            "theme": self.theme,
            "email_notifications": self.email_notifications,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Sender(db.Model):
    __tablename__ = "senders"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nazwa = db.Column(db.String(255), nullable=False)
    adres = db.Column(db.String(255))
    miasto = db.Column(db.String(100))
    kod_pocztowy = db.Column(db.String(20))
    telefon = db.Column(db.String(50))
    email = db.Column(db.String(255))

    user = db.relationship("User", back_populates="senders")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "nazwa": self.nazwa,
            "adres": self.adres,
            "miasto": self.miasto,
            "kod_pocztowy": self.kod_pocztowy,
            "telefon": self.telefon,
            "email": self.email,
        }


class GeneratedLetter(db.Model):
    __tablename__ = "generated_letters"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    subtype = db.Column(db.String(100), nullable=True)
    html_content = db.Column(db.Text, nullable=False)
    sender_name = db.Column(db.String(255), nullable=True)
    recipient_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    file_pdf = db.Column(db.String(500), nullable=True)
    file_doc = db.Column(db.String(500), nullable=True)

    user = db.relationship("User", back_populates="generated_letters")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "document_type": self.document_type,
            "subtype": self.subtype,
            "html_content": self.html_content,
            "sender_name": self.sender_name,
            "recipient_name": self.recipient_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "file_pdf": self.file_pdf,
            "file_doc": self.file_doc,
        }


class Plan(db.Model):
    __tablename__ = "plans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(10), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)    # cena w groszach
    letters_limit = db.Column(db.Integer, nullable=False, default=50)
    description = db.Column(db.String(500), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "price": self.price,
            "price_pln": self.price / 100,
            "letters_limit": self.letters_limit,
            "description": self.description,
        }


class Komornik(db.Model):
    __tablename__ = "komornicy"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    imie_nazwisko = db.Column(db.Text, nullable=False)
    plec = db.Column(db.Text, nullable=False, default="m")
    adres = db.Column(db.Text, nullable=False)
    kod_pocztowy = db.Column(db.Text, nullable=False)
    miasto = db.Column(db.Text, nullable=False)
    telefon = db.Column(db.Text)
    email = db.Column(db.Text)
    sad_rejonowy = db.Column(db.Text)
    aktywny = db.Column(db.Boolean, default=True)
    data_dodania = db.Column(db.DateTime, default=datetime.utcnow)

    postepowania = db.relationship("Postepowanie", back_populates="komornik")

    def to_dict(self):
        return {
            "id": self.id,
            "imie_nazwisko": self.imie_nazwisko,
            "plec": self.plec,
            "adres": self.adres,
            "kod_pocztowy": self.kod_pocztowy,
            "miasto": self.miasto,
            "telefon": self.telefon,
            "email": self.email,
            "sad_rejonowy": self.sad_rejonowy,
            "aktywny": self.aktywny,
            "data_dodania": self.data_dodania.isoformat() if self.data_dodania else None,
        }


class Pracownik(db.Model):
    __tablename__ = "pracownicy"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    imie = db.Column(db.Text, nullable=False)
    nazwisko = db.Column(db.Text, nullable=False)
    pesel = db.Column(db.Text, unique=True, nullable=False, index=True)
    data_urodzenia = db.Column(db.Date)
    adres_zamieszkania = db.Column(db.Text)
    kod_pocztowy = db.Column(db.Text)
    miasto = db.Column(db.Text)
    telefon = db.Column(db.Text)
    email = db.Column(db.Text)
    stanowisko = db.Column(db.Text)
    spolka = db.Column(db.Text, nullable=False)
    data_zatrudnienia = db.Column(db.Date)
    data_zwolnienia = db.Column(db.Date, nullable=True)
    status_zatrudnienia = db.Column(db.Text, default="aktywny")
    numer_rachunku = db.Column(db.Text)
    typ_umowy = db.Column(db.Text)
    aktywny = db.Column(db.Boolean, default=True)
    data_dodania = db.Column(db.DateTime, default=datetime.utcnow)

    postepowania = db.relationship(
        "Postepowanie",
        back_populates="pracownik",
        primaryjoin="Pracownik.pesel==foreign(Postepowanie.pesel_pracownika)",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "imie": self.imie,
            "nazwisko": self.nazwisko,
            "pesel": self.pesel,
            "data_urodzenia": self.data_urodzenia.isoformat() if self.data_urodzenia else None,
            "adres_zamieszkania": self.adres_zamieszkania,
            "kod_pocztowy": self.kod_pocztowy,
            "miasto": self.miasto,
            "telefon": self.telefon,
            "email": self.email,
            "stanowisko": self.stanowisko,
            "spolka": self.spolka,
            "data_zatrudnienia": self.data_zatrudnienia.isoformat() if self.data_zatrudnienia else None,
            "data_zwolnienia": self.data_zwolnienia.isoformat() if self.data_zwolnienia else None,
            "status_zatrudnienia": self.status_zatrudnienia,
            "numer_rachunku": self.numer_rachunku,
            "typ_umowy": self.typ_umowy,
            "aktywny": self.aktywny,
            "data_dodania": self.data_dodania.isoformat() if self.data_dodania else None,
        }


class Postepowanie(db.Model):
    __tablename__ = "postepowania"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pesel_pracownika = db.Column(db.Text, db.ForeignKey("pracownicy.pesel"), nullable=False, index=True)
    komornik_id = db.Column(db.Integer, db.ForeignKey("komornicy.id"), nullable=True)
    komornik_nazwa = db.Column(db.Text, nullable=False)
    sygnatura_sprawy = db.Column(db.Text, nullable=False)
    data_wplywu = db.Column(db.Date, nullable=False)
    data_zakonczenia = db.Column(db.Date, nullable=True)
    status = db.Column(db.Text, default="aktywne")
    typ_postepowania = db.Column(db.Text)
    kwota_zadluzenia = db.Column(db.Numeric(10, 2))
    opis = db.Column(db.Text)
    aktywny = db.Column(db.Boolean, default=True)
    data_dodania = db.Column(db.DateTime, default=datetime.utcnow)

    komornik = db.relationship("Komornik", back_populates="postepowania")
    pracownik = db.relationship(
        "Pracownik",
        back_populates="postepowania",
        primaryjoin="foreign(Postepowanie.pesel_pracownika)==Pracownik.pesel",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "pesel_pracownika": self.pesel_pracownika,
            "komornik_id": self.komornik_id,
            "komornik_nazwa": self.komornik_nazwa,
            "sygnatura_sprawy": self.sygnatura_sprawy,
            "data_wplywu": self.data_wplywu.isoformat() if self.data_wplywu else None,
            "data_zakonczenia": self.data_zakonczenia.isoformat() if self.data_zakonczenia else None,
            "status": self.status,
            "typ_postepowania": self.typ_postepowania,
            "kwota_zadluzenia": float(self.kwota_zadluzenia) if self.kwota_zadluzenia is not None else None,
            "opis": self.opis,
            "aktywny": self.aktywny,
            "data_dodania": self.data_dodania.isoformat() if self.data_dodania else None,
        }


# =========================
# Seed danych testowych
# =========================
def _d(v):
    return datetime.strptime(v, "%Y-%m-%d").date() if v else None


def populate_test_data():
    """Wersja ORM metody populate_test_data() z database.py."""
    if Komornik.query.count() > 0:
        print("🔄 Dane testowe już istnieją, pomijam wypełnianie")
        return

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
        ("Marcin Przybylski", "m", "ul. Prosta 89", "00-838", "Warszawa", "22-543-21-09", "m.przybylski@komornik.pl", "Sąd Rejonowy w Warszawie"),
    ]
    db.session.add_all([
        Komornik(
            imie_nazwisko=r[0], plec=r[1], adres=r[2], kod_pocztowy=r[3], miasto=r[4],
            telefon=r[5], email=r[6], sad_rejonowy=r[7]
        ) for r in komornicy_data
    ])

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
        ("Rafał", "Krawczyk", "87111916789", "1987-11-19", "ul. Jaracza 34", "90-015", "Łódź", "515-678-901", "rafal.krawczyk@avalon.pl", "Kierowca", "Avalon Taxi", "2018-07-25", None, "aktywny", "PL83124000050000400069831111", "najem pojazdu"),
    ]
    db.session.add_all([
        Pracownik(
            imie=r[0], nazwisko=r[1], pesel=r[2], data_urodzenia=_d(r[3]), adres_zamieszkania=r[4],
            kod_pocztowy=r[5], miasto=r[6], telefon=r[7], email=r[8], stanowisko=r[9], spolka=r[10],
            data_zatrudnienia=_d(r[11]), data_zwolnienia=_d(r[12]), status_zatrudnienia=r[13],
            numer_rachunku=r[14], typ_umowy=r[15]
        ) for r in pracownicy_data
    ])

    postepowania_data = [
        ("85030512345", 1, "Adam Niegórski", "KM-123/2024", "2024-01-15", None, "aktywne", "zajęcie wynagrodzenia", 5000.00, "Zadłużenie z tytułu alimentów"),
        ("92081823456", 3, "Marek Nowak", "KM-456/2024", "2024-02-20", None, "aktywne", "zajęcie wierzytelności", 12000.00, "Dług kredytowy"),
        ("88111434567", 5, "Tomasz Wójcik", "KM-789/2024", "2024-03-10", "2024-07-15", "zakończone", "zajęcie rachunku", 3000.00, "Kary administracyjne"),
        ("87070656789", 8, "Magdalena Szymańska", "KM-321/2024", "2024-04-05", None, "aktywne", "zajęcie wynagrodzenia", 8000.00, "Zadłużenie podatkowe"),
        ("85030512345", 2, "Anna Kowalska", "KM-111/2024", "2024-01-10", None, "aktywne", "zajęcie wynagrodzenia", 15000.00, "Zadłużenie kredytowe bank A"),
        ("85030512345", 7, "Piotr Kowalczyk", "KM-222/2024", "2024-02-05", None, "aktywne", "zajęcie wynagrodzenia", 7500.00, "Zadłużenie kredytowe bank B"),
        ("88111434567", 4, "Katarzyna Wiśniewska", "KM-333/2024", "2024-01-20", None, "aktywne", "zajęcie wierzytelności", 20000.00, "Zadłużenie z tytułu umowy"),
        ("88111434567", 9, "Jan Kaczmarek", "KM-444/2024", "2024-03-01", None, "aktywne", "zajęcie wynagrodzenia", 9000.00, "Zadłużenie alimentacyjne"),
        ("88111434567", 12, "Monika Zielińska", "KM-555/2024", "2024-03-15", None, "aktywne", "zajęcie rachunku", 4500.00, "Kary i grzywny"),
        ("90040545678", 6, "Barbara Lewandowska", "KM-666/2023", "2023-06-15", "2023-12-20", "zakończone", "zajęcie wynagrodzenia", 6000.00, "Spłacone w całości"),
        ("94122767890", 10, "Agnieszka Zawadzka", "KM-777/2023", "2023-08-10", "2024-01-30", "zakończone", "zajęcie rachunku", 2500.00, "Ugoda zawarta"),
    ]
    db.session.add_all([
        Postepowanie(
            pesel_pracownika=r[0], komornik_id=r[1], komornik_nazwa=r[2], sygnatura_sprawy=r[3],
            data_wplywu=_d(r[4]), data_zakonczenia=_d(r[5]), status=r[6], typ_postepowania=r[7],
            kwota_zadluzenia=Decimal(str(r[8])), opis=r[9]
        ) for r in postepowania_data
    ])

    db.session.commit()
    print("✅ Baza danych została wypełniona danymi testowymi")