from app.db import get_db
from app import bcrypt
from flask_login import UserMixin
from bson import ObjectId
from datetime import datetime
from datetime import timedelta, time

# --- User Roles and Modules ---
# These constants define the core architecture of your application
ROLES = ['SUPER_ADMIN', 'MODULE_ADMIN', 'SUB_USER']
MODULES = ['CLINICAL', 'EMERGENCY_LEGAL', 'SUPPORT_FACILITY', 'ENGINEERING_INFRA']

class User(UserMixin):
    """
    Custom User class for Flask-Login with MongoDB.
    This class is NOT a database model itself, but an object
    representation of a user document from MongoDB.
    """
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.password_hash = user_data['password_hash']
        self.role = user_data['role']
        self.module = user_data['module']
        self.created_by = user_data.get('created_by') # Use .get for optional field

    def check_password(self, password):
        """Check if a provided password matches the hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Return a dictionary representation of the user."""
        return {
            '_id': ObjectId(self.id),
            'username': self.username,
            'role': self.role,
            'module': self.module,
            'created_by': self.created_by
        }

# --- Database Helper Functions ---

def get_user_collection():
    """Helper to get the 'users' collection from MongoDB."""
    db = get_db()
    return db.users

def get_user_by_id(user_id):
    """Fetch a user by their MongoDB ObjectId string."""
    try:
        users = get_user_collection()
        user_data = users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception as e:
        print(f"Error fetching user by ID: {e}")
        return None
    return None

def get_user_by_username(username):
    """Fetch a user by their username."""
    users = get_user_collection()
    user_data = users.find_one({'username': username})
    if user_data:
        return User(user_data)
    return None

def create_user(username, password, role, module, created_by_id):
    """Create a new user in the database."""
    if get_user_by_username(username):
        return None  # User already exists
    
    users = get_user_collection()
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    user_doc = {
        'username': username,
        'password_hash': hashed_password,
        'role': role,
        'module': module,
        'created_by': created_by_id
    }
    
    result = users.insert_one(user_doc)
    return result.inserted_id

def create_super_admin_user(username, password):
    """A special function to create the first Super Admin."""
    if get_user_by_username(username):
        return None # Admin already exists
        
    users = get_user_collection()
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    user_doc = {
        'username': username,
        'password_hash': hashed_password,
        'role': 'SUPER_ADMIN',
        'module': 'ALL', # Super Admin has access to all modules
        'created_by': None
    }
    
    result = users.insert_one(user_doc)
    return result.inserted_id

def get_users_created_by(admin_id):
    """Fetch all users created by a specific admin."""
    users = get_user_collection()
    # Find users where 'created_by' matches the admin's ID
    user_list = users.find({'created_by': admin_id})
    # Convert to User objects, sorting by username
    return sorted([User(user_data) for user_data in user_list], key=lambda x: x.username)

# --- Doctor Management ---

def get_doctor_collection():
    """Helper to get the 'doctors' collection."""
    db = get_db()
    return db.doctors

def create_doctor(name, department, consultation_fee):
    """Creates a new doctor in the database."""
    doctors = get_doctor_collection()

    doctor_doc = {
        "name": name,
        "department": department,
        "consultation_fee": float(consultation_fee), # Added fee
        "created_at": datetime.utcnow()
    }

    result = doctors.insert_one(doctor_doc)
    return result.inserted_id

def get_all_doctors():
    """Fetches all doctors, sorted by name."""
    doctors = get_doctor_collection()
    return list(doctors.find().sort("name", 1))

def get_doctor_by_id(doctor_id):
    """Fetches a single doctor by their ID."""
    doctors = get_doctor_collection()
    try:
        return doctors.find_one({"_id": ObjectId(doctor_id)})
    except:
        return None

