# backend/config.py

import os

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key')  # Replace with a strong secret in production
    DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'

    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///refinance_chatbot.db')  # Updated to match .env
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your_jwt_secret_key')  # Replace with a strong secret in production

    # Additional configurations can be added here
