# Wdrożenie aplikacji na AWS EC2 (t2.micro/t3.micro)

## 1. Przygotowanie instancji EC2

### Jeśli jeszcze nie masz EC2:
1. Zaloguj się do AWS Console
2. Idź do EC2 Dashboard
3. Kliknij "Launch Instance"
4. Wybierz: **Ubuntu Server 22.04 LTS (Free tier eligible)**
5. Instance type: **t2.micro** (darmowy w Free Tier)
6. Key pair: utwórz nowy lub wybierz istniejący
7. Security Group:
   - SSH (port 22) - tylko twój IP
   - HTTP (port 80) - 0.0.0.0/0
   - Custom TCP (port 8000) - 0.0.0.0/0
8. Storage: 8GB (darmowe) lub więcej jeśli potrzebujesz
9. Launch Instance

### Jeśli już masz EC2:
Sprawdź Security Groups - dodaj reguły:
- HTTP (port 80) - 0.0.0.0/0  
- Custom TCP (port 8000) - 0.0.0.0/0

## 2. Połączenie z serwerem

```bash
# Znajdź swój Public IP w EC2 Console
# Połącz się przez SSH (zamień na swoje dane)
ssh -i your-key.pem ubuntu@YOUR-EC2-PUBLIC-IP

# Lub użyj EC2 Instance Connect w Console (przycisk Connect)
```

## 3. Konfiguracja serwera Ubuntu na EC2

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

# Biblioteki systemowe dla Pillow i pytesseract
sudo apt install -y libjpeg-dev zlib1g-dev libpng-dev
sudo apt install -y tesseract-ocr tesseract-ocr-pol

# Poppler dla PDF
sudo apt install -y poppler-utils

# Sprawdzenie wolnego miejsca na dysku
df -h
```

**UWAGA dla t2.micro**: Ta instancja ma tylko 1GB RAM, więc aplikacja może być wolniejsza. Można rozważyć t3.micro (2GB RAM) jeśli masz w Free Tier.

## 4. Przesłanie aplikacji na serwer

### Opcja A: Przez Git (zalecane)
```bash
# Jeśli masz kod na GitHub/GitLab:
cd /home/ubuntu
git clone https://github.com/twoje-konto/avalon-app.git
cd avalon-app
```

### Opcja B: Przez SCP
```bash
# Z komputera lokalnego (zmień ścieżki):
scp -i your-key.pem -r avalon_test/ ubuntu@YOUR-EC2-IP:/home/ubuntu/avalon-app
```

### Opcja C: Przez tar + SCP
```bash
# Na lokalnym komputerze:
tar -czf avalon-app.tar.gz avalon_test/

# Prześlij
scp -i your-key.pem avalon-app.tar.gz ubuntu@YOUR-EC2-IP:/home/ubuntu/

# Na serwerze:
ssh -i your-key.pem ubuntu@YOUR-EC2-IP
tar -xzf avalon-app.tar.gz
mv avalon_test avalon-app
cd avalon-app
```

## 5. Konfiguracja aplikacji na serwerze

```bash
cd /home/ubuntu/avalon-app

# Tworzenie wirtualnego środowiska
python3.11 -m venv venv
source venv/bin/activate

# Instalacja zależności
pip install --upgrade pip
pip install -r requirements.txt

# Test aplikacji (WAŻNE: zmień host na 0.0.0.0)
# Edytuj app.py żeby działało z zewnątrz
```

### Modyfikacja app.py dla EC2:
```bash
nano app.py
```

Na końcu pliku zmień:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

### Test aplikacji:
```bash
python app.py
# Sprawdź http://YOUR-EC2-PUBLIC-IP:5000 w przeglądarce
# Ctrl+C żeby zatrzymać
```

## 6. Konfiguracja do działania na porcie 80 (bez Nginx)

### Prostsze rozwiązanie - bezpośrednio na porcie 80:
```bash
# Zatrzymaj aplikację jeśli działa
# Edytuj app.py
nano app.py
```

Zmień port na 80:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
```

### Uruchomienie z sudo (port 80 wymaga uprawnień):
```bash
sudo /home/ubuntu/avalon-app/venv/bin/python app.py
```

**Problem**: To zablokuje terminal. Lepiej użyć Supervisor.

## 7. Konfiguracja Supervisor (automatyczne uruchamianie)

### Tworzenie konfiguracji:
```bash
sudo nano /etc/supervisor/conf.d/avalon-app.conf
```

Zawartość (pamiętaj zmienić port w app.py na 80):
```ini
[program:avalon-app]
command=/home/ubuntu/avalon-app/venv/bin/python app.py
directory=/home/ubuntu/avalon-app
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/avalon-app.log
environment=PATH="/home/ubuntu/avalon-app/venv/bin"
```

