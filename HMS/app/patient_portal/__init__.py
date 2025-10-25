from flask import Blueprint

# Create a Blueprint named 'patient_portal'
# template_folder='templates' tells Flask where to find this blueprint's HTML files
patient_bp = Blueprint(
    'patient_portal',
    __name__,
    template_folder='templates',
    # Optional: If you add CSS/JS specific to the portal later
    # static_folder='static',
    # static_url_path='/patient_portal/static'
)

# Import routes after creating the blueprint to avoid circular imports
from . import routes