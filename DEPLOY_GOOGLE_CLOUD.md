# Wdrożenie aplikacji na Ubuntu w Google Cloud Platform

## 1. Przygotowanie instancji VM w Google Cloud

### Tworzenie VM:
```bash
# Utwórz nową instancję VM
gcloud compute instances create avalon-app \
    --image-family ubuntu-2204-lts \
    --image-project ubuntu-os-cloud \
    --machine-type e2-medium \
    --zone us-central1-a \
    --boot-disk-size 20GB \
    --tags http-server,https-server

# Otwórz porty dla HTTP/HTTPS
gcloud compute firewall-rules create allow-http-8000 \
    --allow tcp:8000 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTP on port 8000"
```

### Lub przez Console:
1. Idź do Google Cloud Console → Compute Engine → VM instances
2. Kliknij "Create Instance"
3. Nazwa: `avalon-app`
4. Region/Zona: wybierz najbliższą
5. Machine type: `e2-medium` (2 vCPU, 4GB RAM)
6. Boot disk: Ubuntu 22.04 LTS, 20GB
7. Firewall: zaznacz "Allow HTTP traffic" i "Allow HTTPS traffic"
8. Kliknij "Create"

## 2. Połączenie z serwerem

```bash
# Połącz się przez SSH
gcloud compute ssh avalon-app --zone us-central1-a

# Lub użyj SSH z Console (przycisk SSH obok nazwy VM)
```

## 3. Konfiguracja serwera Ubuntu

### Aktualizacja systemu:
```bash
sudo apt update && sudo apt upgrade -y
```

### Instalacja Python i narzędzi:
```bash
# Instalacja Python 3.11 i pip
sudo apt install -y python3.11 python3.11-venv python3-pip

# Instalacja dodatkowych narzędzi
sudo apt install -y git nginx supervisor sqlite3

# Instalacja bibliotek systemowych dla Pillow i pytesseract
sudo apt install -y libjpeg-dev zlib1g-dev libpng-dev
sudo apt install -y tesseract-ocr tesseract-ocr-pol

# Instalacja Poppler (dla PDF)
sudo apt install -y poppler-utils
```

## 4. Przesłanie aplikacji na serwer

### Opcja A: Przez Git (zalecane)
```bash
# Utwórz repozytorium na GitHub/GitLab z plikami aplikacji
# Następnie na serwerze:
cd /home/$USER
git clone https://github.com/twoje-konto/avalon-app.git
cd avalon-app
```

### Opcja B: Przez SCP
```bash
# Z komputera lokalnego:
gcloud compute scp --recurse avalon_test/ avalon-app:/home/$USER/avalon-app --zone us-central1-a
```

### Opcja C: Przez SSH + tar
```bash
# Na lokalnym komputerze:
tar -czf avalon-app.tar.gz avalon_test/

# Prześlij przez SSH
gcloud compute scp avalon-app.tar.gz avalon-app:/home/$USER/ --zone us-central1-a

# Na serwerze:
tar -xzf avalon-app.tar.gz
mv avalon_test avalon-app
cd avalon-app
```

## 5. Konfiguracja aplikacji na serwerze

```bash
cd /home/$USER/avalon-app

# Tworzenie wirtualnego środowiska
python3.11 -m venv venv
source venv/bin/activate

# Instalacja zależności
pip install --upgrade pip
pip install -r requirements.txt

# Nadanie uprawnień wykonania
chmod +x deploy.sh update.sh

# Test aplikacji
python app.py
# Sprawdź czy działa na http://EXTERNAL-IP:5000
```

## 6. Konfiguracja Nginx (reverse proxy)

### Tworzenie konfiguracji Nginx:
```bash
sudo nano /etc/nginx/sites-available/avalon-app
```

