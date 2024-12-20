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

    # Load the DATABASE_URL from the .env file
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///local.db')

    # Heroku gives 'postgres://' but SQLAlchemy requires 'postgresql://'
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable SQLAlchemy event tracking to boost performance

    DEBUG = os.getenv('DEBUG', 'False').lower() in ['true', '1', 'yes']  # Convert DEBUG to boolean
    ENV = os.getenv('FLASK_ENV', 'development')  # Set the environment (development/production/testing)


class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True  # Enable debug mode
    ENV = 'development'  # Set the environment to development


class ProductionConfig(Config):
    """Configuration for production environment."""
    DEBUG = False  # Disable debug mode
    ENV = 'production'  # Set the environment to production


class TestingConfig(Config):
    """Configuration for testing environment."""
    TESTING = True  # Enable testing mode
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # Use an in-memory database for tests


# Dictionary to select configuration by environment
configurations = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

# Log the environment being used
current_env = os.getenv('FLASK_ENV', 'development')
logging.info(f"App running in {current_env} mode using {configurations[current_env].SQLALCHEMY_DATABASE_URI}")
