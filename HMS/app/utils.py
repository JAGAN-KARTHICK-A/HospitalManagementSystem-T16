from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user

def role_required(role_list):
    """
    Custom decorator to restrict access based on user roles.
    Takes a list of allowed roles.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # This should be handled by @login_required, but as a fallback:
                return redirect(url_for('main.login'))
            
            if current_user.role not in role_list:
                # User is logged in but doesn't have the right role
                flash('You do not have permission to access this page.', 'danger')
                return abort(403) # Forbidden
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
