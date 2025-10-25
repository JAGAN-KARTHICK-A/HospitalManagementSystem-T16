from flask import (
    render_template, flash, redirect, url_for, request, Blueprint, jsonify
)
from flask_login import login_user, logout_user, current_user, login_required

from flask import send_from_directory, current_app
from werkzeug.utils import secure_filename
from app.ai_stubs import analyze_complaint_with_ai
from app.models import (
    # ... (all your existing imports) ...
    # --- Add these new ones ---
    create_complaint, get_all_complaints, get_complaint_by_id,
    add_complaint_update, update_complaint_status_and_assignment,
    add_vitals_log, get_vitals_for_patient, search_patients, get_or_create_patient, get_patient_by_pid, get_all_patients
)
import os

from app.models import (
    get_user_by_username, create_user, get_users_created_by, ROLES, MODULES
)
from app.models import (
    get_user_by_username, create_user, get_users_created_by, ROLES, MODULES,
    # --- Add these ---
    create_doctor, get_all_doctors, get_doctor_by_id, update_doctor, delete_doctor,
    # --- Your existing appointment functions ---
    create_appointment, get_appointments_for_queue, 
    update_appointment_status, get_appointment_by_id,
    get_patient_by_id, search_patients,
    create_triage_entry, get_triage_queue, update_triage_status, get_triage_log_history,
    create_formulary_drug, get_all_formulary_drugs, delete_formulary_drug,
    create_lab_test, get_all_lab_tests, delete_lab_test,
    create_consultation, get_consultations_for_patient, get_triage_collection, get_consultation_history,
    get_consultation_by_triage_id,
    update_formulary_stock, get_billing_collection, create_billing_entry,
    get_billing_log, get_pending_prescriptions, dispense_prescription,
    update_billing_status, get_lab_order_queue, update_lab_order_status, submit_lab_result,
    get_total_patient_count, get_appointments_today_count,
    get_available_beds_count, get_pending_er_cases_count,
    get_unpaid_bills_for_patient, mark_patient_bills_paid,
    assign_doctor_to_triage
)

from app.utils import role_required
from datetime import datetime

from app.ai_stubs import analyze_complaint_with_ai, analyze_triage_with_ai, analyze_complaint_with_ai, analyze_triage_with_ai, analyze_drug_interactions
from bson import ObjectId

# From app.models
from app.models import (
    # ... (all your existing imports) ...
    mark_patient_bills_paid,
    # --- Add these ER functions ---
    create_er_case, get_er_queue, get_er_case_by_id,
    update_er_case_details, add_er_note_or_order, set_er_disposition,
    get_all_doctors, get_doctor_by_id # Also need doctor functions for assignment
)
# From app.ai_stubs (should already be there)
from app.ai_stubs import analyze_triage_with_ai

import pickle

# Define lists needed for dropdowns
ER_STATUSES = ["Waiting", "Assigned Doctor", "In-Treatment", "Observation", "Awaiting Disposition", "Discharged", "Admitted", "Transferred"]
DISPOSITION_DECISIONS = ["Discharged", "Admitted", "Transferred", "Observation"]


# Create a Blueprint named 'main'
main = Blueprint('main', __name__)

# --- Authentication Routes ---

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user_by_username(username)
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('Logged in successfully.', 'success')
            # Redirect to the page they were trying to access, or dashboard
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html', title='Login')

@main.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

# --- Core Application Routes ---

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    """Displays the main dashboard page with live stats."""
    
    # --- Fetch Live Stats ---
    total_patients = get_total_patient_count()
    appointments_today = get_appointments_today_count()
    available_beds, total_beds = get_available_beds_count() # Placeholder
    pending_er = get_pending_er_cases_count() # Placeholder
    
    # Create a dictionary to pass stats to the template
    stats = {
        "total_patients": total_patients,
        "appointments_today": appointments_today,
        "available_beds": available_beds,
        "total_beds": total_beds,
        "pending_er": pending_er
    }
    
    return render_template('dashboard.html', title='Dashboard', stats=stats)

# --- Admin Routes ---

