# ========================================
# SRM AI Patient Assistant Blueprint
# Handles patient chat, blockchain logging, and AI interaction.
# ========================================

import os
import re
from datetime import datetime, timedelta, time
from bson import ObjectId
from flask import (
    render_template, request, jsonify, session, redirect, url_for, flash, Response
)
from io import BytesIO # To handle PDF data in memory
from xhtml2pdf import pisa # The core conversion function
from web3 import Web3

# --- Blueprint Import ---
from . import patient_bp

# --- AI Analysis ---
from app.ai_stubs import analyze_patient_interaction

# --- Database Models ---
from app.models import (
    find_patient_by_phone, get_or_create_patient, create_complaint,
    get_patient_by_id, create_triage_entry, get_triage_collection,
    find_available_slots, create_appointment, get_appointments_for_patient,
    get_results_for_patient, get_bill_summary_for_patient,
    get_doctor_by_id, get_first_doctor_in_dept,
    get_insurance_summary_data
)

# ========================================
# Blockchain Setup (Ganache)
# ========================================

GANACHE_URL = "http://127.0.0.1:7545"
CONTRACT_ADDRESS = "0xD43D862B1Ebc24039b1bAb8E79036177f89e984e"
CONTRACT_ABI = """
[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"uint256","name":"logId","type":"uint256"},{"indexed":true,"internalType":"string","name":"caseId","type":"string"},{"indexed":false,"internalType":"string","name":"eventDetails","type":"string"},{"indexed":false,"internalType":"uint256","name":"timestamp","type":"uint256"},{"indexed":false,"internalType":"address","name":"loggedBy","type":"address"}],"name":"LogAdded","type":"event"},{"inputs":[{"internalType":"string","name":"_caseId","type":"string"},{"internalType":"string","name":"_eventDetails","type":"string"}],"name":"addLog","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"allLogs","outputs":[{"internalType":"uint256","name":"logId","type":"uint256"},{"internalType":"string","name":"caseId","type":"string"},{"internalType":"string","name":"eventDetails","type":"string"},{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"loggedBy","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"_index","type":"uint256"}],"name":"getLog","outputs":[{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getLogCount","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
"""

# Initialize blockchain connection
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))
if not web3.is_connected():
    raise ConnectionError("Failed to connect to Ganache blockchain node.")

web3.eth.default_account = web3.eth.accounts[0]
contract = web3.eth.contract(
    address=web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=CONTRACT_ABI
)

# ========================================
# In-memory store for chat sessions
# ========================================
chat_histories = {}


# ========================================
# Blockchain Endpoints
# ========================================

