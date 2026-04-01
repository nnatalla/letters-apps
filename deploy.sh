#!/bin/bash

# Avalon System Deployment Script for Ubuntu Server
# This script sets up the complete environment for the Avalon system

set -e

echo "🚀 Starting Avalon System deployment..."

# Variables
APP_DIR="/opt/avalon"
APP_USER="avalon"
SERVICE_NAME="avalon"
DOMAIN="your-domain.com"  # Change this to your domain

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user with sudo privileges."
   exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required system packages
print_status "Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    supervisor \
    sqlite3 \
    tesseract-ocr \
    tesseract-ocr-pol \
    poppler-utils \
    wkhtmltopdf \
    git \
    curl \
    unzip \
    certbot \
    python3-certbot-nginx

# Create application user
print_status "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash $APP_USER
    sudo usermod -aG www-data $APP_USER
    print_success "User $APP_USER created"
else
    print_warning "User $APP_USER already exists"
fi

# Create application directory
print_status "Setting up application directory..."
sudo mkdir -p $APP_DIR
sudo chown $APP_USER:$APP_USER $APP_DIR

# Create log directories
print_status "Creating log directories..."
sudo mkdir -p /var/log/avalon
sudo mkdir -p /var/run/avalon
sudo chown $APP_USER:$APP_USER /var/log/avalon
sudo chown $APP_USER:$APP_USER /var/run/avalon

# Copy application files (assuming they're in current directory)
print_status "Copying application files..."
sudo cp -r ./* $APP_DIR/
sudo chown -R $APP_USER:$APP_USER $APP_DIR

# Create Python virtual environment
print_status "Creating Python virtual environment..."
sudo -u $APP_USER python3 -m venv $APP_DIR/venv

# Install Python dependencies
print_status "Installing Python dependencies..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
sudo -u $APP_USER $APP_DIR/venv/bin/pip install gunicorn

# Create production configuration
print_status "Creating production configuration..."
sudo -u $APP_USER cat > $APP_DIR/.env.production << EOF
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_PATH=$APP_DIR/avalon_system.db
UPLOAD_FOLDER=$APP_DIR/temp_uploads
LOG_LEVEL=INFO
EOF

# Set up database
print_status "Setting up database..."
sudo -u $APP_USER mkdir -p $APP_DIR/temp_uploads
sudo -u $APP_USER chmod 755 $APP_DIR/temp_uploads

# Create Supervisor configuration
print_status "Creating Supervisor configuration..."
sudo tee /etc/supervisor/conf.d/avalon.conf > /dev/null << EOF
[program:avalon]
command=$APP_DIR/venv/bin/gunicorn -c $APP_DIR/gunicorn.conf.py wsgi:app
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/avalon/supervisor.log
environment=PATH="$APP_DIR/venv/bin",FLASK_ENV="production"
EOF

# Create Nginx configuration
print_status "Creating Nginx configuration..."
sudo tee /etc/nginx/sites-available/avalon > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /temp_uploads {
        alias $APP_DIR/temp_uploads;
        expires 1h;
        add_header Cache-Control "public, no-transform";
    }
}
EOF

# Enable Nginx site
print_status "Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/avalon /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
print_status "Testing Nginx configuration..."
sudo nginx -t

# Start services
print_status "Starting services..."
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start avalon
sudo systemctl restart nginx
sudo systemctl enable supervisor
sudo systemctl enable nginx

# Setup firewall
print_status "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'

print_success "🎉 Avalon System has been deployed successfully!"
print_status "📋 Deployment Summary:"
echo "   - Application Directory: $APP_DIR"
echo "   - Application User: $APP_USER"
echo "   - Service Status: sudo supervisorctl status avalon"
echo "   - Logs: /var/log/avalon/"
echo "   - Nginx Config: /etc/nginx/sites-available/avalon"
echo ""
print_status "🔧 Next Steps:"
echo "   1. Update the domain name in /etc/nginx/sites-available/avalon"
echo "   2. Set up SSL certificate: sudo certbot --nginx -d $DOMAIN"
echo "   3. Check service status: sudo supervisorctl status"
echo "   4. View logs: sudo tail -f /var/log/avalon/error.log"
echo ""
print_warning "⚠️  Don't forget to:"
echo "   - Update your DNS records to point to this server"
echo "   - Add your Groq API key to $APP_DIR/.env.production"
echo "   - Test the application thoroughly"
EOF
