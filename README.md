# Hospital Management System (HMS) with AI Patient Assistant

This project is a modular Hospital Management System built with Python (Flask) and MongoDB, featuring role-based access control for staff and an AI-powered Patient Assistant for symptom checking, triage estimation, and accessing hospital information.

---

## ✨ Features

### Staff Portal (Role-Based Access)
* **Modular Design:** Organized into core hospital functions.
* **Role-Based Access Control (RBAC):**
    * **Super Admin:** Manages Module Admins.
    * **Module Admins:** Manage users and functions within their assigned module (Clinical, Emergency/Legal, etc.).
    * **Sub-Users:** Operate within a specific module with permissions granted by Module Admins.
* **Implemented Clinical Modules:**
    * **Patient Registration:** Creates unique Patient IDs (PID) and links appointments.
    * **Appointment Scheduling & Queue:** Basic scheduling and digital queue management.
    * **Doctor Management:** CRUD operations for managing doctors and their consultation fees (in ₹).
    * **Vitals Logging:** Record patient vitals (BP, HR, Temp) with basic AI anomaly detection/alerts.
    * **Triage Management:** AI-powered triage scoring (ESI-like) based on symptoms and vitals, prioritized queue with doctor assignment.
    * **Consultation & E-Prescription:** SOAP notes, adding prescriptions (from formulary), ordering lab tests. Includes AI drug interaction checks. View mode for completed consultations.
    * **Formulary Management:** Manage available medications, stock levels, and pricing (in ₹).
    * **Lab Test Management:** Manage available lab tests and pricing (in ₹).
    * **Pharmacy Information System (PIS):** View pending prescriptions, dispense medication (updating stock and billing).
    * **Stock Management (GRN):** Add received stock to the formulary.
    * **Laboratory Information System (LIS):** Manage lab order workflow (Sample Collection Queue, Lab Workbench for results entry), automatic billing on verification.
    * **Billing Management:** Centralized log of charges (Consultations, Pharmacy, Labs), patient-specific billing view, ability to mark bills as paid.
* **Implemented Emergency & Legal Modules (Integrated into Main Blueprint):**
    * **ER Case Management:** Register ER cases, view prioritized ER queue based on AI triage, manage case details (status, location, doctor assignment), add notes/orders, set disposition. Accessible via `/er-dashboard` and `/er-case/<id>`.
    * **MLC Blockchain Logging (API & Staff UI):**
        * Add medico-legal case logs to a blockchain (requires connection setup). Accessed via `/mlc-add-log`.
        * View logs per Case ID. Accessed via `/mlc-view-log`.
        * View all logs (Admin). Accessed via `/mlc-view-all-logs`.

### Patient Portal (AI Assistant - No Login Required Initially)
* **AI Chat Interface:** Conversational interface using Gemini, full-screen, dark theme.
* **Multilingual Voice Interaction:** Full-screen voice mode using Web Speech API (Speech-to-Text & Text-to-Speech) with language selection (EN, TA, HI) and voice matching.
* **AI Symptom Checker & Triage:** Analyzes symptoms, provides urgency estimation and next steps (including emergency detection).
* **ER Pre-registration:** For emergency cases, allows identified patients (via name/phone) to send details ahead to the clinical Triage queue (`create_triage_entry`).
* **Patient Identification:** Uses Name + Phone Number lookup/registration via chat.
* **Information Access (for Identified Patients):**
    * View upcoming/past appointments.
    * View verified lab results.
    * View unpaid bill summary (in ₹).
* **General Hospital Q&A:** Answers basic questions about the hospital.
* **Insurance Summary:**
    * Dedicated page (`/patient/insurance-summary`) consolidating activities.
    * PDF download option (using xhtml2pdf).
    * On-page phone number identification prompt if accessed directly without prior chat identification.
* **AI Features Listing Page:** Professional page (`/patient/ai-features`) describing available and future AI tools.

---

## 🛠️ Technologies Used

* **Backend:** Python 3.x, Flask
* **Database:** MongoDB, PyMongo
* **Frontend:** HTML, Tailwind CSS (via CDN), JavaScript
* **AI:** Google Gemini API (`google-generativeai` library)
* **PDF Generation:** xhtml2pdf
* **Voice Interaction:** Web Speech API (Browser built-in)
* **Blockchain Interaction (Optional):** Web3.py
* **Authentication:** Flask-Login, Flask-Bcrypt
* **Environment:** Python Virtual Environment (`venv`)
* **Configuration:** `python-dotenv`

---

## 🏗️ Architecture

* **App Factory Pattern:** `create_app()` in `app/__init__.py`.
* **Blueprints:**
    * `main`: Core staff portal routes, authentication, ER/Legal pages.
    * `patient_portal`: Patient-facing AI assistant, Insurance Summary, AI features page, Blockchain APIs.
