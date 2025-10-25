from app import create_app

# Create the Flask app instance using the app factory
app = create_app()

if __name__ == '__main__':
    # This block is for running with 'python run.py'
    app.run(debug=True)