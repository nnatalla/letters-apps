#!/bin/bash

# Avalon System - Quick Update Script
# Use this script to quickly update the application on the server

set -e

APP_DIR="/opt/avalon"
APP_USER="avalon"

echo "🔄 Updating Avalon System..."

# Stop the application
echo "Stopping application..."
sudo supervisorctl stop avalon

# Backup current database
echo "Backing up database..."
sudo -u $APP_USER cp $APP_DIR/avalon_system.db $APP_DIR/avalon_system.db.backup.$(date +%Y%m%d_%H%M%S)

# Update application files (assuming new files are in current directory)
echo "Updating application files..."
sudo cp -r ./app.py ./database.py ./index.html ./static/ $APP_DIR/
sudo chown -R $APP_USER:$APP_USER $APP_DIR

# Update Python dependencies if requirements.txt changed
if [ -f "./requirements.txt" ]; then
    echo "Updating Python dependencies..."
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r ./requirements.txt
fi

# Restart the application
echo "Restarting application..."
sudo supervisorctl start avalon

# Check status
echo "Checking application status..."
sudo supervisorctl status avalon

echo "✅ Update completed successfully!"
echo "📋 Check logs: sudo tail -f /var/log/avalon/error.log"
