import os

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key')
    DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'

    # SQLAlchemy settings
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your_jwt_secret_key')

    # Additional configurations can be added here
