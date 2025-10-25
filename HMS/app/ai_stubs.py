import re
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
import json

os.environ["GOOGLE_API_KEY"] = "AIzaSyA29vrgfMmglSXDp5qaijtS33g0nhByzNw" #"AIzaSyByTOIw_uFOQya7v1AoPxmWvT66wac0hvA"

chat = ChatGoogleGenerativeAI(
    model = "gemini-2.5-flash",
    temperature = 0.7
)

def analyze_complaint_with_ai(complaint_text):
    categories = [
        "Billing & Finance", "Staff Behavior", "Medical Care", 
        "Facility & Cleanliness", "Scheduling", "General Inquiry"
    ]
    urgencies = ["Low", "Medium", "High"]
    prompt = f"""
        You are an AI assistant for a hospital's complaint management system.
        Your task is to analyze a patient complaint and return ONLY a JSON object
        with two keys: "category" and "urgency".

        1.  **category**: Choose one of the following predefined categories:
            {json.dumps(categories)}
        
        2.  **urgency**: Choose one of the following predefined urgencies:
            {json.dumps(urgencies)}

        Analyze the following complaint text:
        ---
        {complaint_text}
        ---

        Return ONLY the JSON object.
        - Never return Markdown(MD) content.
        RULES: - You have to only respond to me in JSON format and don't include any Markdown(MD) tags in your responses
    """
    try:
        resp = chat.invoke([HumanMessage(content=prompt)])
        print(resp.content)
        json_str = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if not json_str:
            print("AI Error: No JSON object found in response.")
            return fallback_analysis(complaint_text)

        result = json.loads(json_str.group(0))

        print("Res : ", result)

        category = result.get("category", "General Inquiry")
        urgency = result.get("urgency", "Low")

        if category not in categories:
            category = "General Inquiry"
        if urgency not in urgencies:
            urgency = "Low"
        
        return category, urgency
    except Exception as e:
        print("Exception: ", e)
        return fallback_analysis(complaint_text)

def fallback_analysis(complaint_text):
    """
    The original stub logic to use if the AI fails.
    """
    text_lower = complaint_text.lower()
    category = "General Inquiry"
    urgency = "Low"

    # Rule-based urgency scoring
    if re.search(r'\b(pain|severe|urgent|asap|emergency)\b', text_lower):
        urgency = "High"
    elif re.search(r'\b(mistake|wrong|upset|delay)\b', text_lower):
        urgency = "Medium"

    # Rule-based categorization
    if re.search(r'\b(bill|charge|payment|invoice|insurance)\b', text_lower):
        category = "Billing & Finance"
    elif re.search(r'\b(rude|staff|nurse|reception|behavior)\b', text_lower):
        category = "Staff Behavior"
    elif re.search(r'\b(doctor|medical|treatment|misdiagnosis|pain)\b', text_lower):
        category = "Medical Care"
    elif re.search(r'\b(clean|room|housekeeping|facility)\b', text_lower):
        category = "Facility & Cleanliness"
    elif re.search(r'\b(appointment|schedule|wait|delay)\b', text_lower):
        category = "Scheduling"

    print("Res : ", category, urgency)

    return category, urgency

def analyze_triage_with_ai(symptoms, vitals_data):
    triage_levels = {
        1: "Level 1: Resuscitation (Immediate)",
        2: "Level 2: Emergency (1-14 mins)",
        3: "Level 3: Urgent (15-60 mins)",
        4: "Level 4: Less Urgent (61-120 mins)",
        5: "Level 5: Non-Urgent (121+ mins)"
    }

    prompt = f"""
    You are an expert Triage Nurse AI using the ESI (Emergency Severity Index) 5-level system.
    Your task is to analyze the patient's symptoms and vitals, then return ONLY a JSON object
    with two keys: "risk_score" (an integer 1-5) and "priority_level" (the string from the ESI levels).

    - **Level 1 (Resuscitation)**: Immediate, life-saving intervention required (e.g., cardiac arrest, severe respiratory distress).
    - **Level 2 (Emergency)**: High-risk situation, disoriented, severe pain, or vital signs in danger zone (e.g., chest pain, stroke symptoms).
    - **Level 3 (Urgent)**: Multiple resources required, but stable vitals (e.g., abdominal pain, high fever, bad fracture).
    - **Level 4 (Less Urgent)**: One resource required (e.g., simple cut, sprain).
    - **Level 5 (Non-Urgent)**: No resources required (e.g., prescription refill, cold symptoms).

    PATIENT DATA:
    - **Vitals**: {json.dumps(vitals_data)}
    - **Symptoms**: "{symptoms}"

    Return ONLY the JSON object.
    """

    try:
        # Send the prompt to the model
        response = chat.invoke([HumanMessage(content=prompt)])
        
        json_str = re.search(r'\{.*\}', response.content, re.DOTALL)
        if not json_str:
            print("AI Triage Error: No JSON object found.")
            return fallback_triage_analysis(symptoms, vitals_data)

        result = json.loads(json_str.group(0))
        
        # Validate the response
        score = result.get("risk_score", 5)
        level = result.get("priority_level", "Level 5: Non-Urgent")
        
        if score not in [1, 2, 3, 4, 5]:
            score = 5

        print(f"AI Triage Complete: Score={score}, Level={level}")
        return {"score": score, "level": level}

    except Exception as e:
        print(f"AI Triage Failed: {e}. Falling back to stub logic.")
        return fallback_triage_analysis(symptoms, vitals_data)

