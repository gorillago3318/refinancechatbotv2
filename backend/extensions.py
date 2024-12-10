<<<<<<< HEAD
# backend/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions without binding to the app
=======
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize extensions
>>>>>>> 870f5012dd82d8904a3a273ae3903fd4423d0643
db = SQLAlchemy()
migrate = Migrate()
