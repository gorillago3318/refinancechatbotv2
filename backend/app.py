import os
import logging
from flask import Flask
from dotenv import load_dotenv
from .extensions import db, migrate  # Relative import

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

def create_app():
    """Application factory to create and configure the app."""
    app = Flask(__name__)

    # Configure database URL
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
        logging.info(f"🗂️ Contents of backend/routes: {files_in_routes}")
    except Exception as e:
        logging.error(f"❌ Failed to list backend/routes directory: {e}")

    # **Start of import for chatbot_bp with logging**
    try:
        from backend.routes.chatbot import chatbot_bp  # Correct import for chatbot_bp
        logging.info("✅ Successfully imported chatbot_bp from backend.routes.chatbot")
    except ImportError as e:
        logging.error(f"❌ ImportError: Failed to import chatbot_bp: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error while importing chatbot_bp: {e}")
    # **End of import for chatbot_bp**

    # Register the chatbot blueprint
    try:
        app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
        logging.info("✅ Successfully registered chatbot_bp blueprint at /api/chatbot")
    except Exception as e:
        logging.error(f"❌ Failed to register chatbot_bp blueprint: {e}")

    # Import models (if necessary)
    with app.app_context():
        try:
            from backend import models  # Import models here if required
            logging.info("✅ Successfully imported models from backend/models.py")
        except Exception as e:
            logging.error(f"❌ Failed to import models from backend/models.py: {e}")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.getenv('DEBUG', 'False').lower() == 'true')
