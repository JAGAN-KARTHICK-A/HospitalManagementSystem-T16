import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/hms_db'
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
