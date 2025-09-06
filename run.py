#!/usr/bin/env python3
"""
Production runner for AHOY Flask app
"""
from app import app, find_available_port
import os
import socket

if __name__ == '__main__':
    # Try to use the PORT environment variable first, then find an available port
    try:
        port = int(os.environ.get('PORT', 5000))
        # Test if the port is available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
    except (ValueError, OSError):
        # If PORT env var is invalid or port is in use, find an available port
        port = find_available_port()
        print(f"Port 5000 is in use. Using port {port} instead.")
    
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
