from flask import Flask
from backend.extensions import db, migrate
from dotenv import load_dotenv
import os

def create_app():
    app = Flask(__name__)

    # Load environment variables
    load_dotenv()

    # Fix DATABASE_URL if it uses 'postgres://' instead of 'postgresql://'
    database_url = os.getenv('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from backend.routes.chatbot import chatbot_bp
    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')

    with app.app_context():
        from backend import models  # Import models here

    return app

app = create_app()

if __name__ == "__main__":
    app.run()
