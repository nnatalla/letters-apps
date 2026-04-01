# Avalon System Deployment Guide

## 📋 Prerequisites

Before deploying to Google Cloud Ubuntu server, ensure you have:

1. **Ubuntu 20.04/22.04 LTS** server on Google Cloud
2. **SSH access** to the server
3. **Domain name** pointed to your server's IP (optional but recommended)
4. **Groq API key** for OCR functionality

## 🚀 Deployment Steps

### 1. Prepare Local Files

Your project is ready for deployment with these files:
- `app.py` - Main Flask application
- `database.py` - Database management
- `index.html` - Frontend interface
- `requirements.txt` - Python dependencies
- `gunicorn.conf.py` - Production WSGI server config
- `deploy.sh` - Automated deployment script
- `.env.production` - Production environment variables

### 2. Upload Files to Server

```bash
# Option A: Using SCP
scp -r * username@your-server-ip:/home/username/avalon/

# Option B: Using Git (recommended)
git init
git add .
git commit -m "Initial deployment"
git push origin main
# Then on server: git clone your-repo-url
```

### 3. Run Deployment Script

```bash
# Connect to your server
ssh username@your-server-ip

# Navigate to project directory
cd /path/to/avalon

# Make deployment script executable
chmod +x deploy.sh

# Run deployment (this will take 5-10 minutes)
./deploy.sh
```

### 4. Configure Environment

Edit production environment file:
```bash
sudo nano /opt/avalon/.env.production
```

**Important:** Update these values:
- `SECRET_KEY` - Generate a secure secret key
- `GROQ_API_KEY` - Your Groq API key

### 5. Set Up Domain (Optional)

Edit Nginx configuration:
```bash
sudo nano /etc/nginx/sites-available/avalon
```

Replace `your-domain.com` with your actual domain.

### 6. Enable SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 🔧 Management Commands

### Check Application Status
```bash
sudo supervisorctl status avalon
```

### View Logs
```bash
# Application logs
sudo tail -f /var/log/avalon/error.log

# Access logs
sudo tail -f /var/log/avalon/access.log

# Supervisor logs
sudo tail -f /var/log/avalon/supervisor.log
```

### Restart Application
```bash
sudo supervisorctl restart avalon
```

### Update Application
```bash
# Upload new files and run:
chmod +x update.sh
./update.sh
```

## 🌐 Firewall & Security

The deployment script automatically:
- ✅ Enables UFW firewall
- ✅ Opens SSH and HTTP/HTTPS ports
- ✅ Creates dedicated application user
- ✅ Sets proper file permissions
- ✅ Configures secure Nginx proxy

## 📊 Monitoring

### Service Status
```bash
# Check all services
systemctl status nginx supervisor

# Check application specifically
sudo supervisorctl status avalon
```

### Performance Monitoring
```bash
# Check memory usage
free -h

# Check disk usage
df -h

# Check running processes
htop
```

## 🐛 Troubleshooting

### Application Won't Start
1. Check logs: `sudo tail -f /var/log/avalon/error.log`
2. Verify environment: `sudo cat /opt/avalon/.env.production`
3. Check permissions: `ls -la /opt/avalon/`

### Database Issues
1. Check database file: `ls -la /opt/avalon/avalon_system.db`
2. Test database: `sqlite3 /opt/avalon/avalon_system.db ".tables"`

### Nginx Issues
1. Test configuration: `sudo nginx -t`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`

## 🔄 Updates

To update your application:

1. **Upload new files** to server
2. **Run update script**: `./update.sh`
3. **Check status**: `sudo supervisorctl status avalon`

## 📝 Default URLs

After deployment, your application will be available at:
- **HTTP**: `http://your-server-ip/`
- **HTTPS** (with SSL): `https://your-domain.com/`

## 🔐 Security Notes

- Database backups are created automatically during updates
- Application runs as non-root user (`avalon`)
- Firewall is enabled with minimal required ports
- File uploads are restricted to configured directory
- Nginx provides reverse proxy protection

---

**Support**: If you encounter issues, check the logs first, then review this guide's troubleshooting section.
