import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from together import Together
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# Define enums similar to the email-analyzer-api.py
class SentimentEnum(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral" 
    NEGATIVE = "Negative"

class UrgencyEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class IntentEnum(str, Enum):
    REQUEST = "Request"
    INFORMATION = "Information"
    QUESTION = "Question"
    TASK_ASSIGNMENT = "Task Assignment"
    FOLLOW_UP = "Follow-up"
    INCIDENT = "Incident"
    CHANGE = "Change"
    PROBLEM = "Problem"
    OTHER = "Other"

# Define standard ServiceNow business services
SERVICENOW_BUSINESS_SERVICES = {
    "IT Service Management": [
        "ITSM", "IT Service Management", "Service Desk", "Help Desk",
        "Incident Management", "Problem Management", "Change Management",
        "Service Catalog", "Service Request", "Knowledge Management"
    ],
    "IT Operations Management": [
        "ITOM", "IT Operations", "Infrastructure Management",
        "Event Management", "Discovery", "Service Mapping",
        "Cloud Management", "Operational Intelligence"
    ],
    "IT Business Management": [
        "ITBM", "IT Business Management", "Project Portfolio Management",
        "Application Portfolio Management", "Financial Management",
        "Demand Management", "Resource Management"
    ],
    "Customer Service Management": [
        "CSM", "Customer Service", "Customer Support",
        "Case Management", "Customer Experience",
        "Field Service", "Customer Portal"
    ],
    "Human Resources Service Delivery": [
        "HRSD", "HR Service Delivery", "Employee Service Center",
        "HR Case Management", "Employee Portal",
        "HR Knowledge Management", "HR Service Catalog"
    ],
    "Security Operations": [
        "SecOps", "Security Operations", "Security Incident Response",
        "Vulnerability Response", "Threat Intelligence",
        "Security Operations Center", "SOC"
    ],
    "Governance, Risk, and Compliance": [
        "GRC", "Governance", "Risk Management", "Compliance",
        "Policy Management", "Audit Management",
        "Risk Assessment", "Compliance Management"
    ]
}

# Define customer-side ServiceNow entities
CUSTOMER_ENTITIES = {
    "customer_type": [
        "Employee", "Customer", "Partner", "Vendor", "Contractor",
        "External User", "Internal User", "Guest", "End User"
    ],
    "customer_priority": [
        "Critical", "High", "Medium", "Low", "P1", "P2", "P3", "P4"
    ],
    "customer_impact": [
        "High", "Medium", "Low", "None",
        "Business Critical", "Business Important", "Business Normal"
    ],
    "customer_location": [
        "Office", "Remote", "Home", "Field", "Branch",
        "Headquarters", "Data Center", "Store", "Site"
    ],
    "customer_department": [
        "IT", "HR", "Finance", "Sales", "Marketing",
        "Operations", "Customer Service", "Support",
        "Development", "Engineering", "Product"
    ],
    "customer_role": [
        "Manager", "Director", "VP", "C-Level", "Admin",
        "User", "Developer", "Analyst", "Specialist",
        "Consultant", "Coordinator"
    ]
}

# Compile regex patterns for entity extraction
ENTITY_PATTERNS = {
    # ServiceNow record identifiers
    "incident_number": re.compile(r"(?:incident|ticket|case)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "change_request": re.compile(r"(?:change|CR)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "problem_number": re.compile(r"(?:problem|PR)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "task_number": re.compile(r"(?:task|TASK)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "request_number": re.compile(r"(?:request|REQ)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    
    # Customer information
    "customer_type": re.compile(r"(?:customer|user)\s+(?:type|category)\s*(?:is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_type"]) + ")", re.IGNORECASE),
    "customer_priority": re.compile(r"(?:priority|impact)\s+(?:level|is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_priority"]) + ")", re.IGNORECASE),
    "customer_impact": re.compile(r"(?:business|impact)\s+(?:impact|level|is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_impact"]) + ")", re.IGNORECASE),
    "customer_location": re.compile(r"(?:location|working from|workplace)\s*(?:is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_location"]) + ")", re.IGNORECASE),
    "customer_department": re.compile(r"(?:department|dept|team)\s*(?:is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_department"]) + ")", re.IGNORECASE),
    "customer_role": re.compile(r"(?:role|position|title)\s*(?:is|:)?\s*(" + "|".join(CUSTOMER_ENTITIES["customer_role"]) + ")", re.IGNORECASE),
    
    # User and contact information
    "user_id": re.compile(r"(?:user|employee)\s+(?:id|number|#)?\s*(?:is|:)?\s*([A-Z0-9]+)", re.IGNORECASE),
    "username": re.compile(r"(?:username|login|account)\s+(?:is|:)?\s*([a-zA-Z0-9._-]+)", re.IGNORECASE),
    "phone_number": re.compile(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", re.IGNORECASE),
    "email_address": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    
    # Time and date information
    "date": re.compile(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:tomorrow|next week|next month|today|yesterday)\b", re.IGNORECASE),
    "time": re.compile(r"\b(?:at|around|by)?\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\b", re.IGNORECASE),
    
    # Technical information
    "url": re.compile(r"https?://\S+", re.IGNORECASE),
    "error_code": re.compile(r"(?:error|code|error code)\s*(?:is|:)?\s*(\d{3}(?:\s*-\s*[A-Za-z]+)?)", re.IGNORECASE),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", re.IGNORECASE),
    "mac_address": re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b", re.IGNORECASE),
    
    # Location and organizational information
    "location": re.compile(r"(?:in|from|at)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Street|Avenue|Boulevard|Road|Lane|Drive|Court|Place|Square|City|Town|Building|Office|Floor|Room|Suite|Department|Center|Campus|Site|Location|Facility|Headquarters|Branch|Store|Shop|Outlet|Warehouse|Data Center|Server Room|Lab|Laboratory|Workspace|Area|Zone|Region|District|State|Province|Country))", re.IGNORECASE),
    "department": re.compile(r"(?:department|dept|team)\s+(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    
    # ServiceNow specific fields
    "priority": re.compile(r"(?:priority|impact)\s+(?:is|:)?\s*(critical|high|medium|low)", re.IGNORECASE),
    "category": re.compile(r"(?:category|type)\s*(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "subcategory": re.compile(r"(?:subcategory|subtype)\s*(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "assignment_group": re.compile(r"(?:assignment|assigned|group)\s*(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "affected_ci": re.compile(r"(?:affected|impacted|configuration)\s+(?:item|ci)\s*(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "business_service": re.compile(
        r"(?:business|service|using|via|through)\s+(?:is|:)?\s*(" + 
        "|".join([
            re.escape(service) for services in SERVICENOW_BUSINESS_SERVICES.values() 
            for service in services
        ]) + 
        r")",
        re.IGNORECASE
    ),
    "state": re.compile(r"(?:state|status)\s+(?:is|:)?\s*(new|in progress|pending|resolved|closed|cancelled)", re.IGNORECASE),
    
    # System and equipment information
    "system_name": re.compile(r"(?:system|application|software|hardware|device|equipment|portal)\s+(?:name|is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "equipment_type": re.compile(r"(?:kiosk|terminal|device|equipment|hardware|machine)\s+(?:type|is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "issue_impact": re.compile(r"(?:impact|affecting|affects|impacting|impacts)\s+(?:is|:)?\s*([^.,]+)", re.IGNORECASE),
    "issue_symptoms": re.compile(r"(?:symptoms|behavior|what's happening|what is happening)\s*(?:is|:)?\s*([^.,]+)", re.IGNORECASE),
    "store_manager": re.compile(r"(?:reported by|reported|manager|supervisor|agent)\s*(?:is|:)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE),
    "issue_location": re.compile(r"(?:access|accessing|using|in)\s+(?:the|to)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "access_issue": re.compile(r"(?:unable|cannot|cant|can't|failed|failing)\s+(?:to)?\s*(?:access|login|log in|log-in|authenticate|authorize)\s+(?:to|the)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "reported_time": re.compile(r"(?:reported|occurred|happened|started)\s+(?:at|time|when)?\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?(?:\s+today|\s+yesterday)?)", re.IGNORECASE),
}

# Define urgency keywords with more comprehensive coverage
HIGH_URGENCY_KEYWORDS = {
    "urgent", "asap", "immediately", "emergency", "critical",
    "deadline", "today", "tomorrow", "soon", "quickly", "rush",
    "blocking", "outage", "down", "broken", "failed", "error",
    "cannot", "unable", "stopped", "crashed", "not working",
    "stopped working", "system down", "system outage", "system failure",
    "immediate assistance", "escalate", "significant impact", "affecting"
}

MEDIUM_URGENCY_KEYWORDS = {
    "next week", "soon", "timely", "when you can", "this week",
    "important", "attention", "priority", "issue", "problem",
    "concern", "request", "needed", "required", "should"
}

# Define intent keywords for better classification
INTENT_KEYWORDS = {
    "follow-up": {
        "follow up", "follow-up", "followup", "no update", "haven't been any updates",
        "check status", "status update", "any progress", "still waiting", "escalate"
    },
    "incident": {
        "error", "issue", "problem", "broken", "not working", "failed", "crash", "down", "outage",
        "complaint", "delayed", "refund", "return", "customer complaint", "customer issue",
        "customer problem", "customer service", "service issue", "service problem",
        "system outage", "system down", "system failure", "technical issue", "technical problem",
        "kiosk", "self-checkout", "checkout", "terminal", "device", "equipment", "hardware",
        "software", "application", "system", "network", "server", "database"
    },
    "request": {
        "need", "want", "request", "would like", "please", "could you", "can you",
        "install", "setup", "configure", "access", "permission", "approval"
    },
    "question": {
        "?", "how", "what", "when", "where", "why", "who", "which",
        "can you tell me", "do you know", "could you explain"
    },
    "change": {
        "change", "modify", "update", "alter", "switch", "convert",
        "upgrade", "downgrade", "replace", "substitute"
    },
    "problem": {
        "root cause", "investigate", "analyze", "troubleshoot", "diagnose",
        "fix", "resolve", "solution", "workaround"
    },
    "information": {
        "inform", "notify", "update", "status", "progress", "report",
        "let you know", "advise", "alert", "announce"
    }
}

def clean_json_response(content: str) -> str:
    """
    Removes Markdown-style code block from the model's response.
    """
    # If the output starts with ``` and ends with ```, strip them
    if content.startswith("```") and content.endswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)  # remove ```json or ```
        content = content.rstrip("`").rstrip()  # remove trailing backticks
    
    # Try to find JSON object in the response if not properly formatted
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json_match.group(0).strip()
    
    return content.strip()

def normalize_business_service(service: str) -> str:
    """Normalize business service to standard ServiceNow service"""
    service = service.strip()
    
    # Check for exact matches first
    for category, services in SERVICENOW_BUSINESS_SERVICES.items():
        if service in services:
            return category
    
    # Check for partial matches
    service_lower = service.lower()
    for category, services in SERVICENOW_BUSINESS_SERVICES.items():
        if any(service_lower in s.lower() for s in services):
            return category
    
    return service

def extract_entities_from_text(text: str) -> Dict[str, Any]:
    """Extract entities from email text using regex patterns"""
    entities = {}
    
    # Extract entities based on patterns
    for entity_name, pattern in ENTITY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            # For numeric IDs, convert to string
            if entity_name in ["incident_number", "change_request", "problem_number", "user_id"]:
                # Only include if it's a valid ID format
                if re.match(r'^[A-Z0-9]+$', str(matches[0])):
                    entities[entity_name] = str(matches[0]).upper()
            # For business service, normalize to standard service
            elif entity_name == "business_service":
                normalized_service = normalize_business_service(matches[0])
                if normalized_service:
                    entities[entity_name] = normalized_service
            # For dates, ensure proper format
            elif entity_name == "date":
                date_str = str(matches[0])
                # Only include if it's a proper date format
                if re.match(r'^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:tomorrow|next week|next month|today|yesterday)\b', date_str, re.IGNORECASE):
                    entities[entity_name] = date_str
            # For other entities, keep as string
            else:
                # Clean up the match (remove leading/trailing special chars and newlines)
                clean_match = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$|\n.*$', '', matches[0])
                if clean_match:
                    # Additional validation for specific entity types
                    if entity_name == "department":
                        # Only include if it's a proper department name (capitalized words)
                        if re.match(r'^[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*$', clean_match):
                            entities[entity_name] = clean_match
                    elif entity_name == "location":
                        # Only include if it's a proper location name with a valid suffix
                        if re.match(r'^[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Street|Avenue|Boulevard|Road|Lane|Drive|Court|Place|Square|City|Town|Building|Office|Floor|Room|Suite|Department|Center|Campus|Site|Location|Facility|Headquarters|Branch|Store|Shop|Outlet|Warehouse|Data Center|Server Room|Lab|Laboratory|Workspace|Area|Zone|Region|District|State|Province|Country)$', clean_match, re.IGNORECASE):
                            entities[entity_name] = clean_match
                    elif entity_name == "request_number":
                        # Only include if it's a proper request number format
                        if re.match(r'^[A-Z0-9]+$', clean_match):
                            entities[entity_name] = clean_match
                    else:
                        entities[entity_name] = clean_match
    
    return entities

def analyze_email_content(text: str, regex_entities: Dict[str, Any]) -> dict:
    """
    Analyzes email content using LLM to determine sentiment, intent, urgency, keywords,
    and extract entities
    """
    # Prepare the prompt for the LLM
    prompt = f"""Analyze this email and extract key information:

Email Content:
{text}

Please provide a JSON response with the following structure:
{{
    "sentiment": "Positive/Neutral/Negative",
    "urgency": "High/Medium/Low",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "intent": "Request/Information/Question/Task Assignment/Follow-up/Incident/Change/Problem/Other",
    "entities": {{
        // Extract ONLY the most relevant and helpful entities that are EXPLICITLY mentioned in the email.
        // Focus on information that will be useful for ticket creation and issue resolution.
        // Examples of useful entities:
        // - incident_number: Incident/ticket numbers (e.g., INC123456)
        // - error_code: Error codes or messages (e.g., "401", "403 Forbidden")
        // - system_name: Name of affected system/application
        // - issue_type: Type of issue (e.g., "Printer Access Issue")
        // - issue_location: Where the issue is occurring
        // - employee_name: Name of affected user
        // - employee_id: Employee ID or number
        // - reporter_name: Name of person reporting the issue
        // - reporter_role: Role of person reporting
        // - sender_email: Email of sender
        // - recipient_email: Email of recipient
        // - reported_time: When the issue was reported
    }}
}}

CRITICAL RULES:
1. ONLY include entities that are EXPLICITLY mentioned in the email
2. DO NOT make assumptions or add information that isn't in the text
3. DO NOT include any keys with null values
4. For dates, use the exact format mentioned in the email
5. DO NOT infer or guess values for any fields
6. If a field's value is not explicitly stated, DO NOT include that field
7. Preserve exact case and formatting as mentioned in the email
8. ONLY include entities that will be helpful for ticket creation and issue resolution
9. Pay special attention to:
    - Incident/ticket numbers
    - Error codes and messages
    - System names and locations
    - User information
    - Reporter information
    - Communication details

ENTITY EXTRACTION EXAMPLES:
1. For incident number:
   Input: "Ticket Number: INC908721"
   Output: {{"incident_number": "INC908721"}}

2. For error code:
   Input: "Authentication Failed - Code 401"
   Output: {{"error_code": "401"}}

3. For reporter information:
   Input: "Thanks,\nAnita Roy\nIT Support Specialist"
   Output: {{
       "reporter_name": "Anita Roy",
       "reporter_role": "IT Support Specialist"
   }}

4. For issue details:
   Input: "network printer on Floor 5"
   Output: {{
       "issue_location": "Floor 5",
       "system_name": "network printer"
   }}"""

    try:
        # Try primary model first (Llama-3.3-70B-Instruct-Turbo)
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
        )
        logger.info("Successfully used primary model (Llama-3.3-70B-Instruct-Turbo)")
    except Exception as e:
        logger.error("Primary model failed: %s", str(e))
        # Try first fallback model
        logger.info("Attempting to use first fallback model: mistralai/Mistral-7B-Instruct-v0.1")
        try:
            response = client.chat.completions.create(
                model="mistralai/Mistral-7B-Instruct-v0.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024,
                timeout=30,
            )
            logger.info("Successfully used first fallback model")
        except Exception as e2:
            logger.error("First fallback model failed: %s", str(e2))
            # Try second fallback model
            logger.info("Attempting to use second fallback model: togethercomputer/llama-2-7b-chat")
            try:
                response = client.chat.completions.create(
                    model="togethercomputer/llama-2-7b-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1024,
                    timeout=30,
                )
                logger.info("Successfully used second fallback model")
            except Exception as e3:
                logger.error("Second fallback model also failed: %s", str(e3))
                logger.info("Falling back to default response")
                return {
                    "sentiment": "Neutral",
                    "urgency": "Medium",
                    "keywords": [],
                    "intent": "Other",
                    "entities": {}
                }

    content = response.choices[0].message.content.strip()
    logger.info("Raw model output:\n%s", content)

    try:
        cleaned = clean_json_response(content)
        logger.debug("Cleaned JSON: %s", cleaned)

        result = json.loads(cleaned)
        
        # Validate the result has all required fields
        expected_keys = ["sentiment", "urgency", "keywords", "intent", "entities"]
        if not all(key in result for key in expected_keys):
            missing_keys = [key for key in expected_keys if key not in result]
            logger.warning("Missing expected keys in LLM response: %s", str(missing_keys))
            # Add any missing keys with default values
            if "sentiment" not in result:
                result["sentiment"] = "Neutral"
            if "urgency" not in result:
                result["urgency"] = "Medium"
            if "keywords" not in result:
                result["keywords"] = []
            if "intent" not in result:
                result["intent"] = "Other"
            if "entities" not in result:
                result["entities"] = {}
        
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Error parsing response: %s", str(e))
        return {
            "sentiment": "Neutral",
            "urgency": "Medium",
            "keywords": [],
            "intent": "Other",
            "entities": {}
        }

def determine_urgency(text: str) -> str:
    """Determine the urgency level based on keywords in the text"""
    text_lower = text.lower()
    
    for keyword in HIGH_URGENCY_KEYWORDS:
        if keyword in text_lower:
            return UrgencyEnum.HIGH.value
    
    for keyword in MEDIUM_URGENCY_KEYWORDS:
        if keyword in text_lower:
            return UrgencyEnum.MEDIUM.value
    
    return UrgencyEnum.LOW.value

def determine_intent(text: str) -> str:
    """Determine the intent of the email based on keywords"""
    text_lower = text.lower()
    
    # First check for follow-up as it's a specific case
    if any(keyword in text_lower for keyword in INTENT_KEYWORDS["follow-up"]):
        return IntentEnum.FOLLOW_UP.value
    
    # Then check for incident/complaint as it's a high priority case
    if any(keyword in text_lower for keyword in INTENT_KEYWORDS["incident"]):
        return IntentEnum.INCIDENT.value
    
    # Then check other intents
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent not in ["follow-up", "incident"] and any(keyword in text_lower for keyword in keywords):
            return intent.capitalize()
    
    return IntentEnum.OTHER.value

def extract_entities(text: str, additional_details: Optional[Dict[str, Any]] = None, request_data: Optional[Dict[str, Any]] = None) -> dict:
    """
    Enhanced entity extraction that uses LLM as the primary method
    """
    # Split the email text into subject and body if it has a "Subject:" line
    subject = ""
    body = text
    
    if text.startswith("Subject:"):
        parts = text.split("\n\n", 1)
        subject = parts[0].replace("Subject:", "").strip()
        body = parts[1] if len(parts) > 1 else ""
    
    # Prepare the full email content for LLM analysis
    full_email_content = f"""Subject: {subject if subject else request_data.get('email_subject', '')}

{body if body else request_data.get('email_body', '')}"""

    # Add any additional details to the content
    if additional_details:
        full_email_content += "\n\nAdditional Details:\n" + "\n".join([f"{k}: {v}" for k, v in additional_details.items()])
    
    # Add request data if present
    if request_data:
        if "sender" in request_data:
            full_email_content += f"\n\nSender: {request_data['sender']}"
        if "recipient" in request_data:
            full_email_content += f"\n\nRecipient: {request_data['recipient']}"
    
    # Have LLM analyze the content
    result = analyze_email_content(full_email_content, {})
    
    return result

def analyze_email(email_text: str) -> dict:
    """
    Analyzes email content and generates an appropriate reply
    """
    # Prepare the prompt for the LLM
    prompt = f"""Analyze this email and generate an appropriate reply:

Email Content:
{email_text}

Please provide a JSON response with the following structure:
{{
    "generated_reply": "Your suggested reply to the email"
}}

Focus on generating a professional and helpful response."""

    try:
        # Try primary model first
        response = client.chat.completions.create(
            model="mistralai/Mistral-7B-Instruct-v0.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
        )
        logger.info("Successfully used primary model")
    except Exception as e:
        logger.error("Primary model failed: %s", str(e))
        # Try fallback model if primary fails
        logger.info("Attempting to use fallback model: togethercomputer/llama-2-7b-chat")
        try:
            response = client.chat.completions.create(
                model="togethercomputer/llama-2-7b-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1024,
                timeout=30,
            )
            logger.info("Successfully used fallback model")
        except Exception as e2:
            logger.error("Fallback model also failed: %s", str(e2))
            logger.info("Falling back to default reply")
            return {
                "generated_reply": "Thank you for your email. I will review and respond to your message shortly."
            }

    content = response.choices[0].message.content.strip()
    logger.info("Raw model output:\n%s", content)

    try:
        cleaned = clean_json_response(content)
        logger.debug("Cleaned JSON: %s", cleaned)

        result = json.loads(cleaned)
        
        # Validate the result has the required field
        if "generated_reply" not in result:
            logger.warning("Missing generated_reply in LLM response")
            result["generated_reply"] = "Thank you for your email. I will review and respond to your message shortly."
        
        # Ensure generated_reply is a string and not empty
        if not result.get("generated_reply") or not isinstance(result["generated_reply"], str):
            result["generated_reply"] = "Thank you for your email. I will review and respond to your message shortly."
            
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Error parsing response: %s", str(e))
        return {
            "generated_reply": "Thank you for your email. I will review and respond to your message shortly."
        }
