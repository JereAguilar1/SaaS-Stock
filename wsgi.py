"""WSGI entry point for Gunicorn."""
import sys
import os

# Ensure the app directory is in the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app
from app import create_app

# Create the application instance
app = create_app()

if __name__ == "__main__":
    app.run()