def update_doctor(doctor_id, name, department):
    """Updates an existing doctor's details."""
    doctors = get_doctor_collection()
    try:
        result = doctors.update_one(
            {"_id": ObjectId(doctor_id)},
            {"$set": {"name": name, "department": department}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating doctor: {e}")
        return False

def delete_doctor(doctor_id):
    """Deletes a doctor from the database."""
    doctors = get_doctor_collection()
    try:
        result = doctors.delete_one({"_id": ObjectId(doctor_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting doctor: {e}")
        return False

def get_appointment_collection():
    """Helper to get the 'appointments' collection."""
    db = get_db()
    return db.appointments

def create_appointment(patient_id, patient_name, doctor_id, appointment_time, payment_status):
    """Creates a new patient appointment, linked to a patient ID."""
    
    # Get the doctor's details from the doctors collection
    doctor = get_doctor_by_id(doctor_id)
    if not doctor:
        raise ValueError("Doctor not found for the given ID")
        
    appointments = get_appointment_collection()
    
    appointment_doc = {
        "patient_id": patient_id, # <-- This is the new linkage
        "patient_name": patient_name, # <-- Denormalized for easy display
        "doctor_id": ObjectId(doctor_id),
        "doctor_name": doctor['name'],
        "department": doctor['department'],
        "appointment_time": appointment_time,
        "payment_status": payment_status,
        "status": "Pending",
        "created_at": datetime.utcnow()
    }
    
    result = appointments.insert_one(appointment_doc)
    return result.inserted_id

def get_appointments_for_queue(date_str=None):
    """
    Fetches appointments for the queue.
    We'll use $lookup to join with patient data (e.g., to get PID)
    """
    appointments = get_appointment_collection()
    
    query = {"status": {"$in": ["Pending", "CheckedIn"]}}

    # Use MongoDB Aggregation Pipeline to join with patients
    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient_details"
            }
        },
        {"$unwind": "$patient_details"}, # Deconstruct the array
        {
            "$sort": {
                "appointment_time": 1,
                "created_at": 1
            }
        }
    ]
    
    return list(appointments.aggregate(pipeline))

def get_appointment_by_id(appointment_id):
    """Fetches a single appointment by its ID."""
    appointments = get_appointment_collection()
    try:
        return appointments.find_one({"_id": ObjectId(appointment_id)})
    except:
        return None

def update_appointment_status(appointment_id, new_status):
    """Updates the status of an appointment (e.g., 'CheckedIn', 'Completed')."""
    appointments = get_appointment_collection()
    
    if new_status not in ["Pending", "CheckedIn", "Completed"]:
        raise ValueError("Invalid status")

    try:
        result = appointments.update_one(
            {"_id": ObjectId(appointment_id)},
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating status: {e}")
        return False

# --- Complaint Management ---

def get_complaint_collection():
    """Helper to get the 'complaints' collection."""
    db = get_db()
    return db.complaints

def create_complaint(patient_id, patient_name, patient_contact, complaint_text, channel_source, file_path, category, urgency, created_by_id):
    """Logs a new complaint ticket in the database, linked to a patient."""
    complaints = get_complaint_collection()
    
    complaint_doc = {
        "patient_id": ObjectId(patient_id), # <-- Link to patient
        "patient_name": patient_name, # Denormalized for easy display
        "patient_contact": patient_contact, # Denormalized for easy display
        "complaint_text": complaint_text,
        "channel_source": channel_source,
        "attachment_path": file_path,
        "category": category,
        "urgency": urgency,
        "status": "New", # Status: New, Assigned, In Progress, Resolved, Closed
        "assigned_to": None,
        "created_at": datetime.utcnow(),
        "created_by": ObjectId(created_by_id),
        "updates": [] # A log of all actions on this ticket
    }
    
    result = complaints.insert_one(complaint_doc)
    return result.inserted_id

def get_all_complaints():
    """Fetches all complaints, sorted by urgency and date."""
    complaints = get_complaint_collection()
    
    # Define a custom sort order for urgency
    urgency_sort = {'High': 1, 'Medium': 2, 'Low': 3}
    
    all_complaints = list(complaints.find().sort("created_at", -1)) # Sort by newest first
    
    # Sort by urgency using Python
    all_complaints.sort(key=lambda x: (urgency_sort.get(x['urgency'], 4), x['created_at']))
    
    return all_complaints

def get_complaint_by_id(complaint_id):
    """Fetches a single complaint by its ID."""
    complaints = get_complaint_collection()
    try:
        return complaints.find_one({"_id": ObjectId(complaint_id)})
    except:
        return None

def add_complaint_update(complaint_id, user_name, comment):
    """Adds a resolution note or update to a complaint ticket."""
    complaints = get_complaint_collection()
    
    update_doc = {
        "user_name": user_name,
        "comment": comment,
        "timestamp": datetime.utcnow()
    }
    
    result = complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$push": {"updates": update_doc}}
    )
    return result.modified_count > 0

def update_complaint_status_and_assignment(complaint_id, new_status, assigned_to_name):
    """Updates the ticket's status and who it is assigned to."""
    complaints = get_complaint_collection()
    
    result = complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {
            "status": new_status,
            "assigned_to": assigned_to_name
        }}
    )
    return result.modified_count > 0

def get_next_sequence_value(sequence_name):
    """Gets the next auto-incrementing ID from the counters collection."""
    db = get_db()
    counters = db.counters
    
    # Find the sequence and increment it.
    # upsert=True creates the doc if it doesn't exist.
    sequence_doc = counters.find_one_and_update(
        {'_id': sequence_name},
        {'$inc': {'sequence_value': 1}},
        return_document=True,
        upsert=True
    )
    
    # The first time this runs, sequence_doc might not have sequence_value
    if 'sequence_value' not in sequence_doc:
        # It was just created, so the value is 1
        return 1
    
    return sequence_doc['sequence_value']

# --- Patient Management ---

def get_patient_collection():
    """Helper to get the 'patients' collection."""
    db = get_db()
    return db.patients

def get_or_create_patient(patient_name, patient_contact):
    """
    Finds a patient by contact number. If they don't exist,
    creates a new patient record with a unique Patient ID (PID).
    Returns the full patient document.
    """
    patients = get_patient_collection()
    
    # Try to find an existing patient by contact number
    existing_patient = patients.find_one({"patient_contact": patient_contact})
    
    if existing_patient:
        print(f"Found existing patient: {existing_patient['pid']}")
        return existing_patient
    
    # --- Create New Patient ---
    # Get the next unique PID
    next_id = get_next_sequence_value("patient_id")
    pid = f"PID-{10000 + next_id}" # e.g., PID-10001
    
    patient_doc = {
        "pid": pid,
        "patient_name": patient_name,
        "patient_contact": patient_contact,
        "created_at": datetime.utcnow(),
        "vitals": [] # We will store vital logs here
    }
    
    result = patients.insert_one(patient_doc)
    patient_doc['_id'] = result.inserted_id
    
    print(f"Created new patient: {pid}")
    return patient_doc

def get_patient_by_pid(pid):
    """Finds a single patient by their human-readable PID."""
    patients = get_patient_collection()
    return patients.find_one({"pid": pid})

