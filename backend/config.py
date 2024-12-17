import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class with default settings."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_default_secret_key')
    if SECRET_KEY == 'your_default_secret_key':
        logging.warning("SECRET_KEY is not set in .env. Using the default, which is not safe for production.")

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///local.db')

if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable modification tracking for better performance
    DEBUG = os.getenv('DEBUG', 'True').lower() in ['true', '1', 'yes']  # Convert environment variable to boolean

class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True  # Enable debug mode for development
    ENV = 'development'  # Set the Flask environment to development

class ProductionConfig(Config):
    """Configuration for production environment."""
    DEBUG = False  # Disable debug mode for production
    ENV = 'production'  # Set the Flask environment to production

class TestingConfig(Config):
    """Configuration for testing environment."""
    TESTING = True  # Enable testing mode
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # In-memory database for tests

# Dictionary to select configuration by environment
configurations = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

# Log the environment being used
current_env = os.getenv('FLASK_ENV', 'development')
logging.info(f"App running in {current_env} mode")