@main.route('/manage-users', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def manage_users():
    """
    Page for Super Admins to create Module Admins,
    and for Module Admins to create Sub-users.
    """
    
    # Determine what this admin can create
    if current_user.role == 'SUPER_ADMIN':
        creatable_role = 'MODULE_ADMIN'
        creatable_modules = MODULES
        module_locked = False
    else: # current_user.role == 'MODULE_ADMIN'
        creatable_role = 'SUB_USER'
        creatable_modules = [current_user.module] # Can only create users for their own module
        module_locked = True
        
    if request.method == 'POST':
        # --- Handle User Creation ---
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        module = request.form.get('module')

        # --- Security & Validation ---
        if not username or not password:
            flash('Username and password are required.', 'danger')
        # Check if the admin is trying to create a role they are allowed to
        elif role != creatable_role:
            flash('You do not have permission to create this type of user.', 'danger')
        # Check if they are assigning a module they are allowed to
        elif module not in creatable_modules:
            flash('You do not have permission to assign this module.', 'danger')
        else:
            try:
                # Create the user, passing the current user's ID as 'created_by'
                user_id = create_user(username, password, role, module, current_user.id)
                if user_id:
                    flash(f'User "{username}" created successfully.', 'success')
                else:
                    flash(f'Username "{username}" already exists.', 'warning')
            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')
                
        return redirect(url_for('main.manage_users'))

    # --- Handle GET Request ---
    
    # Get the list of users this admin has already created
    created_users = get_users_created_by(current_user.id)
    
    return render_template(
        'manage_users.html',
        title='Manage Users',
        created_users=created_users,
        creatable_role=creatable_role,
        creatable_modules=creatable_modules,
        module_locked=module_locked
    )

# --- Stubs for Module Pages ---
# You will build these out. These are just placeholders.

@main.route('/registration', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def digital_registration():
    """
    Handles new patient registrations (online/offline/kiosk)
    and manages the digital queue.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
    
    # Handle New Appointment Creation
    if request.method == 'POST':
        try:
            # Get form data
            patient_name = request.form.get('patient_name')
            patient_contact = request.form.get('patient_contact')
            doctor_id = request.form.get('doctor_id')
            app_date = request.form.get('appointment_date')
            app_time = request.form.get('appointment_time')
            payment_status = request.form.get('payment_status')

            if not all([patient_name, patient_contact, doctor_id, app_date, app_time, payment_status]):
                flash('All fields are required.', 'danger')
                return redirect(url_for('main.digital_registration'))

            # --- NEW PATIENT LOGIC ---
            # Find or create a patient record
            patient = get_or_create_patient(patient_name, patient_contact)
            
            # Combine date and time into a datetime object
            appointment_time = datetime.strptime(f"{app_date} {app_time}", '%Y-%m-%d %H:%M')
            
            # Create the appointment, now linking to the patient's ObjectId
            create_appointment(
                patient_id=patient['_id'],
                patient_name=patient['patient_name'], # Pass name for denormalization
                doctor_id=doctor_id,
                appointment_time=appointment_time,
                payment_status=payment_status
            )
            
            flash(f"Appointment created for {patient['pid']} - {patient['patient_name']}.", 'success')
            
        except Exception as e:
            flash(f'Error creating appointment: {e}', 'danger')
            
        return redirect(url_for('main.digital_registration'))

    # Handle GET Request (Show form and queue)
    doctors = get_all_doctors() # Fetches from MongoDB
    queue = get_appointments_for_queue()
    
    # Get today's date for the date picker default
    today_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    return render_template(
        'registration.html', 
        title='Digital Registration & Queue',
        doctors=doctors,
        queue=queue,
        today_date=today_date
    )

@main.route('/queue/update/<string:appointment_id>/<string:new_status>')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def update_queue_status(appointment_id, new_status):
    """Updates a patient's status in the queue."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    try:
        if new_status not in ["CheckedIn", "Completed"]:
            flash("Invalid status update.", "danger")
        elif update_appointment_status(appointment_id, new_status):
            flash(f"Patient status updated to '{new_status}'.", "success")
        else:
            flash("Could not find or update appointment.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        
    return redirect(url_for('main.digital_registration'))

@main.route('/er-cases')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def er_case_management():
    """Placeholder for 'Emergency Case Management' module."""
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        return abort(403)
    return render_template('dashboard.html', title='ER Case Management')

@main.route('/manage-doctors', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def manage_doctors():
    """
    (Admin Only) Page to add and view doctors.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403) # Only Clinical Admins

    if request.method == 'POST':
        # --- Handle Add Doctor ---
        name = request.form.get('name')
        department = request.form.get('department')
        fee = request.form.get('consultation_fee') # Added fee

        if not name or not department or not fee:
            flash('Name, Department, and Fee are required.', 'danger')
        else:
            try:
                create_doctor(name, department, fee) # Pass fee
                flash(f'Doctor "{name}" added successfully.', 'success')
            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')

        return redirect(url_for('main.manage_doctors'))

    # --- Handle GET Request ---
    doctors = get_all_doctors()
    return render_template(
        'manage_doctors.html',
        title='Manage Doctors',
        doctors=doctors
    )

@main.route('/manage-doctors/edit/<string:doctor_id>', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def edit_doctor(doctor_id):
    """(Admin Only) Page to edit a doctor."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    doctor = get_doctor_by_id(doctor_id)
    if not doctor:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('main.manage_doctors'))

    if request.method == 'POST':
        name = request.form.get('name')
        department = request.form.get('department')
        
        if not name or not department:
            flash('Name and Department are required.', 'danger')
        else:
            try:
                update_doctor(doctor_id, name, department)
                flash(f'Doctor "{name}" updated successfully.', 'success')
                return redirect(url_for('main.manage_doctors'))
            except Exception as e:
                flash(f'An error occurred: {e}', 'danger')
        
    # --- Handle GET Request ---
    return render_template(
        'edit_doctor.html', 
        title='Edit Doctor', 
        doctor=doctor
    )

@main.route('/manage-doctors/delete/<string:doctor_id>')
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def delete_doctor_route(doctor_id):
    """(Admin Only) Route to delete a doctor."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    try:
        # We should check if this doctor has appointments first...
        # For simplicity, we'll just delete.
        # In production, you'd "deactivate" them instead.
        if delete_doctor(doctor_id):
            flash('Doctor deleted successfully.', 'success')
        else:
            flash('Doctor not found.', 'danger')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        
    return redirect(url_for('main.manage_doctors'))

@main.route('/complaints', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def complaint_portal():
    """
    Main portal for logging new complaints and viewing the dashboard.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)

    # --- Handle GET Request (Search & Select Patient) ---
    search_query = request.args.get('search_query')
    select_patient_id = request.args.get('select_patient_id')
    
    patients = []
    selected_patient = None

    if search_query:
        patients = search_patients(search_query)
        if not patients:
            flash('No patients found matching that name or PID.', 'warning')
    
    if select_patient_id:
        selected_patient = get_patient_by_id(select_patient_id)

    # --- Handle POST Request (Log Complaint) ---
    if request.method == 'POST':
        try:
            # Get data from the form (now includes patient ID)
            patient_id = request.form.get('patient_id')
            patient_name = request.form.get('patient_name')
            patient_contact = request.form.get('patient_contact')
            channel_source = request.form.get('channel_source')
            complaint_text = request.form.get('complaint_text')
            
            if not all([patient_id, patient_name, patient_contact, channel_source, complaint_text]):
                flash('All fields (including a selected patient) are required.', 'danger')
                return redirect(url_for('main.complaint_portal'))

            file_path = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                if file.filename != '':
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)

            # --- AI PROCESSING ---
            category, urgency = analyze_complaint_with_ai(complaint_text)
            
            # --- Update create_complaint call ---
            create_complaint(
                patient_id=patient_id,
                patient_name=patient_name,
                patient_contact=patient_contact,
                complaint_text=complaint_text,
                channel_source=channel_source,
                file_path=file_path,
                category=category,
                urgency=urgency,
                created_by_id=current_user.id
            )
            
            flash('New complaint logged successfully.', 'success')
            
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
            
        return redirect(url_for('main.complaint_portal'))

    # --- Handle GET Request (View Page) ---
    complaints = get_all_complaints()
    return render_template(
        'complaints.html',
        title='Complaint & Query Portal',
        complaints=complaints,
        patients=patients, # Pass search results
        selected_patient=selected_patient # Pass selected patient
    )

@main.route('/complaint/<string:complaint_id>', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def complaint_detail(complaint_id):
    """
    Page for viewing and resolving a single complaint ticket.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    complaint = get_complaint_by_id(complaint_id)
    if not complaint:
        flash('Complaint not found.', 'danger')
        return redirect(url_for('main.complaint_portal'))

    if request.method == 'POST':
        try:
            action = request.form.get('action')
            
            if action == 'add_update':
                comment = request.form.get('comment')
                if not comment:
                    flash('Comment cannot be empty.', 'warning')
                else:
                    add_complaint_update(complaint_id, current_user.username, comment)
                    flash('Update added to resolution log.', 'success')
                    
            elif action == 'update_status':
                new_status = request.form.get('status')
                assigned_to = request.form.get('assigned_to')
                update_complaint_status_and_assignment(complaint_id, new_status, assigned_to)
                flash('Ticket status and assignment updated.', 'success')
                
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
            
        return redirect(url_for('main.complaint_detail', complaint_id=complaint_id))

    # --- Handle GET Request ---
    return render_template(
        'complaint_detail.html',
        title='Complaint Details',
        complaint=complaint
    )

@main.route('/uploads/<path:filename>')
@login_required
def get_uploaded_file(filename):
    """Serves uploaded files."""
    try:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        abort(404)

# --- Vitals Logging (Module 3) ---

@main.route('/vitals-logging', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def vitals_logging():
    """
    Main page for finding a patient to log vitals for.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    patients = []
    if request.method == 'POST':
        query_text = request.form.get('search_query')
        if query_text:
            patients = search_patients(query_text)
            if not patients:
                flash('No patients found matching that name or PID.', 'warning')
        else:
            flash('Please enter a name or PID to search.', 'warning')
            
    return render_template(
        'vitals_logging.html',
        title="Vitals Logging",
        patients=patients
    )

@main.route('/vitals-logging/patient/<string:pid>', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def vitals_patient(pid):
    """
    Data entry form for a specific patient's vitals.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    patient = get_patient_by_pid(pid)
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('main.vitals_logging'))

    if request.method == 'POST':
        try:
            # Collect vitals data from the form
            vitals_data = {
                "bp_systolic": int(request.form.get('bp_systolic')),
                "bp_diastolic": int(request.form.get('bp_diastolic')),
                "heart_rate": int(request.form.get('heart_rate')),
                "temperature": float(request.form.get('temperature'))
            }
            
            # Add the log
            add_vitals_log(
                patient_id=patient['_id'],
                nurse_id=current_user.id,
                nurse_name=current_user.username,
                vitals_data=vitals_data
            )
            flash('Vitals logged successfully.', 'success')
            
        except Exception as e:
            flash(f'Error logging vitals: {e}', 'danger')
            
        return redirect(url_for('main.vitals_patient', pid=pid))
        
    # GET Request: Show the form and past vitals
    # The 'vitals' array is already sorted newest first by the database
    patient_vitals = patient.get("vitals", [])
    
    return render_template(
        'vitals_patient.html',
        title=f"Vitals for {patient['patient_name']}",
        patient=patient,
        patient_vitals=patient_vitals
    )

@main.route('/patient-list')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def patient_list():
    """
    Displays a list of all registered patients.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    patients = get_all_patients()
    
    return render_template(
        'patient_list.html',
        title="All Patients",
        patients=patients
    )

@main.route('/triage-dashboard', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def triage_dashboard():
    """
    Dashboard for triaging patients and viewing the prioritized queue.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    # --- Handle POST Request (Log Triage Entry) ---
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id')
            symptoms = request.form.get('symptoms')
            medical_history = request.form.get('medical_history')

            vitals_data = {
                "bp_systolic": int(request.form.get('bp_systolic')),
                "bp_diastolic": int(request.form.get('bp_diastolic')),
                "heart_rate": int(request.form.get('heart_rate')),
                "temperature": float(request.form.get('temperature'))
            }
            
            if not all([patient_id, symptoms, vitals_data]):
                flash('Patient, symptoms, and vitals are required.', 'danger')
            else:
                # --- AI PROCESSING ---
                ai_result = analyze_triage_with_ai(symptoms, vitals_data)
                
                # --- Create DB Entry ---
                create_triage_entry(
                    patient_id=patient_id,
                    nurse_id=current_user.id,
                    nurse_name=current_user.username,
                    symptoms=symptoms,
                    history=medical_history,
                    vitals_data=vitals_data,
                    ai_result=ai_result
                )
                flash(f"Patient added to queue with priority: {ai_result['level']}", 'success')
                
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
            
        return redirect(url_for('main.triage_dashboard'))
        
    # --- Handle GET Request (Show Page) ---
    # --- Handle GET Request (Show Page) ---
    search_query = request.args.get('search_query')
    select_patient_id = request.args.get('select_patient_id')
    
    patients = []
    selected_patient = None

    if search_query:
        patients = search_patients(search_query)
        if not patients:
            flash('No patients found matching that name or PID.', 'warning')
    
    if select_patient_id:
        selected_patient = get_patient_by_id(select_patient_id)
        
    triage_queue = get_triage_queue()
    doctors = get_all_doctors() # <-- ADDED: Fetch doctors for assignment dropdown
    
    return render_template(
        'triage_dashboard.html',
        title="Triage Dashboard",
        triage_queue=triage_queue,
        patients=patients,
        selected_patient=selected_patient,
        doctors=doctors # <-- ADDED: Pass doctors to template
    )

@main.route('/triage-update/<string:triage_id>/<string:new_status>')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def triage_update_status(triage_id, new_status):
    """Updates a patient's status in the triage queue."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    try:
        if update_triage_status(triage_id, new_status):
            flash(f"Patient status updated to '{new_status}'.", "success")
        else:
            flash("Could not update triage entry.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        
    # --- NEW LOGIC ---
    # If we are starting the consult, redirect to the consultation room
    if new_status == 'In-Progress':
        return redirect(url_for('main.consultation_room', triage_id=triage_id))
        
    return redirect(url_for('main.triage_dashboard'))

@main.route('/triage-log')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def triage_log():
    """
    Displays a complete log of all triage entries.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    triage_history = get_triage_log_history()
    
    return render_template(
        'triage_log.html',
        title="Triage Log",
        triage_history=triage_history
    )

@main.route('/manage-formulary/delete/<string:drug_id>')
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def delete_drug(drug_id):
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
    try:
        if delete_formulary_drug(drug_id):
            flash('Drug removed from formulary.', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
    return redirect(url_for('main.manage_formulary'))

@main.route('/manage-lab-tests', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def manage_lab_tests():
    """(Admin Only) Page to add and view lab tests."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)

    if request.method == 'POST':
        try:
            create_lab_test(
                test_name=request.form.get('test_name'),
                department=request.form.get('department'),
                unit_price=request.form.get('unit_price') # Added price
            )
            flash('Lab test added.', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('main.manage_lab_tests'))

    tests = get_all_lab_tests()
    return render_template('manage_lab_tests.html', title='Manage Lab Tests', tests=tests)

@main.route('/manage-lab-tests/delete/<string:test_id>')
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def delete_test(test_id):
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
    try:
        if delete_lab_test(test_id):
            flash('Lab test removed.', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
    return redirect(url_for('main.manage_lab_tests'))

@main.route('/consultation/<string:triage_id>', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def consultation_room(triage_id):
    """
    Main consultation interface for doctors.
    This route now handles both NEW (editable) and COMPLETED (read-only) consultations.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    # Get the triage data (vitals, symptoms)
    triage_entry = get_triage_collection().find_one({"_id": ObjectId(triage_id)})
    if not triage_entry:
        flash('Triage entry not found.', 'danger')
        return redirect(url_for('main.triage_dashboard'))
        
    # --- NEW LOGIC: Check if consultation is already done ---
    consultation = get_consultation_by_triage_id(triage_id)
    read_only = consultation is not None
    # --------------------------------------------------------

    if request.method == 'POST':
        # Don't allow POST if it's already completed
        if read_only:
            flash('This consultation has already been finalized.', 'warning')
            return redirect(url_for('main.consultation_room', triage_id=triage_id))

        try:
            # 1. Collect Consultation Notes
            notes = {
                "subjective": request.form.get('notes_subjective'),
                "objective": request.form.get('notes_objective'),
                "assessment": request.form.get('notes_assessment'),
                "plan": request.form.get('notes_plan')
            }
            
            # 2. Collect Prescriptions
            prescriptions = []
            med_names = request.form.getlist('med_name[]')
            med_dosages = request.form.getlist('med_dosage[]')
            med_instructions = request.form.getlist('med_instructions[]')
            for name, dosage, instructions in zip(med_names, med_dosages, med_instructions):
                if name and dosage and instructions:
                    prescriptions.append({
                        "name": name,
                        "dosage": dosage,
                        "instructions": instructions
                    })

                    # --- DEBUG PRINT ---
            print("\n--- Received Prescription Data ---")
            print(f"Med Names: {med_names}")
            print(f"Med Dosages: {med_dosages}")
            print(f"Med Instructions: {med_instructions}")
            # --------------------
                    
            # 3. Collect Investigation Orders
            investigation_orders = []
            test_names = request.form.getlist('test_name[]')
            test_notes = request.form.getlist('test_notes[]')
            for name, notes in zip(test_names, test_notes):
                if name:
                    investigation_orders.append({
                        "name": name,
                        "notes": notes
                    })
            
            # 4. Create the Consultation Record
            create_consultation(
                triage_id=triage_id,
                patient_id=triage_entry['patient_id'],
                doctor_id=current_user.id,
                doctor_name=current_user.username,
                notes=notes,
                prescriptions=prescriptions,
                investigation_orders=investigation_orders
            )
            
            # 5. Mark the Triage as "Completed"
            update_triage_status(triage_id, "Completed")
            
            flash('Consultation finalized and saved.', 'success')
            return redirect(url_for('main.triage_dashboard'))
            
        except Exception as e:
            flash(f'An error occurred while saving: {e}', 'danger')
            
    # --- Handle GET Request ---
    # Get data for the UI
    patient = get_patient_by_id(triage_entry['patient_id'])
    past_consultations = get_consultations_for_patient(patient['_id'])
    formulary = get_all_formulary_drugs()
    lab_tests = get_all_lab_tests()
    
    return render_template(
        'consultation_room.html',
        title=f"Consulting: {patient['patient_name']}",
        patient=patient,
        triage_entry=triage_entry,
        past_consultations=past_consultations,
        formulary=formulary,
        lab_tests=lab_tests,
        consultation=consultation, # Pass the completed consult (or None)
        read_only=read_only         # Pass the read-only flag
    )

@main.route('/api/check-interactions', methods=['POST'])
@login_required
def api_check_interactions():
    """
    AJAX endpoint for checking drug interactions.
    """
    data = request.get_json()
    med_list = data.get('medications', [])
    if not med_list:
        return ({"error": "No medications provided"}, 400)
        
    result = analyze_drug_interactions(med_list)
    return (result, 200)

@main.route('/consultation-log')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def consultation_log():
    """Displays a complete log of all finalized consultations."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
    
    history = get_consultation_history()
    
    return render_template(
        'consultation_log.html',
        title="Consultation Log",
        history=history
    )

@main.route('/manage-formulary', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN'])
def manage_formulary():
    """(Admin Only) Page to add and view formulary drugs."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)

    if request.method == 'POST':
        try:
            create_formulary_drug(
                drug_name=request.form.get('drug_name'),
                brand_name=request.form.get('brand_name'),
                dosage_form=request.form.get('dosage_form'),
                stock_level=request.form.get('stock_level'),
                unit_price=request.form.get('unit_price'),
                low_stock_threshold=request.form.get('low_stock_threshold')
            )
            flash('Drug added to formulary.', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('main.manage_formulary'))

    drugs = get_all_formulary_drugs()
    return render_template('manage_formulary.html', title='Manage Formulary', drugs=drugs)

@main.route('/pharmacy', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def pharmacy_dashboard():
    """
    Main Pharmacy dashboard. Shows pending prescriptions and formulary.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    pending_rx = get_pending_prescriptions()
    formulary = get_all_formulary_drugs()
    
    return render_template(
        'pharmacy.html',
        title="Pharmacy Dashboard",
        pending_rx=pending_rx,
        formulary=formulary
    )

@main.route('/pharmacy/dispense', methods=['POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def pharmacy_dispense():
    """
    Handles the POST request to dispense a medication.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
    
    try:
        dispense_prescription(
            consultation_id=request.form.get('consultation_id'),
            prescription_id=request.form.get('prescription_id'),
            formulary_id=request.form.get('formulary_id'),
            quantity=request.form.get('quantity'),
            user_name=current_user.username
        )
        flash('Medication dispensed and billed successfully.', 'success')
    except Exception as e:
        flash(f'Error dispensing: {e}', 'danger')
        
    return redirect(url_for('main.pharmacy_dashboard'))

@main.route('/pharmacy/stock', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def pharmacy_stock():
    """
    Stock Management (GRN) page.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    if request.method == 'POST':
        try:
            formulary_id = request.form.get('formulary_id')
            quantity = int(request.form.get('quantity'))
            
            if quantity <= 0:
                flash('Quantity must be a positive number.', 'danger')
            else:
                update_formulary_stock(formulary_id, quantity)
                flash('Stock updated successfully.', 'success')
        except Exception as e:
            flash(f'Error updating stock: {e}', 'danger')
        
        return redirect(url_for('main.pharmacy_stock'))
        
    # GET Request
    formulary = get_all_formulary_drugs()
    return render_template(
        'pharmacy_stock.html',
        title="Stock Management (GRN)",
        formulary=formulary
    )

@main.route('/billing-log')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def billing_log():
    """
    Shows a log of all billing entries.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    billing_history = get_billing_log()
    return render_template(
        'billing_log.html',
        title="Billing Log",
        billing_history=billing_history
    )

@main.route('/billing/mark-paid/<string:billing_id>')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def mark_bill_paid(billing_id):
    """Marks a single billing item as 'Paid'."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    try:
        if update_billing_status(billing_id, "Paid"):
            flash('Bill item marked as Paid.', 'success')
        else:
            flash('Could not update status.', 'danger')
    except Exception as e:
        flash(f'Error updating status: {e}', 'danger')
        
    return redirect(url_for('main.billing_log'))

@main.route('/lab/sample-collection')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def lab_sample_collection():
    """
    Shows the queue of patients waiting for lab samples to be collected.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    queue = get_lab_order_queue(["Pending Sample"])
    return render_template(
        'lab_sample_collection.html',
        title="Lab Sample Collection Queue",
        queue=queue
    )

@main.route('/lab/collect-sample/<string:consultation_id>/<string:order_id>')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def lab_collect_sample(consultation_id, order_id):
    """
    Action route to mark a sample as collected.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    try:
        update_lab_order_status(
            consultation_id, order_id, "Sample Collected", current_user.username
        )
        flash('Sample marked as collected. Sent to lab workbench.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
        
    return redirect(url_for('main.lab_sample_collection'))

@main.route('/lab/workbench', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def lab_workbench():
    """
    Shows the lab tech's workbench for entering results.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    if request.method == 'POST':
        try:
            consultation_id = request.form.get('consultation_id')
            order_id = request.form.get('order_id')
            result_text = request.form.get('result_text')
            
            submit_lab_result(
                consultation_id, order_id, result_text, current_user.username
            )
            flash('Result submitted, verified, and billed.', 'success')
        except Exception as e:
            flash(f'Error submitting result: {e}', 'danger')
            
        return redirect(url_for('main.lab_workbench'))
        
    # GET Request
    queue = get_lab_order_queue(["Sample Collected"])
    return render_template(
        'lab_workbench.html',
        title="Lab Workbench",
        queue=queue
    )

@main.route('/patient-billing', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def patient_billing():
    """
    Search for a patient and view their consolidated unpaid bill.
    """
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)

    search_query = request.args.get('search_query')
    select_patient_id = request.args.get('select_patient_id')

    patients = []
    selected_patient = None
    unpaid_bills = []
    total_due = 0.0

    if search_query:
        patients = search_patients(search_query)
        if not patients:
            flash('No patients found matching that name or PID.', 'warning')

    if select_patient_id:
        selected_patient = get_patient_by_id(select_patient_id)
        if selected_patient:
            unpaid_bills = get_unpaid_bills_for_patient(selected_patient['_id'])
            total_due = sum(item['total_amount'] for item in unpaid_bills)

    return render_template(
        'patient_billing.html',
        title="Patient Billing",
        patients=patients,
        selected_patient=selected_patient,
        unpaid_bills=unpaid_bills,
        total_due=total_due
    )

@main.route('/patient-billing/mark-paid/<string:patient_id>')
@login_required
@role_required(['SUPER_ADMIN', 'SUB_USER', 'MODULE_ADMIN'])
def mark_patient_bill_paid(patient_id):
    """Marks all unpaid bills for a patient as paid."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)

    try:
        modified_count = mark_patient_bills_paid(patient_id)
        if modified_count > 0:
            flash(f'{modified_count} bill items marked as Paid.', 'success')
        else:
            flash('No unpaid bills found for this patient.', 'info')
    except Exception as e:
        flash(f'Error marking bills paid: {e}', 'danger')

    # Redirect back to the patient billing page for the same patient
    return redirect(url_for('main.patient_billing', select_patient_id=patient_id))

@main.route('/triage-assign-doctor/<string:triage_id>', methods=['POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN']) # Only admins can assign for now
def assign_triage_doctor(triage_id):
    """Assigns a doctor to a triage queue entry."""
    if current_user.module not in ['CLINICAL', 'ALL']:
        return abort(403)
        
    doctor_id = request.form.get('doctor_id')
    if not doctor_id:
        flash('Please select a doctor to assign.', 'danger')
        return redirect(url_for('main.triage_dashboard'))
        
    try:
        doctor = get_doctor_by_id(doctor_id)
        if not doctor:
             flash('Selected doctor not found.', 'danger')
        elif assign_doctor_to_triage(triage_id, doctor_id, doctor['name']):
            flash(f"Patient assigned to {doctor['name']}.", 'success')
        else:
             flash('Failed to assign doctor.', 'danger')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        
    return redirect(url_for('main.triage_dashboard'))


# ======================================
# EMERGENCY & LEGAL MODULE ROUTES
# ======================================

@main.route('/er-dashboard', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER']) # Allow Sub Users too
def er_dashboard():
    """ER Dashboard: Shows queue and allows new case registration."""
    # Check access permission
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    # --- Handle POST for New Case Registration ---
    if request.method == 'POST':
        # ... (Same POST logic as before) ...
        try:
            patient_id = request.form.get('patient_id')
            pre_hospital = request.form.get('pre_hospital_info')
            symptoms = request.form.get('symptoms')
            vitals_data = {
                "bp_systolic": int(request.form.get('bp_systolic')),
                "bp_diastolic": int(request.form.get('bp_diastolic')),
                "heart_rate": int(request.form.get('heart_rate')),
                "temperature": float(request.form.get('temperature'))
            }

            if not patient_id or not symptoms or not vitals_data.get('bp_systolic'): # Basic check
                flash('Patient, Symptoms, and Vitals are required.', 'danger')
            else:
                ai_result = analyze_triage_with_ai(symptoms, vitals_data)
                case_id = create_er_case(
                    patient_id=patient_id, pre_hospital_info=pre_hospital, symptoms=symptoms,
                    vitals_data=vitals_data, ai_triage_result=ai_result,
                    registered_by_id=current_user.id, registered_by_name=current_user.username
                )
                flash(f"New ER case registered (ID: ...{str(case_id)[-6:]}) with priority {ai_result['score']}.", 'success')
        except Exception as e:
            flash(f'Error registering ER case: {e}', 'danger')
        return redirect(url_for('main.er_dashboard')) # Redirect to GET

    # --- Handle GET Request ---
    search_query = request.args.get('search_query')
    select_patient_id = request.args.get('select_patient_id')
    patients = []
    selected_patient = None

    if search_query:
        patients = search_patients(search_query)
        if not patients: flash('No patients found.', 'warning')
    if select_patient_id:
        selected_patient = get_patient_by_id(select_patient_id)

    er_queue = get_er_queue()
    doctors = get_all_doctors() # For assignment dropdown

    return render_template(
        'er_dashboard.html', # Template now in main templates folder
        title="ER Dashboard",
        er_queue=er_queue,
        patients=patients,
        selected_patient=selected_patient,
        doctors=doctors, # Pass doctors
        er_statuses=ER_STATUSES # Pass statuses
    )

@main.route('/er-case/<string:case_id>', methods=['GET', 'POST'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER'])
def er_case_detail(case_id):
    """View details and manage a specific ER case."""
    # Check access permission
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    er_case = get_er_case_by_id(case_id)
    if not er_case:
        flash('ER Case not found.', 'danger')
        return redirect(url_for('main.er_dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add_note':
                note_text = request.form.get('note_text')
                if note_text:
                    add_er_note_or_order(case_id, note_text, 'note', current_user.username)
                    flash('Case note added.', 'success')
                else: flash('Note cannot be empty.', 'warning')

            elif action == 'add_order':
                order_text = request.form.get('order_text')
                if order_text:
                    add_er_note_or_order(case_id, order_text, 'order', current_user.username)
                    flash('Treatment order added.', 'success')
                else: flash('Order text cannot be empty.', 'warning')

            elif action == 'update_details':
                status = request.form.get('status')
                location = request.form.get('current_location')
                doctor_id = request.form.get('assigned_doctor_id')
                doctor_name = None
                if doctor_id:
                    doctor = get_doctor_by_id(doctor_id)
                    if doctor: doctor_name = doctor['name']
                update_er_case_details(case_id, status=status, location=location,
                                        assigned_doctor_id=doctor_id, assigned_doctor_name=doctor_name)
                flash('Case details updated.', 'success')

            elif action == 'set_disposition':
                decision = request.form.get('disposition_decision')
                notes = request.form.get('disposition_notes')
                if decision:
                    set_er_disposition(case_id, decision, notes, current_user.username)
                    flash(f'Disposition set to {decision}.', 'success')
                    if decision in ["Admitted", "Discharged", "Transferred"]:
                        return redirect(url_for('main.er_dashboard')) # Go back to dashboard if case closed
                else: flash('Please select a disposition decision.', 'warning')

        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

        return redirect(url_for('main.er_case_detail', case_id=case_id)) # Redirect back to detail page

    # --- Handle GET Request ---
    doctors = get_all_doctors() # For assignment dropdown
    return render_template(
        'er_case_detail.html', # Template now in main templates folder
        title=f"ER Case: {er_case['pid']}",
        er_case=er_case,
        doctors=doctors,
        er_statuses=ER_STATUSES,
        disposition_decisions=DISPOSITION_DECISIONS
    )

# ... (inside EMERGENCY & LEGAL MODULE ROUTES section) ...

@main.route('/mlc-add-log', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER'])
def mlc_add_log_page():
    """Renders the page for adding a new MLC log to the blockchain."""
    # Check access permission
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('mlc_add_log.html', title="Add MLC Blockchain Log")

@main.route('/mlc-view-log', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER'])
def mlc_view_log_page():
    """Renders the page for viewing MLC logs by Case ID."""
    # Check access permission
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Case ID might be passed as a query parameter for pre-filling search
    case_id_query = request.args.get('case_id', '')
    return render_template('mlc_view_log.html', title="View MLC Blockchain Log", case_id_query=case_id_query)


@main.route('/mlc-view-all-logs', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN']) # Maybe restrict who can see ALL logs
def mlc_view_all_logs_page():
    """Renders the page for viewing all MLC logs from the blockchain."""
    # Check access permission
    if current_user.module not in ['EMERGENCY_LEGAL', 'ALL']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('mlc_view_all_logs.html', title="View All MLC Blockchain Logs")

def save_emergency(location, content, level):
    if os.path.exists("./emergencies.bin"):
        f = open("./emergencies.bin", "rb")
        d = pickle.loads(f.read())
        f.close()
        d.append({"location":location, "content":content, "level":level})
        f = open("./emergencies.bin", "wb")
        f.write(pickle.dumps(d))
        f.close()
    else:
        f = open("./emergencies.bin", "wb")
        f.write(pickle.dumps([]))
        f.close()

def get_emergencies():
    if os.path.exists("./emergencies.bin"):
        f = open("./emergencies.bin", "rb")
        d = pickle.loads(f.read())
        f.close()
        return d
    else:
        f = open("./emergencies.bin", "wb")
        f.write(pickle.dumps([]))
        f.close()
        return []

@main.route('/emergencies', methods=['GET'])
@login_required
@role_required(['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER'])
def list_emergencies():
    data = get_emergencies()
    return render_template("list_ers.html", cases=data)

@main.route('/reg-er', methods=['POST'])
def register_emergency():
    if request.method == "POST":
        location = request.json.get("location")
        content = request.json.get("content")
        level = request.json.get("level")
        save_emergency(location, content, level)
        return "Ok"