def get_patient_by_id(patient_id):
    """Finds a single patient by their MongoDB ObjectId."""
    patients = get_patient_collection()
    try:
        return patients.find_one({"_id": ObjectId(patient_id)})
    except:
        return None

def search_patients(query_text):
    """Searches for patients by name or PID."""
    patients = get_patient_collection()
    
    # Create a text index on 'pid' and 'patient_name' in MongoDB
    # You must run this in mongo shell once:
    # db.patients.createIndex({ "pid": "text", "patient_name": "text" })
    
    # For simplicity without indexing, we use $regex
    return list(patients.find({
        "$or": [
            {"pid": {"$regex": query_text, "$options": "i"}},
            {"patient_name": {"$regex": query_text, "$options": "i"}}
        ]
    }).limit(20))

# --- Vitals Logging (Module 3) ---

def _check_vitals_anomalies(vitals_data):
    """
    Performs anomaly detection on vitals data.
    Returns a list of alerts.
    """
    alerts = []
    
    # Blood Pressure
    bp_s = vitals_data.get('bp_systolic')
    bp_d = vitals_data.get('bp_diastolic')
    if bp_s and bp_d:
        if bp_s > 140 or bp_d > 90:
            alerts.append(f"Hypertension Alert (Stage 1/2): {bp_s}/{bp_d} mmHg")
        if bp_s < 90 or bp_d < 60:
            alerts.append(f"Hypotension Alert: {bp_s}/{bp_d} mmHg")

    # Heart Rate
    hr = vitals_data.get('heart_rate')
    if hr:
        if hr > 100:
            alerts.append(f"Tachycardia Alert: {hr} bpm")
        if hr < 60:
            alerts.append(f"Bradycardia Alert: {hr} bpm")
            
    # Temperature (F)
    temp = vitals_data.get('temperature')
    if temp:
        if temp > 100.4:
            alerts.append(f"Fever Alert: {temp}°F")
        if temp < 95.0:
            alerts.append(f"Hypothermia Alert: {temp}°F")
            
    return alerts

def add_vitals_log(patient_id, nurse_id, nurse_name, vitals_data):
    """
    Adds a new vitals log to a patient's record.
    This also performs anomaly detection.
    """
    patients = get_patient_collection()
    
    # Perform anomaly detection
    alerts = _check_vitals_anomalies(vitals_data)
    
    vitals_log_doc = {
        "_id": ObjectId(), # Generate a new ID for this sub-document
        "nurse_id": nurse_id,
        "nurse_name": nurse_name,
        "logged_at": datetime.utcnow(),
        "vitals": vitals_data,
        "alerts": alerts # Store the alerts
    }
    
    # Push this log into the patient's "vitals" array
    result = patients.update_one(
        {"_id": ObjectId(patient_id)},
        {
            "$push": {
                "vitals": {
                    "$each": [vitals_log_doc],
                    "$sort": {"logged_at": -1} # Keep the array sorted, newest first
                }
            }
        }
    )
    
    return result.modified_count > 0

def get_vitals_for_patient(patient_id):
    """
    Gets all vitals for a patient.
    (This is now just part of the patient document)
    """
    patient = get_patient_by_id(patient_id)
    if patient:
        return patient.get("vitals", [])
    return []

def get_all_patients():
    """Fetches all patients, sorted by PID."""
    patients = get_patient_collection()
    return list(patients.find().sort("pid", 1)) # Sort by PID ascending


# --- Triage Management (Module 4) ---

def get_triage_collection():
    """Helper to get the 'triage_log' collection."""
    db = get_db()
    return db.triage_log

def create_triage_entry(patient_id, nurse_id, nurse_name, symptoms, history, vitals_data, ai_result):
    """Creates a new entry in the triage log."""
    triage_log = get_triage_collection()

    patient = get_patient_by_id(patient_id)
    if not patient:
        raise ValueError("Patient not found.")

    triage_doc = {
        "patient_id": patient_id,
        "pid": patient['pid'],
        "patient_name": patient['patient_name'],
        "triage_by_id": nurse_id,
        "triage_by_name": nurse_name,
        "triage_at": datetime.utcnow(),
        "symptoms": symptoms,
        "medical_history": history,
        "vitals": vitals_data,
        "risk_score": ai_result['score'],
        "priority_level": ai_result['level'],
        "status": "Waiting", # Status: Waiting, Assigned, In-Progress, Completed
        "assigned_doctor_id": None, # <-- NEW FIELD
        "assigned_doctor_name": None # <-- NEW FIELD
    }

    result = triage_log.insert_one(triage_doc)
    return result.inserted_id

def get_triage_queue():
    """Gets all patients in 'Waiting', 'Assigned', or 'In-Progress' status, prioritized."""
    triage_log = get_triage_collection()

    # Sort by risk_score (1 is highest priority), then by time (oldest first)
    return list(triage_log.find(
        # --- THIS IS THE CRITICAL LINE ---
        {"status": {"$in": ["Waiting", "Assigned", "In-Progress"]}}
        # ---------------------------------
    ).sort([
        ("risk_score", 1), # ASC, so 1 comes before 5
        ("triage_at", 1)   # ASC, so oldest comes first
    ]))

