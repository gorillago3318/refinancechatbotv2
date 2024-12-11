import logging
import os
from flask import Flask
from dotenv import load_dotenv
from backend.extensions import db, migrate  # Importing db and migrate for SQLAlchemy and migrations

def create_app():
    app = Flask(__name__)

    # Load environment variables
    load_dotenv()

    # Configure database
    database_url = os.getenv('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Debug log: Check files in backend/routes/
    try:
        routes_dir = os.path.join(os.getcwd(), 'backend', 'routes')
        files_in_routes = os.listdir(routes_dir)
        print(f"🗂️ Contents of backend/routes: {files_in_routes}")
    except Exception as e:
        print(f"❌ Failed to list backend/routes directory: {e}")

    # **Start of import for chatbot_bp with logging**
    try:
        from backend.routes.chatbot import chatbot_bp  # Correct import for chatbot_bp
        print("✅ Successfully imported chatbot_bp from backend.routes.chatbot")
    except ImportError as e:
        print(f"❌ ImportError: Failed to import chatbot_bp: {e}")
    except Exception as e:
        print(f"❌ Unexpected error while importing chatbot_bp: {e}")
    # **End of import for chatbot_bp**

    # Register the chatbot blueprint
    try:
        app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
        print("✅ Successfully registered chatbot_bp blueprint at /api/chatbot")
    except Exception as e:
        print(f"❌ Failed to register chatbot_bp blueprint: {e}")

    # Import models (if necessary)
    with app.app_context():
        try:
            from backend import models  # Import models here if required
            print("✅ Successfully imported models from backend/models.py")
        except Exception as e:
            print(f"❌ Failed to import models from backend/models.py: {e}")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
