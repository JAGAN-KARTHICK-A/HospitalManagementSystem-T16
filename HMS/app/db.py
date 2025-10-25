from pymongo import MongoClient
from flask import current_app, g

# g is a special object that is unique for each request.
# We use it to store the database connection.

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db' not in g:
        try:
            client = MongoClient(current_app.config['MONGO_URI'])
            g.db = client.get_default_database()
            print("Database connection established.")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
    return g.db

def close_db(e=None):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)

    if db is not None:
        # Pymongo's client object manages pooling.
        # We don't explicitly close the client here to allow connection reuse.
        # If you were not using g, you would close client here.
        # For this pattern, we just pop it from g.
        pass

def init_db(app):
    """Register database functions with the Flask app."""
    # This tells Flask to call close_db when cleaning up after returning the response.
    app.teardown_appcontext(close_db)