def update_triage_status(triage_id, new_status):
    """Updates the status of a triage entry."""
    triage_log = get_triage_collection()
    print(f"MODEL: Attempting to update triage_id {triage_id} to status '{new_status}'") # DEBUG

    # Allow transition from Assigned -> In-Progress
    if new_status not in ["Waiting", "Assigned", "In-Progress", "Completed"]:
        print(f"MODEL: Invalid status '{new_status}' received.") # DEBUG
        raise ValueError("Invalid status")

    try:
        # Ensure we only allow valid transitions (e.g., don't go back from Completed)
        current_entry = triage_log.find_one({"_id": ObjectId(triage_id)})
        if not current_entry:
            print(f"MODEL: Triage entry {triage_id} not found for status update.")
            return False
        
        # Add rules here if needed, e.g.,
        # if current_entry['status'] == 'Completed' and new_status != 'Completed':
        #     print("MODEL: Cannot change status from Completed.")
        #     return False

        result = triage_log.update_one(
            {"_id": ObjectId(triage_id)},
            {"$set": {"status": new_status}}
        )
        print(f"MODEL: Update result for {triage_id}: Matched={result.matched_count}, Modified={result.modified_count}") # DEBUG
        return result.modified_count > 0
    except Exception as e:
        print(f"MODEL: Database error updating status for {triage_id}: {e}") # DEBUG
        # Re-raise the exception so the route's try/except catches it
        raise e
    
def get_triage_log_history():
    """Gets all triage entries, sorted by most recent."""
    triage_log = get_triage_collection()
    return list(triage_log.find().sort("triage_at", -1)) # Sort by newest first

# --- Formulary Management (Module 5) ---

def get_formulary_collection():
    """Helper to get the 'formulary' (drug list) collection."""
    db = get_db()
    return db.formulary

def create_formulary_drug(drug_name, brand_name, dosage_form, stock_level, unit_price, low_stock_threshold):
    """Adds a new drug to the hospital's formulary (inventory)."""
    formulary = get_formulary_collection()
    drug_doc = {
        "drug_name": drug_name.lower(), # For searching
        "brand_name": brand_name,
        "dosage_form": dosage_form, # e.g., "500mg Tablet"
        "stock_level": int(stock_level),
        "unit_price": float(unit_price),
        "low_stock_threshold": int(low_stock_threshold),
        "created_at": datetime.utcnow()
    }
    return formulary.insert_one(drug_doc).inserted_id

def get_all_formulary_drugs():
    """Gets all drugs, sorted by name."""
    return list(get_formulary_collection().find().sort("drug_name", 1))

def delete_formulary_drug(drug_id):
    """Deletes a drug from the formulary."""
    return get_formulary_collection().delete_one({"_id": ObjectId(drug_id)}).deleted_count > 0

# --- Lab Test Management (Module 5) ---

def get_lab_test_collection():
    """Helper to get the 'lab_tests' collection."""
    db = get_db()
    return db.lab_tests

def create_lab_test(test_name, department, unit_price):
    """Adds a new lab test to the hospital's list."""
    lab_tests = get_lab_test_collection()
    test_doc = {
        "test_name": test_name.lower(), # For searching
        "department": department, # e.g., "Pathology", "Radiology"
        "unit_price": float(unit_price),
        "created_at": datetime.utcnow()
    }
    return lab_tests.insert_one(test_doc).inserted_id

def get_all_lab_tests():
    """Gets all tests, sorted by name."""
    return list(get_lab_test_collection().find().sort("test_name", 1))

def delete_lab_test(test_id):
    """Deletes a lab test from the list."""
    return get_lab_test_collection().delete_one({"_id": ObjectId(test_id)}).deleted_count > 0

# --- Consultation Management (Module 5) ---

def get_consultation_collection():
    """Helper to get the 'consultations' collection."""
    db = get_db()
    return db.consultations

def create_consultation(triage_id, patient_id, doctor_id, doctor_name, notes, prescriptions, investigation_orders):
    """
    Creates a complete consultation record, linking notes, prescriptions,
    and orders to a patient and a triage event. Also adds billing entry.
    """
    consultations = get_consultation_collection()

    # --- Process Prescriptions ---
    processed_prescriptions = []
    for rx in prescriptions:
        rx["_id"] = ObjectId()
        rx["status"] = "Pending"
        processed_prescriptions.append(rx)

    # --- Process Lab Orders ---
    processed_investigation_orders = []
    for order in investigation_orders:
        order["_id"] = ObjectId()
        order["status"] = "Pending Sample"
        order["result"] = None
        order["verified_by"] = None
        order["verified_at"] = None
        processed_investigation_orders.append(order)

    consult_doc = {
        "triage_id": ObjectId(triage_id),
        "patient_id": ObjectId(patient_id),
        "doctor_id": ObjectId(doctor_id), # Keep user ID for audit trail
        "doctor_name": doctor_name,
        "consultation_at": datetime.utcnow(),
        "notes": notes,
        "prescriptions": processed_prescriptions,
        "investigation_orders": processed_investigation_orders
    }
    inserted_id = consultations.insert_one(consult_doc).inserted_id

    # --- UPDATED: Add Billing for Consultation Fee using doctor_name ---
    doctor = get_doctor_by_name(doctor_name) # Use name to find the doctor profile

    if not doctor:
        print(f"ERROR: Doctor profile not found for name '{doctor_name}' during consultation billing.") # Debug print
        fee = 0.0 # Default fee to 0 if doctor profile not found
    else:
        fee = doctor.get('consultation_fee', 0.0) # Default to 0 if no fee set

    if fee > 0:
        create_billing_entry(
            patient_id=patient_id,
            item_description=f"Consultation with {doctor_name}",
            quantity=1,
            unit_price=fee,
            total_amount=fee
        )
    # ---------------------------------------------

    return inserted_id

