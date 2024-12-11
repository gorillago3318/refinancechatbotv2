from flask import Flask
from backend.extensions import db, migrate  # ✅ Correct import
from dotenv import load_dotenv
import os
import logging
from urllib.parse import urlparse

# Enable basic logging
logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)

    # Load environment variables
    load_dotenv()

    # Configure SQLAlchemy database URI
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from backend.routes.chatbot import chatbot_bp
    from backend.routes.auth import auth_bp
    from backend.routes.admin import admin_bp
    from backend.routes.agent import agent_bp

    app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(agent_bp, url_prefix='/api/agent')

    with app.app_context():
        from backend import models

    # Root endpoint (Landing page)
    @app.route('/')
    def home():
        return "Welcome to the Finzo Chatbot API"

    # Webhook endpoint (test it with Postman)
    @app.route('/webhook', methods=['POST'])
    def webhook():
        return "Webhook received successfully!", 200

    return app

# Expose the app object for Gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # Heroku provides the port
    app.run(host='0.0.0.0', port=port)