def fallback_triage_analysis(symptoms, vitals_data):
    """
    Fallback rule-based triage if AI fails.
    """
    s_lower = symptoms.lower()
    
    if "chest pain" in s_lower or "stroke" in s_lower or "breathing" in s_lower:
        return {"score": 2, "level": "Level 2: Emergency"}
        
    if vitals_data.get('temperature', 98.6) > 102:
        return {"score": 3, "level": "Level 3: Urgent"}
        
    if "fracture" in s_lower or "severe pain" in s_lower:
        return {"score": 3, "level": "Level 3: Urgent"}
        
    if "sprain" in s_lower or "cut" in s_lower:
        return {"score": 4, "level": "Level 4: Less Urgent"}

    return {"score": 5, "level": "Level 5: Non-Urgent"}


def analyze_drug_interactions(medication_list):
    global chat
    if not chat:
        print("AI Model not available. Falling back to stub logic.")
        return fallback_drug_interaction(medication_list)

    if len(medication_list) < 2:
        return {"alerts": [], "severe": False} # No interactions with one drug

    prompt = f"""
    You are an expert Clinical Pharmacist AI.
    Analyze the following list of medications for any potential drug-drug interactions.
    
    Medication List:
    {json.dumps(medication_list)}

    Return ONLY a JSON object with two keys:
    1. "alerts": A list of strings, with one string for each interaction found. (e.g., ["Aspirin and Warfarin increase bleeding risk."])
    2. "severe": A boolean (true/false) if any of the found interactions are life-threatening.

    If no interactions are found, return {{"alerts": [], "severe": false}}.
    Return ONLY the JSON object.
    """

    try:
        response = chat.invoke([HumanMessage(content=prompt)])
        json_str = re.search(r'\{.*\}', response.content, re.DOTALL)
        if not json_str:
            print("AI Interaction Error: No JSON object found.")
            return fallback_drug_interaction(medication_list)

        result = json.loads(json_str.group(0))
        return {
            "alerts": result.get("alerts", []),
            "severe": result.get("severe", False)
        }
    except Exception as e:
        print(f"AI Interaction Failed: {e}. Falling back to stub logic.")
        return fallback_drug_interaction(medication_list)

def fallback_drug_interaction(medication_list):
    """
    Fallback rule-based interaction check.
    """
    alerts = []
    severe = False
    
    # Simple rule for a common, severe interaction
    if "warfarin" in " ".join(medication_list).lower() and "aspirin" in " ".join(medication_list).lower():
        alerts.append("Warfarin + Aspirin: High risk of severe bleeding.")
        severe = True
        
    return {"alerts": alerts, "severe": severe}