def get_consultations_for_patient(patient_id):
    """Gets all past consultations for a patient, newest first."""
    return list(get_consultation_collection().find(
        {"patient_id": ObjectId(patient_id)}
    ).sort("consultation_at", -1))

def get_consultation_history():
    """Gets all consultation records, joined with patient and triage info."""
    consultations = get_consultation_collection()
    pipeline = [
        {"$sort": {"consultation_at": -1}}, # Sort by newest first
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient"
            }
        },
        {
            "$lookup": {
                "from": "triage_log",
                "localField": "triage_id",
                "foreignField": "_id",
                "as": "triage"
            }
        },
        {"$unwind": "$patient"},
        {"$unwind": "$triage"} # A consult should always have a patient and triage entry
    ]
    return list(consultations.aggregate(pipeline))

def get_consultation_by_triage_id(triage_id):
    """
    Finds a consultation record based on its parent triage_id.
    """
    return get_consultation_collection().find_one({"triage_id": ObjectId(triage_id)})

def update_formulary_stock(formulary_id, quantity_change):
    """
    Updates the stock level for a formulary item.
    Use a positive number for GRN (adding stock).
    Use a negative number for dispensing (subtracting stock).
    """
    formulary = get_formulary_collection()
    result = formulary.update_one(
        {"_id": ObjectId(formulary_id)},
        {"$inc": {"stock_level": int(quantity_change)}}
    )
    return result.modified_count > 0

# --- Billing (Module 6) ---

def get_billing_collection():
    """Helper to get the 'billing' collection."""
    db = get_db()
    return db.billing

def create_billing_entry(patient_id, item_description, quantity, unit_price, total_amount):
    """Creates a new line item in the billing log."""
    billing = get_billing_collection()
    bill_doc = {
        "patient_id": patient_id,
        "item_description": item_description,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_amount": total_amount,
        "created_at": datetime.utcnow(),
        "status": "Unpaid"
    }
    return billing.insert_one(bill_doc).inserted_id

def get_billing_log():
    """Gets all billing entries, joined with patient data."""
    billing = get_billing_collection()
    pipeline = [
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient"
            }
        },
        {"$unwind": "$patient"}
    ]
    return list(billing.aggregate(pipeline))

# --- Pharmacy Information System (Module 6) ---

def get_pending_prescriptions():
    """
    Finds all prescription items that have not been dispensed.
    """
    consultations = get_consultation_collection()
    pipeline = [
        # Find all consultations that have at least one pending prescription
        {"$match": {"prescriptions.status": "Pending"}},
        {"$unwind": "$prescriptions"}, # Deconstruct the array
        # Filter to *only* the pending prescriptions
        {"$match": {"prescriptions.status": "Pending"}},
        # Join with patient data
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient"
            }
        },
        {"$unwind": "$patient"},
        {"$sort": {"consultation_at": 1}} # Oldest first
    ]
    return list(consultations.aggregate(pipeline))

def dispense_prescription(consultation_id, prescription_id, formulary_id, quantity, user_name):
    """
    Marks a prescription as dispensed, updates stock, and creates a bill.
    """
    # 1. Get Formulary Item to find its price
    formulary = get_formulary_collection()
    drug = formulary.find_one({"_id": ObjectId(formulary_id)})
    if not drug:
        raise ValueError("Formulary drug not found.")
        
    # 2. Update the Consultation
    consultations = get_consultation_collection()
    result = consultations.update_one(
        {
            "_id": ObjectId(consultation_id),
            "prescriptions._id": ObjectId(prescription_id)
        },
        {
            "$set": {
                "prescriptions.$.status": "Dispensed",
                "prescriptions.$.dispensed_by": user_name,
                "prescriptions.$.dispensed_at": datetime.utcnow()
            }
        }
    )
    if result.modified_count == 0:
        raise ValueError("Could not find or update the prescription.")
        
    # 3. Update Stock
    # We use -quantity because we are *removing* stock
    update_formulary_stock(formulary_id, -int(quantity))
    
    # 4. Create Billing Entry
    # Get patient ID from the consultation
    consult = consultations.find_one({"_id": ObjectId(consultation_id)})
    total_amount = drug['unit_price'] * int(quantity)
    item_desc = f"{drug['drug_name']} ({drug['brand_name']}) - {drug['dosage_form']}"
    
    create_billing_entry(
        patient_id=consult['patient_id'],
        item_description=item_desc,
        quantity=int(quantity),
        unit_price=drug['unit_price'],
        total_amount=total_amount
    )
    
    return True

def update_billing_status(billing_id, new_status):
    """Updates the status of a billing item (e.g., to 'Paid')."""
    billing = get_billing_collection()
    result = billing.update_one(
        {"_id": ObjectId(billing_id)},
        {"$set": {"status": new_status}}
    )
    return result.modified_count > 0

# --- Laboratory Information System (Module 8) ---

def get_lab_order_queue(status_list):
    """
    Finds all lab orders that match a given status or list of statuses.
    This will be used for both sample collection and the lab workbench.
    """
    consultations = get_consultation_collection()
    pipeline = [
        # Find all consultations that have at least one order with the matching status
        {"$match": {"investigation_orders.status": {"$in": status_list}}},
        {"$unwind": "$investigation_orders"}, # Deconstruct the array
        # Filter to *only* the matching orders
        {"$match": {"investigation_orders.status": {"$in": status_list}}},
        # Join with patient data
        {
            "$lookup": {
                "from": "patients",
                "localField": "patient_id",
                "foreignField": "_id",
                "as": "patient"
            }
        },
        {"$unwind": "$patient"},
        {"$sort": {"consultation_at": 1}} # Oldest first
    ]
    return list(consultations.aggregate(pipeline))

