#!/usr/bin/env python3
"""
Production runner for AHOY Flask app
"""
from app import app
import os

if __name__ == '__main__':
    # Use environment variables for production
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)