def analyze_patient_symptoms(symptom_description):
    """
    Uses Gemini to analyze patient symptoms, estimate urgency,
    and suggest next steps within the hospital system.
    Returns: {"urgency_level": <str>, "explanation": <str>, "next_steps": [<str>]}
    """
    global chat
    if not chat:
        print("AI Model not available for symptom analysis.")
        return {
            "urgency_level": "Unknown",
            "explanation": "AI service unavailable. Please contact the hospital directly.",
            "next_steps": ["Call the hospital front desk.", "Visit the nearest clinic if concerned."]
        }

    # Define urgency levels for the AI
    urgency_levels = [
        "Immediate (ER Recommended)",
        "Urgent (Seek care soon - Appointment/Urgent Care)",
        "Less Urgent (Consider booking an appointment)",
        "Self-Care Recommended (Monitor symptoms)"
    ]

    prompt = f"""
    You are a helpful AI Patient Assistant for SRM Hospital Tiruchirappalli.
    Your goal is to analyze a patient's description of their symptoms,
    estimate an appropriate urgency level (using ONLY the predefined levels below),
    provide a brief explanation for the urgency estimation,
    and suggest 1-3 concrete next steps the patient can take within the SRM Hospital system
    (e.g., booking an appointment with a specific department, visiting the ER, calling a number).

    **CRITICAL:** Provide clear disclaimers that you are an AI and this is NOT a medical diagnosis. Advise seeking professional medical help for concerns.

    Predefined Urgency Levels (Choose ONE):
    {json.dumps(urgency_levels)}

    Patient's Symptom Description:
    ---
    "{symptom_description}"
    ---

    Return ONLY a JSON object with three keys:
    1. "urgency_level": The chosen predefined urgency level string.
    2. "explanation": A brief (1-2 sentence) explanation for the chosen urgency, including disclaimers.
    3. "next_steps": A list of 1-3 suggested action strings relevant to SRM Hospital.
    """

    try:
        response = chat.invoke([HumanMessage(content=prompt)])
        json_str = re.search(r'\{.*\}', response.content, re.DOTALL)
        if not json_str:
            print("AI Symptom Error: No JSON object found.")
            raise ValueError("AI response format error")

        result = json.loads(json_str.group(0))

        # Basic validation
        if result.get("urgency_level") not in urgency_levels:
            result["urgency_level"] = "Unknown"
        if not result.get("explanation"):
            result["explanation"] = "Could not determine urgency. Please consult a doctor. This is not medical advice."
        if not result.get("next_steps"):
            result["next_steps"] = ["Contact SRM Hospital for guidance."]

        print(f"AI Symptom Analysis Complete: Urgency={result['urgency_level']}")
        return result

    except Exception as e:
        print(f"AI Symptom Analysis Failed: {e}. Returning fallback.")
        return {
            "urgency_level": "Unknown",
            "explanation": f"AI analysis encountered an error ({e}). Please contact the hospital directly for medical advice. This is not a diagnosis.",
            "next_steps": ["Call the SRM Hospital front desk."]
        }
    
def analyze_patient_interaction(user_message, patient_identified=False):
    """
    A very clean and stable function.
    Understands what the user says and gives back structured info.
    No loops, no chat history, no overthinking.
    """
    global chat

    # If model missing
    if not chat:
        return {
            "intent": "error",
            "ai_response_text": "Sorry, I'm currently offline. Please contact the hospital directly.",
            "requires_identification": False,
            "action_details": {}
        }

    # Keep it short and direct
    prompt = f"""
    You are SRM Hospital's Patient Assistant AI.
    The user is {'already identified' if patient_identified else 'not identified yet'}.
    The user said: "{user_message}"

    Choose the intent and reply simply.
    Return **only** JSON like this:

    {{
        "intent": "<one of: greeting, check_symptoms_emergency, check_symptoms_non_emergency,
                   view_results, view_bill, view_appointments,
                   provide_identification, general_chat, goodbye, unknown>",
        "ai_response_text": "<short reply to user>",
        "requires_identification": true/false,
        "action_details": {{ optional info }},
        "triage_result": {{ 'symptoms':<symptoms is er is triggered> }}
    }}

    Rules:
    - If user says hello → intent="greeting"
    - If emergency symptoms (chest pain, bleeding, etc.) → check_symptoms_emergency
    - If mild symptoms (fever, headache) → check_symptoms_non_emergency
    - If asking to see bill/results/appointments → intent accordingly
    - If user gives name or number → provide_identification
    - If already identified → never ask again for ID
    - For general talk → general_chat
    - If not clear → unknown
    - if you want to identify a patient, then give action_details as a json of 'patient_name':<name>, 'phone_number':<ph.no> and set requires_identification as True if the patient types in both name or phno or even seperately.
    - You are a bot helping patients in Trichy SRM Hospital. so be relavent.
    - If a patient hacing emergency automatically proceed to ER registration immediately without advising them.
    - Please act wisely and don't frustrate the patients.
    - Always respond with a **single valid JSON**, no text outside it.
    """

    try:
        response = chat.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Extract JSON safely
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in: {content}")

        result = json.loads(match.group(0))


        # Ensure fields exist
        result.setdefault("intent", "unknown")
        result.setdefault("ai_response_text", "Sorry, I didn’t understand.")
        result.setdefault("requires_identification", False)
        result.setdefault("action_details", {})
        result.setdefault("triage_result", {})

        print("JSON_RESULT : ", result)

        # 🔒 Fix: Never ask ID again
        if patient_identified and result["intent"] == "provide_identification":
            result["intent"] = "general_chat"
            result["requires_identification"] = False
            result["ai_response_text"] = "You're already identified. How can I assist further?"

        # 🔒 Fix: Ask for ID once for private requests
        if not patient_identified and result["intent"] in ["view_results", "view_bill", "view_appointments", "provide_identification", "check_symptoms_emergency"]:
            result["requires_identification"] = True
            result["intent"] = "request_identification"
            result["ai_response_text"] = "Please provide your registered name or phone number to continue."

        return result

    except Exception as e:
        print(f"❌ Error analyzing message: {e}")
        return {
            "intent": "error",
            "ai_response_text": "Sorry, something went wrong while processing your message.",
            "requires_identification": False,
            "action_details": {}
        }