import os
from flask import Flask
from dotenv import load_dotenv
from backend.routes.chatbot import chatbot_bp

# Importing these outside to avoid circular imports later
from backend.extensions import db, migrate

def create_app():
    """
    Application Factory to create Flask app
    """
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__)

    # Fix DATABASE_URL if it uses 'postgres://' instead of 'postgresql://'
    database_url = os.getenv('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///default.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')

    # Log important app configurations
    app.logger.info(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.logger.info(f"SQLALCHEMY_TRACK_MODIFICATIONS: {app.config['SQLALCHEMY_TRACK_MODIFICATIONS']}")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints (Import here to avoid circular import issues)
    with app.app_context():
        from backend.routes.chatbot import chatbot_bp  # Move import here
        app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
        
        from backend import models  # Import models here so they are loaded properly

    return app

# Create the app instance
app = create_app()

# Run only if this script is executed directly
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv('PORT', 5000)))
