from flask import Flask
from backend.extensions import db, migrate  # ✅ Correct import
from dotenv import load_dotenv
import os

def create_app():
    app = Flask(__name__)

    # Load environment variables
    load_dotenv()

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    db.init_app(app)
    migrate.init_app(app, db)

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

    return app

# Expose the app object for Gunicorn
app = create_app()

if __name__ == "__main__":
    app.run()