@patient_bp.route('/add_log', methods=['POST'])
def add_log_entry():
    """Add a new log entry to the blockchain."""
    try:
        data = request.json
        case_id = data.get('caseId')
        details = data.get('details')

        if not case_id or not details:
            return jsonify({"status": "error", "message": "Missing caseId or details"}), 400

        tx_hash = contract.functions.addLog(case_id, details).transact()
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        return jsonify({
            "status": "success",
            "message": "Log entry added to blockchain.",
            "transaction_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@patient_bp.route('/get_logs/<string:case_id>', methods=['GET'])
def get_log_entries(case_id):
    """Retrieve all blockchain logs for a given case ID."""
    try:
        all_logs = []
        log_count = contract.functions.getLogCount().call()

        for i in range(log_count):
            log_data = contract.functions.getLog(i).call()
            if log_data[1] == case_id:
                all_logs.append({
                    "logId": log_data[0],
                    "caseId": log_data[1],
                    "eventDetails": log_data[2],
                    "timestamp": log_data[3],
                    "loggedBy": log_data[4],
                })

        return jsonify({
            "status": "success",
            "caseId": case_id,
            "logs": all_logs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@patient_bp.route('/get_all_logs', methods=['GET'])
def get_all_log_entries():
    """Retrieve all blockchain logs (no filter)."""
    try:
        all_logs = []
        log_count = contract.functions.getLogCount().call()

        for i in range(log_count):
            log_data = contract.functions.getLog(i).call()
            all_logs.append({
                "logId": log_data[0],
                "caseId": log_data[1],
                "eventDetails": log_data[2],
                "timestamp": log_data[3],
                "loggedBy": log_data[4],
            })

        return jsonify({
            "status": "success",
            "log_count": len(all_logs),
            "logs": all_logs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# ========================================
# Chat + AI Assistant Endpoints
# ========================================

@patient_bp.route('/', methods=['GET'])
def assistant_home():
    """Render the main chat interface for the patient assistant."""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = os.urandom(16).hex()
        chat_histories[session['chat_session_id']] = []

    # Clear all previous pending states
    for key in [
        'patient_mongo_id', 'patient_identified_name', 'pending_registration',
        'pending_er_reg', 'available_slots', 'booking_intent_details'
    ]:
        session.pop(key, None)

    chat_session_id = session['chat_session_id']
    history = chat_histories.get(chat_session_id, [])

    return render_template(
        'patient_assistant.html',
        title="SRM AI Patient Assistant",
        history=history
    )


@patient_bp.route('/chat', methods=['POST'])
def handle_chat():
    """Handle incoming user chat messages and AI processing (clean, loop-free version)."""
    data = request.get_json()
    user_message = data.get('message')
    chat_session_id = session.get('chat_session_id')

    if not user_message or not chat_session_id:
        return jsonify({"error": "Missing message or session ID"}), 400

    # Keep short chat history for context (optional)
    current_history = chat_histories.setdefault(chat_session_id, [])
    current_history.append({"sender": "user", "text": user_message})

    # Identify if patient already verified
    patient_mongo_id = session.get('patient_mongo_id')
    patient_identified_name = session.get('patient_identified_name')
    patient_identified = bool(patient_mongo_id)

    # --- Call AI analysis (now simplified, no history param) ---
    ai_analysis = analyze_patient_interaction(
        user_message,
        patient_identified=patient_identified
    )

    intent = ai_analysis.get("intent", "unknown")
    ai_response_text = ai_analysis.get("ai_response_text", "Sorry, I couldn't process that.")
    action_details = ai_analysis.get("action_details", {})
    triage_result = ai_analysis.get("triage_result", {})

    final_ai_text = ai_response_text
    action_performed = None

    # --------------------------
    # 1️⃣ Identification Handling
    # --------------------------
    print("INTENT :", intent, "ai_response_text : ", ai_response_text, "action_details", action_details, "triage_result", triage_result)
    if intent == "request_identification" or intent == "provide_identification":
        name = action_details.get("patient_name")
        phone = action_details.get("phone_number")

        print("Name : ", name)
        print("Phone : ", phone)

        if name and phone:
            patient = find_patient_by_phone(phone)
            print("Patient : ", patient)
            if patient:
                session['patient_mongo_id'] = str(patient['_id'])
                session['patient_identified_name'] = patient['patient_name']
                final_ai_text = f"Thank you, {patient['patient_name']}. You are verified! How can I assist you?"
                action_performed = "identification_success"
            else:
                final_ai_text = (
                    f"Thank you, {name}. I couldn’t find a record for {phone}. "
                    "Would you like to register as a new patient?"
                )
                session['pending_registration'] = {'name': name, 'phone': phone}
                action_performed = "request_registration"
        else:
            final_ai_text = "Please provide both your full name and phone number."
            action_performed = "incomplete_identification"

    # --------------------------
    # 2️⃣ Registration Confirmation
    # --------------------------
    elif intent == "confirmation_yes" and session.get('pending_registration'):
        reg_info = session.pop('pending_registration')
        try:
            new_patient = get_or_create_patient(reg_info['name'], reg_info['phone'])
            session['patient_mongo_id'] = str(new_patient['_id'])
            session['patient_identified_name'] = new_patient['patient_name']
            final_ai_text = (
                f"Welcome, {new_patient['patient_name']}! "
                f"You are now registered (Patient ID: {new_patient['pid']})."
            )
            action_performed = "registration_success"
        except Exception as e:
            final_ai_text = f"Sorry, there was an error registering you: {e}."
            action_performed = "registration_fail"

    # --------------------------
    # 3️⃣ ER Triage Confirmation
    # --------------------------
    elif intent == "check_symptoms_emergency":
        patient_id_str = session.get('patient_mongo_id')
        patient_object_id = ObjectId(patient_id_str) if patient_id_str else None

        if patient_object_id:
            try:
                triage_id = create_triage_entry(
                    patient_id=patient_object_id,
                    nurse_id=ObjectId("000000000000000000000000"),
                    nurse_name="AI Assistant",
                    symptoms=triage_result.get('symptoms', 'Not specified'),
                    history="Registered via AI Chatbot",
                    vitals_data={"bp_systolic": 0, "bp_diastolic": 0, "heart_rate": 0, "temperature": 0.0},
                    ai_result={"score": 2, "level": "Emergency"}
                )
                final_ai_text = (
                    f"Okay, {session.get('patient_identified_name', 'Patient')}, "
                    f"I’ve added you to the triage queue (Ref: ...{str(triage_id)[-6:]}). "
                    f"Please proceed to the ER."
                )
                action_performed = "er_triage_success"
            except Exception as e:
                final_ai_text = f"Sorry, I couldn’t complete ER registration: {e}"
                action_performed = "er_triage_fail"
        else:
            final_ai_text = "You need to be identified first before ER triage."
            action_performed = "er_triage_fail"

    # --------------------------
    # 4️⃣ General, Greetings, View Info
    # --------------------------
    elif intent in ["greeting", "general_chat", "view_bill", "view_results", "view_appointments"]:
        final_ai_text = ai_response_text
        action_performed = "general_response"

        # Handle view requests if identified
        if patient_identified:
            if intent == "view_bill":
                final_ai_text = "Fetching your billing details..."
                action_performed = "fetch_bill"
            elif intent == "view_results":
                final_ai_text = "Fetching your medical results..."
                action_performed = "fetch_results"
            elif intent == "view_appointments":
                final_ai_text = "Fetching your upcoming appointments..."
                action_performed = "fetch_appointments"

    # --------------------------
    # 5️⃣ Fallback / Exit Intents
    # --------------------------
    elif intent in ["goodbye", "confirmation_no", "unknown"]:
        session.pop('pending_registration', None)
        session.pop('pending_er_reg', None)
        final_ai_text = ai_response_text
        action_performed = "end_or_clear"

    # --------------------------
    # 🧾 Final Response Assembly
    # --------------------------
    response_data = {
        "sender": "ai",
        "text": final_ai_text,
        "triage_result": triage_result,
        "action_performed": action_performed
    }

    current_history.append(response_data)
    chat_histories[chat_session_id] = current_history[-20:]  # keep short

    return jsonify(response_data)



# ========================================
# AI Features Page
# ========================================
@patient_bp.route('/ai-features', methods=['GET'])
def ai_features_list():
    """List available AI-powered features for patients."""
    return render_template('patient_ai_features.html', title="AI Health Tools")


# In app/patient_portal/routes.py

# In app/patient_portal/routes.py

@patient_bp.route('/insurance-summary', methods=['GET', 'POST'])
def insurance_summary_page():
    """
    Renders the insurance summary page for the identified patient.
    If not identified, prompts for phone number via a form on the page.
    Handles POST requests to identify the patient via phone number.
    """
    patient_mongo_id = session.get('patient_mongo_id')
    patient_name = session.get('patient_identified_name')
    summary_data = None
    identified = False
    error_message = None # To show phone lookup errors

    # --- Handle POST request (Phone number submission) ---
    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        if not phone_number:
            error_message = "Please enter your phone number."
        else:
            try:
                # Attempt to find the patient by phone number
                patient = find_patient_by_phone(phone_number)
                if patient:
                    # Patient found! Store details in session and set flag
                    session['patient_mongo_id'] = str(patient['_id'])
                    session['patient_identified_name'] = patient['patient_name']
                    patient_mongo_id = str(patient['_id']) # Update local variable for immediate use
                    patient_name = patient['patient_name']
                    identified = True
                    flash(f"Welcome, {patient_name}! Your summary is displayed below.", "success")
                    # No redirect needed, will proceed to fetch data below
                else:
                    # Patient not found
                    error_message = "No patient record found for that phone number. Please try again or register via the AI Assistant."
                    identified = False # Ensure flag is false
            except Exception as e:
                print(f"Error during phone lookup: {e}")
                error_message = "An error occurred while looking up your record. Please try again later."
                identified = False

    # --- Handle GET request OR successful POST identification ---
    # Check identification status again (might have been set by POST)
    if not identified and session.get('patient_mongo_id'):
         identified = True
         patient_mongo_id = session['patient_mongo_id']
         patient_name = session['patient_identified_name']


    if identified:
        try:
            # Fetch summary data only if identified
            summary_data = get_insurance_summary_data(patient_mongo_id)
        except Exception as e:
            print(f"Error fetching insurance summary for {patient_mongo_id}: {e}")
            flash("Could not retrieve your activity summary at this time.", "danger")
            # If data fetch fails AFTER identification, show error but stay identified
            summary_data = None # Prevent displaying partial/old data

    # Render the template, passing identification status and data (or None)
    return render_template('patient_insurance_summary.html',
                           title="Insurance Activity Summary",
                           identified=identified,
                           patient_name=patient_name,
                           summary=summary_data,
                           error_message=error_message) # Pass error message for form display


@patient_bp.route('/download-insurance-summary', methods=['GET'])
def download_insurance_summary_pdf():
    """Generates and downloads the insurance summary as a PDF using xhtml2pdf."""
    patient_mongo_id = session.get('patient_mongo_id')
    if not patient_mongo_id:
        return "Access Denied: Not Identified", 403

    try:
        summary_data = get_insurance_summary_data(patient_mongo_id)

        # Render the HTML template specifically for the PDF
        # Ensure 'datetime' is available if used in the PDF template (it should be via context_processor)
        html_for_pdf = render_template('insurance_summary_pdf.html',
                                       summary=summary_data)

        # Create a PDF file in memory
        pdf_buffer = BytesIO()

        # Convert HTML to PDF using pisa
        # result = pisa.CreatePDF(html_for_pdf, dest=pdf_buffer) # Old syntax
        pisa_status = pisa.CreatePDF(BytesIO(html_for_pdf.encode('UTF-8')), dest=pdf_buffer) # Updated syntax expects bytes

        # Check if PDF creation was successful
        if pisa_status.err:
            print(f"Error generating PDF with pisa: {pisa_status.err}")
            raise ValueError(f"Could not generate PDF: {pisa_status.err}")

        # Get PDF content from the buffer
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        # Create filename
        patient_name_safe = "".join(c if c.isalnum() else "_" for c in summary_data['patient']['patient_name'])
        filename = f"SRM_Insurance_Summary_{summary_data['patient']['pid']}_{patient_name_safe}.pdf"

        # Return the PDF as a downloadable file
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment;filename={filename}',
                'Content-Length': len(pdf_bytes) # Add content length header
            }
        )

    except Exception as e:
        print(f"Error generating insurance PDF: {e}")
        flash(f"Could not generate the PDF summary at this time. Error: {e}", "danger")
        # Redirect back to the HTML summary page or home
        return redirect(url_for('patient_portal.insurance_summary_page'))