def update_lab_order_status(consultation_id, order_id, new_status, user_name):
    """
    Updates the status of a single lab order (e.g., "Sample Collected").
    """
    consultations = get_consultation_collection()
    
    update_doc = {
        "investigation_orders.$.status": new_status
    }
    
    if new_status == "Sample Collected":
        update_doc["investigation_orders.$.collected_by"] = user_name
        update_doc["investigation_orders.$.collected_at"] = datetime.utcnow()

    result = consultations.update_one(
        {
            "_id": ObjectId(consultation_id),
            "investigation_orders._id": ObjectId(order_id)
        },
        {"$set": update_doc}
    )
    return result.modified_count > 0

def submit_lab_result(consultation_id, order_id, result_text, user_name):
    """
    Submits the final result for a lab test, marks it as verified,
    and generates a bill.
    """
    # 1. Get the consultation and the specific order to find the test name
    consultations = get_consultation_collection()
    consult = consultations.find_one(
        {"_id": ObjectId(consultation_id)},
        {"investigation_orders": {"$elemMatch": {"_id": ObjectId(order_id)}}, "patient_id": 1}
    )
    if not consult or 'investigation_orders' not in consult or not consult['investigation_orders']:
        raise ValueError("Lab order not found.")
    
    order = consult['investigation_orders'][0]
    test_name = order['name']

    # 2. Get the lab test price from the 'lab_tests' collection
    lab_test = get_lab_test_collection().find_one({"test_name": test_name.lower()})
    if not lab_test:
        raise ValueError(f"Test '{test_name}' not found in lab test list.")
        
    unit_price = lab_test.get('unit_price', 0.0) # Default to 0 if no price

    # 3. Update the consultation record with the result
    result = consultations.update_one(
        {
            "_id": ObjectId(consultation_id),
            "investigation_orders._id": ObjectId(order_id)
        },
        {
            "$set": {
                "investigation_orders.$.status": "Result Verified",
                "investigation_orders.$.result": result_text,
                "investigation_orders.$.verified_by": user_name,
                "investigation_orders.$.verified_at": datetime.utcnow()
            }
        }
    )
    if result.modified_count == 0:
        raise ValueError("Could not find or update the lab order.")

    # 4. Create Billing Entry
    create_billing_entry(
        patient_id=consult['patient_id'],
        item_description=f"Lab Test: {test_name.title()}",
        quantity=1,
        unit_price=unit_price,
        total_amount=unit_price
    )
    
    return True

from datetime import datetime, time

# --- Dashboard Stats ---

def get_total_patient_count():
    """Counts the total number of registered patients."""
    return get_patient_collection().count_documents({})

def get_appointments_today_count():
    """Counts appointments scheduled for today."""
    appointments = get_appointment_collection()
    
    # Get today's date range (start and end)
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)
    
    # Count appointments within today's range
    return appointments.count_documents({
        "appointment_time": {
            "$gte": start_of_day,
            "$lt": end_of_day
        }
    })

def get_available_beds_count():
    """
    Placeholder for available bed count.
    Module 11 (Bed Management) needs to be implemented for this.
    Returns a simulated tuple: (available, total)
    """
    # Replace with real logic once Bed Management is built
    return (45, 350) 

def get_pending_er_cases_count():
    """
    Placeholder for pending ER cases.
    Module 11 (Emergency Case Management) needs to be implemented.
    Returns 0 for now.
    """
    # Replace with real logic once ER module is built
    return 0

def get_unpaid_bills_for_patient(patient_id):
    """Gets all unpaid billing items for a specific patient."""
    billing = get_billing_collection()
    return list(billing.find({
        "patient_id": ObjectId(patient_id),
        "status": "Unpaid"
    }).sort("created_at", 1)) # Oldest first

def mark_patient_bills_paid(patient_id):
    """Marks all unpaid bills for a patient as 'Paid'."""
    billing = get_billing_collection()
    result = billing.update_many(
        {
            "patient_id": ObjectId(patient_id),
            "status": "Unpaid"
        },
        {"$set": {"status": "Paid"}}
    )
    return result.modified_count

def get_doctor_by_name(doctor_name):
    """Finds a single doctor by their name (case-insensitive search)."""
    doctors = get_doctor_collection()
    # Use regex for case-insensitive search
    return doctors.find_one({"name": {"$regex": f"^{doctor_name}$", "$options": "i"}})

def assign_doctor_to_triage(triage_id, doctor_id, doctor_name):
    """Assigns a doctor to a triage entry and updates status."""
    triage_log = get_triage_collection()
    result = triage_log.update_one(
        {"_id": ObjectId(triage_id)},
        {
            "$set": {
                "assigned_doctor_id": ObjectId(doctor_id),
                "assigned_doctor_name": doctor_name,
                "status": "Assigned" # Change status from 'Waiting'
            }
        }
    )
    return result.modified_count > 0

def find_patient_by_phone(phone_number):
    """Finds a patient by their contact number."""
    patients = get_patient_collection()
    return patients.find_one({"patient_contact": phone_number})

# --- Booking / Viewing Functions ---