* **MVC-like Structure:** Routes, models, templates separation.
* **Database:** MongoDB collections (`users`, `patients`, `doctors`, `appointments`, `complaints` (unused), `formulary`, `lab_tests`, `consultations`, `triage_log`, `billing`, `er_cases`, `counters`).
* **Role-Based Access:** `@role_required` decorator and `current_user.module` checks.
* **AI Integration:** `app/ai_stubs.py` handles Gemini calls with fallbacks.
* **Session Management:** Flask sessions for staff login and patient chat identification/context. In-memory chat history.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.8+, `pip`.
* MongoDB running locally (`mongodb://localhost:27017/`).
* Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/app/apikey)).
* **(Optional: Blockchain)** Ganache running, deployed MedLog contract, ABI, address.
* **(Optional: PDF)** Check `xhtml2pdf` dependencies if needed.
* **(Optional: Voice)** Modern browser (Chrome/Edge), microphone access.

### Installation
1.  `git clone <url>`
2.  `cd <repo>`
3.  `python -m venv venv`
4.  Activate venv (`venv\Scripts\activate` or `source venv/bin/activate`)
5.  `pip install -r requirements.txt`

### Configuration
1.  Create `.env` file in root.
2.  Add variables:
    ```dotenv
    SECRET_KEY='a-very-strong-random-secret-key-for-flask-sessions'
    MONGO_URI='mongodb://localhost:27017/hms_db'
    GEMINI_API_KEY='YOUR_GOOGLE_GEMINI_API_KEY'

    # --- Optional: Blockchain Config ---
    # GANACHE_URL='[http://127.0.0.1:7545](http://127.0.0.1:7545)'
    # CONTRACT_ADDRESS='YOUR_DEPLOYED_CONTRACT_ADDRESS'
    # CONTRACT_ABI='PASTE_YOUR_ABI_JSON_AS_A_SINGLE_LINE_STRING'
    ```
    * Adjust blockchain setup in `app/patient_portal/routes.py` if needed.

### Initial Setup (Super Admin)
1.  `flask create-super-admin`
2.  Follow prompts for username/password.

---

## ▶️ Running the Application

1.  Activate venv.
2.  Ensure MongoDB is running.
3.  `flask run`
4.  Access:
    * **Staff Portal:** `http://127.0.0.1:5000/`
    * **AI Patient Assistant:** `http://127.0.0.1:5000/patient/`

---
# Hospital Management System (HMS) with AI Patient Assistant

---

## 📁 Project Structure

```text
/hospital-management-system/
|
|-- /app/                     # Main application package
|   |-- /er_legal/            # (Empty - Blueprint definition only now)
|   |   |-- __init__.py       # Defines er_bp blueprint
|   |
|   |-- /patient_portal/      # Patient-facing blueprint
|   |   |-- /templates/       # Patient HTML (assistant, summary, ai_features)
|   |   |-- __init__.py       # Defines patient_bp blueprint
|   |   |-- routes.py         # Patient chat, summary, blockchain APIs
|   |
|   |-- /static/              # Shared static files (minimal)
|   |   |-- /css/
|   |
|   |-- /templates/           # Staff-facing HTML files (main blueprint)
|   |   |-- base.html, login.html, dashboard.html, _sidebar_nav.html
|   |   |-- registration.html, manage_doctors.html, edit_doctor.html, ...
|   |   |-- pharmacy.html, pharmacy_stock.html, billing_log.html, ...
|   |   |-- lab_sample_collection.html, lab_workbench.html, ...
|   |   |-- consultation_room.html, consultation_log.html, ...
|   |   |-- manage_formulary.html, manage_lab_tests.html, ...
|   |   |-- patient_list.html, vitals_logging.html, vitals_patient.html, ...
|   |   |-- complaints.html, complaint_detail.html, ...
|   |   |-- er_dashboard.html, er_case_detail.html, ...
|   |   |-- mlc_add_log.html, mlc_view_log.html, mlc_view_all_logs.html, ...
|   |
|   |-- __init__.py           # Application factory (create_app)
|   |-- db.py                 # MongoDB connection setup
|   |-- models.py             # All DB functions
|   |-- routes.py             # Staff portal routes (main blueprint) + ER/Legal routes
|   |-- utils.py              # Utility functions (e.g., role decorator)
|   |-- ai_stubs.py           # Gemini API functions
|
|-- /uploads/                 # Folder for file uploads (e.g., complaint attachments)
|-- venv/                     # Virtual environment folder
|-- config.py                 # Configuration classes
|-- run.py                    # Entry point to run the app
|-- requirements.txt          # Python dependencies
|-- README.md                 # Project README file
|-- .env                      # Environment variables (SECRET!)
|-- .gitignore                # Git ignore patterns```
---    

## 🤖 AI Integration

* Uses `google-generativeai` library via `app/ai_stubs.py`.
* `analyze_patient_interaction`: Multi-intent chatbot brain.
* `analyze_triage_with_ai`: ESI-like scoring for ER/chat.
* `analyze_drug_interactions`: Checks medication lists.
* `GEMINI_API_KEY` required in `.env`.
* Fallbacks exist for API failures.
* Prompts define required JSON output format and logic flow.

---

## 🔮 Future Enhancements

* Implement remaining PDF modules (Bed Mgmt, OT, etc.).
* Database storage for chat history.
* Real appointment slot finding/booking.
* Refine AI prompts and error handling.
* Full user management (edit/delete).
* Tests (unit/integration).
* Security hardening (CSRF, validation).
* Replace placeholders (beds count).
* Refine multilingual TTS voice matching.

---
