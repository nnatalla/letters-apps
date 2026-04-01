#!/usr/bin/env python3
"""
WSGI entry point for Avalon System
This file is used by Gunicorn to run the application in production
"""

import os
import sys

# Add the application directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import app

# Set production environment
os.environ.setdefault('FLASK_ENV', 'production')

if __name__ == "__main__":
    app.run()