### Aktywacja:
```bash
# Przeładowanie konfiguracji
sudo supervisorctl reread
sudo supervisorctl update

# Start aplikacji
sudo supervisorctl start avalon-app

# Sprawdzenie statusu
sudo supervisorctl status
```

## 8. Alternatywnie: Nginx + Gunicorn (bardziej profesjonalne)

### Instalacja Gunicorn:
```bash
source /home/ubuntu/avalon-app/venv/bin/activate
pip install gunicorn
```

### Konfiguracja Gunicorn:
```bash
nano /home/ubuntu/avalon-app/gunicorn.conf.py
```

Sprawdź czy masz odpowiednią konfigurację w tym pliku.

### Supervisor dla Gunicorn:
```bash
sudo nano /etc/supervisor/conf.d/avalon-app.conf
```

Zawartość:
```ini
[program:avalon-app]
command=/home/ubuntu/avalon-app/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
directory=/home/ubuntu/avalon-app
user=ubuntu
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/avalon-app.log
environment=PATH="/home/ubuntu/avalon-app/venv/bin"
```

### Nginx konfiguracja:
```bash
sudo nano /etc/nginx/sites-available/avalon-app
```

Zawartość:
```nginx
server {
    listen 80;
    server_name YOUR_EC2_PUBLIC_IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }

    location /static/ {
        alias /home/ubuntu/avalon-app/static/;
        expires 30d;
    }
}
```

### Aktywacja Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/avalon-app /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 9. Monitoring i utrzymanie

### Sprawdzanie logów:
```bash
# Logi aplikacji
sudo tail -f /var/log/avalon-app.log

# Status usług
sudo supervisorctl status
sudo systemctl status nginx
```

### Restart aplikacji:
```bash
sudo supervisorctl restart avalon-app
```

### Sprawdzanie zużycia pamięci (ważne dla t2.micro):
```bash
free -h
htop
```

## 10. Optymalizacja dla t2.micro (1GB RAM)

### Dodanie swap (jeśli brakuje pamięci):
```bash
# Tworzenie 1GB swap
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Stałe dodanie do /etc/fstab
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Monitoring pamięci:
```bash
# Sprawdzanie zużycia
free -h
ps aux --sort=-%mem | head
```

## 11. Zabezpieczenia

### Firewall (UFW):
```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443  # jeśli planujesz SSL
sudo ufw status
```

### Automatyczne aktualizacje:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## 12. SSL (opcjonalne)

### Jeśli masz domenę:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### Bez domeny:
Możesz używać aplikacji przez HTTP z adresem IP.

## 13. Backup bazy danych

### Skrypt backup:
```bash
nano /home/ubuntu/backup_db.sh
```

Zawartość:
```bash
#!/bin/bash
cd /home/ubuntu/avalon-app
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p backups
cp avalon_system.db backups/avalon_system_backup_$DATE.db
# Zachowaj tylko 5 ostatnich backupów (ważne dla małego dysku)
ls -t backups/avalon_system_backup_*.db | tail -n +6 | xargs rm -f
```

### Cron job dla automatycznego backup:
```bash
chmod +x /home/ubuntu/backup_db.sh
crontab -e
```

Dodaj linię (backup codziennie o 2:00):
```
0 2 * * * /home/ubuntu/backup_db.sh
```

## 14. Adres aplikacji

### Znajdź Public IP:
```bash
curl -s http://checkip.dyndns.org | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}'
```

### Lub w AWS Console:
EC2 → Instances → twoja instancja → Public IPv4 address

### Adres aplikacji:
- `http://YOUR-EC2-PUBLIC-IP`

## 15. Troubleshooting dla t2.micro

### Jeśli aplikacja jest wolna:
```bash
# Sprawdź pamięć
free -h

# Sprawdź czy swap jest aktywny
swapon --show

# Restartuj aplikację
sudo supervisorctl restart avalon-app
```

### Jeśli brakuje miejsca na dysku:
```bash
# Sprawdź miejsce
df -h

# Wyczyść cache
sudo apt clean
sudo apt autoremove

# Usuń stare logi
sudo journalctl --vacuum-time=7d
```

## Koszty AWS (Free Tier):
- **t2.micro**: DARMOWE przez 12 miesięcy (750h/miesiąc)
- **8GB storage**: DARMOWE (30GB w Free Tier)
- **Transfer**: 15GB/miesiąc darmowe

**Po Free Tier**: ~$8-10/miesiąc dla t2.micro
