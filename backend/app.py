# backend/app.py

from flask import Flask
from backend.extensions import db, migrate
from dotenv import load_dotenv
import os

def create_app():
    app = Flask(__name__)

    # Load environment variables
    load_dotenv()

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///refinance_chatbot.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')

    db.init_app(app)
    migrate.init_app(app, db)

    from backend.routes.chatbot import chatbot_bp
    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')

    with app.app_context():
        from backend import models

    return app
