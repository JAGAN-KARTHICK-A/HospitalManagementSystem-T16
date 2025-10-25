from flask import Flask
from config import Config
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from app.db import init_db
import os
import click # <-- Import click here
from datetime import datetime
# Initialize extensions
login_manager = LoginManager()
bcrypt = Bcrypt()

# This function is called by Flask-Login to load the current user
@login_manager.user_loader
def load_user(user_id):
    """Loads user object from user ID stored in session."""
    from app.models import get_user_by_id  # <-- Import moved here
    return get_user_by_id(user_id)

# Set the view function name for the login page
login_manager.login_view = 'main.login'
# Set the message category for "login required" flashes
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    """
    Application Factory Pattern: Creates and configures the Flask app.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize database
    init_db(app)

    # Initialize extensions with the app
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # --- Register Blueprints ---
    
    # Import the main blueprint
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Register the patient portal blueprint (prefix it with /patient)
    from app.patient_portal import patient_bp
    app.register_blueprint(patient_bp, url_prefix='/patient') # <-- ADD THIS LINE

    # --- Initialize AI Model ---
    # ... (rest of your create_app function) ...

    # You would add other blueprints here (e.g., clinical, emergency)
    # from app.clinical_routes import clinical_bp
    # app.register_blueprint(clinical_bp, url_prefix='/clinical')

    # --- Register CLI Commands ---
    # Import here to avoid circular imports
    from app.models import create_super_admin_user

    @app.cli.command("create-super-admin")
    def create_super_admin_command():
        """Creates the initial Super Admin user."""
        print("Creating Super Admin Account...")
        try:
            username = input("Enter Super Admin username: ")
            password = input("Enter Super Admin password: ")
            
            if not username or not password:
                print("Username and password cannot be empty.")
                return

            user_id = create_super_admin_user(username, password)
            if user_id:
                print(f"Super Admin '{username}' created successfully with ID: {user_id}")
            else:
                print(f"User '{username}' may already exist.")
                
        except Exception as e:
            print(f"An error occurred: {e}")

    
    @app.context_processor
    def inject_utilities():
        """Inject utility objects/functions into all templates."""
        return dict(datetime=datetime)

    print("Flask App Created and Configured.")

    return app