# 🚀 Szybka Instalacja na Serwerze Ubuntu (Google Cloud)

## Przed rozpoczęciem
1. Połącz się z serwerem: `ssh username@your-server-ip`
2. Przygotuj domenę (opcjonalnie): `your-domain.com → server-ip`
3. Miej gotowy klucz API Groq

## Kroki instalacji

### 1. Upload plików na serwer
```bash
# Opcja A: Przez SCP
scp -r * username@server-ip:/home/username/

# Opcja B: Przez Git (zalecane)
git clone your-repository-url
cd your-repository-name
```

### 2. Uruchom instalację
```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. Skonfiguruj API key
```bash
sudo nano /opt/avalon/.env.production
# Dodaj: GROQ_API_KEY=your-actual-key
```

### 4. Restart aplikacji
```bash
sudo supervisorctl restart avalon
```

### 5. Skonfiguruj domenę (opcjonalnie)
```bash
# Edytuj konfigurację Nginx
sudo nano /etc/nginx/sites-available/avalon
# Zmień your-domain.com na twoją domenę

# Restart Nginx
sudo systemctl restart nginx

# Dodaj SSL
sudo certbot --nginx -d your-domain.com
```

## Sprawdzenie statusu
```bash
sudo supervisorctl status avalon
sudo tail -f /var/log/avalon/error.log
```

## Aktualizacje
```bash
./update.sh
```

**Gotowe!** Aplikacja będzie dostępna na: `http://your-server-ip/` lub `https://your-domain.com/`