def find_available_slots(department=None, doctor_id=None, start_date=None):
    """
    Finds available appointment slots.
    !! HACKATHON SIMULATION !! Replace with real scheduling logic.
    For now, returns a few fake slots for tomorrow.
    """
    print(f"Simulating slot search for Dept: {department}, DocID: {doctor_id}, Start: {start_date}")
    # In reality, query a calendar/schedule database based on doctor availability, duration etc.
    tomorrow = datetime.utcnow().date() + timedelta(days=1)
    slots = [
        datetime.combine(tomorrow, time(9, 0)),
        datetime.combine(tomorrow, time(10, 30)),
        datetime.combine(tomorrow, time(14, 0)),
    ]
    # Return slots formatted nicely
    return [{"time": slot.isoformat(), "display": slot.strftime('%Y-%m-%d %I:%M %p')} for slot in slots]

def get_appointments_for_patient(patient_id):
    """Gets upcoming and past appointments for a patient."""
    appointments = get_appointment_collection()
    now = datetime.utcnow()
    upcoming = list(appointments.find({
        "patient_id": ObjectId(patient_id),
        "appointment_time": {"$gte": now}
    }).sort("appointment_time", 1))
    past = list(appointments.find({
        "patient_id": ObjectId(patient_id),
        "appointment_time": {"$lt": now}
    }).sort("appointment_time", -1).limit(5)) # Limit past for brevity
    return upcoming, past

def get_results_for_patient(patient_id):
    """Gets verified lab results for a patient."""
    consultations = get_consultation_collection()
    results = []
    pipeline = [
        {"$match": {"patient_id": ObjectId(patient_id), "investigation_orders.status": "Result Verified"}},
        {"$unwind": "$investigation_orders"},
        {"$match": {"investigation_orders.status": "Result Verified"}},
        {"$sort": {"investigation_orders.verified_at": -1}},
         # Project only necessary fields
        {"$project": {
            "_id": 0, # Exclude consultation ID
            "test_name": "$investigation_orders.name",
            "result": "$investigation_orders.result",
            "verified_at": "$investigation_orders.verified_at"
        }}
    ]
    verified_orders = list(consultations.aggregate(pipeline))
    return verified_orders


def get_bill_summary_for_patient(patient_id):
    """Gets unpaid bills and total amount for a patient."""
    unpaid_items = get_unpaid_bills_for_patient(patient_id) # Already exists
    total_due = sum(item['total_amount'] for item in unpaid_items)
    return unpaid_items, total_due

def get_first_doctor_in_dept(department_name=None):
    """Finds the first doctor, optionally filtering by department."""
    doctors = get_doctor_collection()
    query = {}
    if department_name:
        # Case-insensitive search for department
        query = {"department": {"$regex": f"^{department_name}$", "$options": "i"}}
    
    doctor = doctors.find_one(query)
    if not doctor and department_name: # Fallback if dept search fails
        doctor = doctors.find_one() # Get any doctor
        
    return doctor

# --- Emergency Case Management (Module 11) ---

def get_er_case_collection():
    """Helper to get the 'er_cases' collection."""
    db = get_db()
    return db.er_cases

def create_er_case(patient_id, pre_hospital_info, symptoms, vitals_data, ai_triage_result, registered_by_id, registered_by_name):
    """Creates a new emergency case."""
    er_cases = get_er_case_collection()

    patient = get_patient_by_id(patient_id)
    if not patient:
        raise ValueError("Patient not found.")

    er_doc = {
        "patient_id": patient_id, # ObjectId
        "pid": patient['pid'], # Human-readable ID
        "patient_name": patient['patient_name'], # Denormalized for display
        "registered_at": datetime.utcnow(),
        "registered_by_id": registered_by_id, # ObjectId of user who registered
        "registered_by_name": registered_by_name, # Name of user
        "pre_hospital_info": pre_hospital_info,
        "presenting_symptoms": symptoms,
        "initial_vitals": vitals_data, # Dict: {bp_systolic:.., bp_diastolic:.., ...}
        "triage_score": ai_triage_result['score'], # e.g., 1-5
        "triage_level": ai_triage_result['level'], # e.g., "Level 1: Resuscitation"
        "status": "Waiting", # Options: Waiting, Assigned Doctor, In-Treatment, Observation, Awaiting Disposition, Discharged, Admitted, Transferred
        "current_location": "ER Waiting Area", # e.g., ER Waiting Area, ER Bed 1, Observation Ward, CT Scan
        "assigned_doctor_id": None, # ObjectId of doctor (can link to users or doctors collection)
        "assigned_doctor_name": None, # Denormalized name
        "treatment_orders": [], # List of { _id, order_text, ordered_by, ordered_at, status }
        "case_notes": [], # List of { _id, note_text, noted_by, noted_at }
        "disposition": None, # Dict: { decision, notes, decided_by, decided_at }
        "closed_at": None # Timestamp when case status becomes Discharged, Admitted, Transferred
    }
    result = er_cases.insert_one(er_doc)
    return result.inserted_id

def get_er_queue():
    """Gets active ER cases (not Discharged/Admitted/Transferred), prioritized."""
    er_cases = get_er_case_collection()
    active_statuses = ["Waiting", "Assigned Doctor", "In-Treatment", "Observation", "Awaiting Disposition"]
    return list(er_cases.find(
        {"status": {"$in": active_statuses}}
    ).sort([
        ("triage_score", 1), # 1 is highest priority
        ("registered_at", 1) # Oldest first within same priority
    ]))

def get_er_case_by_id(case_id):
    """Gets a single ER case by its MongoDB ObjectId."""
    try:
        return get_er_case_collection().find_one({"_id": ObjectId(case_id)})
    except Exception as e:
        print(f"Error fetching ER case by ID {case_id}: {e}")
        return None