Zawartość pliku:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }

    location /static/ {
        alias /home/$USER/avalon-app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### Aktywacja konfiguracji:
```bash
# Włączenie strony
sudo ln -s /etc/nginx/sites-available/avalon-app /etc/nginx/sites-enabled/

# Usunięcie domyślnej strony
sudo rm /etc/nginx/sites-enabled/default

# Test konfiguracji
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 7. Konfiguracja Supervisor (automatyczne uruchamianie)

### Tworzenie konfiguracji Supervisor:
```bash
sudo nano /etc/supervisor/conf.d/avalon-app.conf
```

Zawartość pliku:
```ini
[program:avalon-app]
command=/home/USER/avalon-app/venv/bin/python app.py
directory=/home/USER/avalon-app
user=USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/avalon-app.log
environment=PATH="/home/USER/avalon-app/venv/bin"
```

**UWAGA**: Zamień `USER` na swoją nazwę użytkownika (sprawdź: `whoami`)

### Aktywacja Supervisor:
```bash
# Przeładowanie konfiguracji
sudo supervisorctl reread
sudo supervisorctl update

# Start aplikacji
sudo supervisorctl start avalon-app

# Sprawdzenie statusu
sudo supervisorctl status

# Włączenie auto-startu
sudo systemctl enable supervisor
```

## 8. Konfiguracja SSL (opcjonalne, ale zalecane)

### Używając Let's Encrypt (darmowe SSL):
```bash
# Instalacja Certbot
sudo apt install -y certbot python3-certbot-nginx

# Uzyskanie certyfikatu (zamień YOUR_DOMAIN)
sudo certbot --nginx -d YOUR_DOMAIN

# Test automatycznego odnowienia
sudo certbot renew --dry-run
```

## 9. Konfiguracja domeny (opcjonalne)

### Jeśli masz domenę:
1. W panelu DNS dodaj rekord A wskazujący na External IP twojego VM
2. Poczekaj na propagację DNS (do 24h)
3. Zaktualizuj konfigurację Nginx z nazwą domeny

### Bez domeny:
- Użyj External IP jako adresu strony
- Znajdziesz go w: Compute Engine → VM instances

## 10. Skrypty wdrożeniowe

### Aktualizacja pliku deploy.sh:
```bash
nano deploy.sh
```

Dodaj na początku:
```bash
#!/bin/bash
cd /home/$USER/avalon-app
source venv/bin/activate
```

### Skrypt backup bazy danych:
```bash
nano backup_db.sh
```

Zawartość:
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp avalon_system.db backups/avalon_system_backup_$DATE.db
# Zachowaj tylko 7 ostatnich backupów
ls -t backups/avalon_system_backup_*.db | tail -n +8 | xargs rm -f
```

## 11. Monitoring i logi

### Oglądanie logów:
```bash
# Logi aplikacji
sudo tail -f /var/log/avalon-app.log

# Logi Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Status aplikacji
sudo supervisorctl status avalon-app
```

### Restart aplikacji:
```bash
sudo supervisorctl restart avalon-app
```

## 12. Zabezpieczenia

### Firewall:
```bash
# Instalacja UFW
sudo ufw enable

# Podstawowe reguły
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'

# Sprawdzenie statusu
sudo ufw status
```

### Aktualizacje automatyczne:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## 13. Finalny checklist

- [ ] VM utworzony i skonfigurowany
- [ ] Aplikacja przesłana i działa
- [ ] Nginx skonfigurowany jako reverse proxy
- [ ] Supervisor uruchamia aplikację automatycznie
- [ ] SSL skonfigurowane (opcjonalne)
- [ ] Domena podpięta (opcjonalne)
- [ ] Firewall skonfigurowany
- [ ] Backup bazy danych skonfigurowany

## Adres aplikacji:
- HTTP: `http://EXTERNAL-IP` lub `http://YOUR-DOMAIN`
- HTTPS: `https://YOUR-DOMAIN` (jeśli SSL skonfigurowane)

## Przydatne komendy:

```bash
# Sprawdzenie External IP
curl -s http://checkip.dyndns.org | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}'

# Restart wszystkich usług
sudo systemctl restart nginx
sudo supervisorctl restart avalon-app

# Sprawdzenie czy port jest otwarty
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :5000
```

## Koszty Google Cloud:
- e2-medium VM: ~$25/miesiąc
- 20GB dysk: ~$2/miesiąc
- Transfer danych: zależnie od ruchu

**Tip**: Możesz użyć e2-micro (darmowy w ramach Free Tier) dla testów, ale może być za słaby dla produkcji.