def update_er_case_details(case_id, status=None, location=None, assigned_doctor_id=None, assigned_doctor_name=None):
    """Updates status, location, or assigned doctor for an ER case."""
    er_cases = get_er_case_collection()
    update_doc = {}
    if status:
        update_doc["status"] = status
    if location:
        update_doc["current_location"] = location
    if assigned_doctor_id and assigned_doctor_name:
        update_doc["assigned_doctor_id"] = ObjectId(assigned_doctor_id)
        update_doc["assigned_doctor_name"] = assigned_doctor_name
        current_case = get_er_case_by_id(case_id)
        if current_case and current_case.get('status') == 'Waiting':
             update_doc["status"] = "Assigned Doctor" # Auto-update status

    if not update_doc: return False

    try:
        result = er_cases.update_one({"_id": ObjectId(case_id)}, {"$set": update_doc})
        print(f"Update ER Case {case_id}: Matched={result.matched_count}, Modified={result.modified_count}")
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating ER case {case_id}: {e}")
        return False

def add_er_note_or_order(case_id, text, note_type, user_name):
    """Adds a clinical note or a treatment order to an ER case."""
    er_cases = get_er_case_collection()
    timestamp = datetime.utcnow(); item_id = ObjectId()
    push_field = None; item_doc = None

    if note_type == 'note':
        push_field = 'case_notes'
        item_doc = { "_id": item_id, "note_text": text, "noted_by": user_name, "noted_at": timestamp }
    elif note_type == 'order':
        push_field = 'treatment_orders'
        item_doc = { "_id": item_id, "order_text": text, "ordered_by": user_name, "ordered_at": timestamp, "status": "Ordered" }
    else: raise ValueError("Invalid note_type.")

    try:
        result = er_cases.update_one({"_id": ObjectId(case_id)}, {"$push": {push_field: item_doc}})
        print(f"Add {note_type} to ER Case {case_id}: Matched={result.matched_count}, Modified={result.modified_count}")
        return result.modified_count > 0
    except Exception as e:
        print(f"Error adding {note_type} to ER case {case_id}: {e}")
        return False

def set_er_disposition(case_id, decision, notes, user_name):
    """Sets the final disposition for an ER case and updates status/closed_at."""
    er_cases = get_er_case_collection()
    disposition_doc = { "decision": decision, "notes": notes, "decided_by": user_name, "decided_at": datetime.utcnow() }
    final_statuses = ["Admitted", "Discharged", "Transferred"]
    final_status = decision if decision in final_statuses else "Awaiting Disposition"
    closed_time = datetime.utcnow() if final_status in final_statuses else None

    try:
        result = er_cases.update_one( {"_id": ObjectId(case_id)}, {"$set": {"disposition": disposition_doc, "status": final_status, "closed_at": closed_time }})
        print(f"Set Disposition for ER Case {case_id}: Matched={result.matched_count}, Modified={result.modified_count}")
        return result.modified_count > 0
    except Exception as e:
        print(f"Error setting disposition for ER case {case_id}: {e}")
        return False


# --- Add Imports needed by new functions ---
# Make sure these are at the top of models.py

# ------------------------------------------

def get_insurance_summary_data(patient_id):
    """
    Aggregates data relevant for an insurance summary for a specific patient.
    """
    patient_object_id = ObjectId(patient_id)
    summary_data = {
        "patient": None,
        "consultations": [],
        "dispensed_meds": [],
        "completed_labs": [],
        "paid_bills": []
    }

    # 1. Get Patient Details
    summary_data["patient"] = get_patient_by_id(patient_object_id)
    if not summary_data["patient"]:
        raise ValueError("Patient not found for summary.")

    # 2. Get Consultations (including prescriptions and labs within them)
    consultations = list(get_consultation_collection().find(
        {"patient_id": patient_object_id}
    ).sort("consultation_at", -1)) # Newest first

    summary_data["consultations"] = consultations # Store full consult for context if needed

    # 3. Extract Dispensed Meds and Completed Labs from Consultations
    for consult in consultations:
        if consult.get("prescriptions"):
            for rx in consult["prescriptions"]:
                if rx.get("status") == "Dispensed":
                    summary_data["dispensed_meds"].append({
                        "date": consult.get("consultation_at"), # Use consultation date for prescribing date
                        "drug_name": rx.get("name"),
                        "dosage": rx.get("dosage"),
                        "dispensed_at": rx.get("dispensed_at"), # Get actual dispense date
                        "doctor": consult.get("doctor_name")
                    })
        if consult.get("investigation_orders"):
            for lab in consult["investigation_orders"]:
                if lab.get("status") == "Result Verified":
                    summary_data["completed_labs"].append({
                        "date": consult.get("consultation_at"), # Use consultation date for order date
                        "test_name": lab.get("name"),
                        "result": lab.get("result", "N/A"),
                        "verified_at": lab.get("verified_at"), # Get actual result date
                        "doctor": consult.get("doctor_name")
                    })

    # Sort extracted items by date (newest first for display)
    summary_data["dispensed_meds"].sort(key=lambda x: x.get('dispensed_at') or x.get('date'), reverse=True)
    summary_data["completed_labs"].sort(key=lambda x: x.get('verified_at') or x.get('date'), reverse=True)


    # 4. Get Paid Billing Items
    summary_data["paid_bills"] = list(get_billing_collection().find({
        "patient_id": patient_object_id,
        "status": "Paid" # Only fetch paid items
    }).sort("created_at", -1)) # Newest first

    return summary_data