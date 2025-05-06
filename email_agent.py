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

# Compile regex patterns for entity extraction (imported from email-analyzer-api.py)
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
    "error_code": re.compile(r"(?:error|code|error code)\s*(?:is|:)?\s*([A-Z0-9_]+)", re.IGNORECASE),
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
}

# Define urgency keywords with more comprehensive coverage
HIGH_URGENCY_KEYWORDS = {
    "urgent", "asap", "immediately", "emergency", "critical",
    "deadline", "today", "tomorrow", "soon", "quickly", "rush",
    "blocking", "outage", "down", "broken", "failed", "error",
    "cannot", "unable", "stopped", "crashed", "not working"
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
    "incident": {"error", "issue", "problem", "broken", "not working", "failed", "crash", "down", "outage"},
    "request": {"need", "want", "request", "would like", "please", "could you", "can you"},
    "question": {"?", "how", "what", "when", "where", "why", "who", "which"},
    "change": {"change", "modify", "update", "alter", "switch", "convert"},
    "problem": {"root cause", "investigate", "analyze", "troubleshoot", "diagnose"},
    "information": {"inform", "notify", "update", "status", "progress", "report"}
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

def extract_entities(text: str) -> Dict[str, Any]:
    """Extract entities from email text using regex patterns"""
    entities = {}
    
    # Extract entities based on patterns
    for entity_name, pattern in ENTITY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            # For numeric IDs, convert to string
            if entity_name in ["incident_number", "change_request", "problem_number", "user_id"]:
                entities[entity_name] = str(matches[0]).upper()
            # For business service, normalize to standard service
            elif entity_name == "business_service":
                normalized_service = normalize_business_service(matches[0])
                if normalized_service:
                    entities[entity_name] = normalized_service
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
                    else:
                        entities[entity_name] = clean_match
    
    return entities

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
    
    # Then check other intents
    for intent, keywords in INTENT_KEYWORDS.items():
        if intent != "follow-up" and any(keyword in text_lower for keyword in keywords):
            return intent.capitalize()
    
    return IntentEnum.OTHER.value

def analyze_email(email_text: str, additional_details: Optional[Dict[str, Any]] = None, request_data: Optional[Dict[str, Any]] = None) -> dict:
    """
    Enhanced email analyzer that combines regex-based entity extraction and LLM analysis
    """
    # Split the email text into subject and body if it has a "Subject:" line
    subject = ""
    body = email_text
    
    if email_text.startswith("Subject:"):
        parts = email_text.split("\n\n", 1)
        subject = parts[0].replace("Subject:", "").strip()
        body = parts[1] if len(parts) > 1 else ""
    
    # Extract entities from the entire request data
    entities = {}
    
    # Extract from email subject and body
    subject_entities = extract_entities(subject)
    body_entities = extract_entities(body)
    entities.update({**body_entities, **subject_entities})
    
    # Extract from additional details if present
    if additional_details:
        # Convert additional details to a string for entity extraction
        additional_text = "\n".join([f"{k}: {v}" for k, v in additional_details.items()])
        additional_entities = extract_entities(additional_text)
        entities.update(additional_entities)
        # Also include the additional details as is
        entities.update(additional_details)
    
    # Extract from request data if present
    if request_data:
        # Extract from email_subject and email_body
        if "email_subject" in request_data:
            subject_entities = extract_entities(request_data["email_subject"])
            entities.update(subject_entities)
        if "email_body" in request_data:
            body_entities = extract_entities(request_data["email_body"])
            entities.update(body_entities)
        
        # Extract from sender and recipient
        if "sender" in request_data:
            entities["sender_email"] = request_data["sender"]
        if "recipient" in request_data:
            entities["recipient_email"] = request_data["recipient"]
        
        # Extract from additional_details if present in request_data
        if "additional_details" in request_data:
            additional_entities = extract_entities(str(request_data["additional_details"]))
            entities.update(additional_entities)
            entities.update(request_data["additional_details"])
    
    # Remove any entities with "N/A" values or empty strings
    entities = {k: v for k, v in entities.items() if v != "N/A" and v != ""}
    
    # Determine initial urgency based on keywords
    rule_based_urgency = determine_urgency(email_text)
    
    # Determine initial intent based on keywords
    rule_based_intent = determine_intent(email_text)
    
    # Format additional details for the prompt
    additional_details_text = ""
    if additional_details:
        additional_details_text = "\nAdditional Context:\n" + "\n".join([f"- {k}: {v}" for k, v in additional_details.items()])
    
    # Updated prompt to request more structured JSON output with correct entities format
    prompt = f"""
    Analyze this ServiceNow email and return a JSON object with these exact fields:

    1. intent (MUST be one of these exact values):
       - "Follow-up": For status checks, update requests, or following up on existing issues
       - "Incident": For new issues being reported for the first time
       - "Request": For general requests or asking for something
       - "Question": For emails primarily asking questions
       - "Information": For providing information or updates
       - "Task Assignment": For assigning or requesting task assignments
       - "Change": For change requests or modifications
       - "Problem": For problem management or root cause analysis
       - "Other": Only if none of the above categories fit

    2. sentiment: "Positive", "Neutral", or "Negative"
    3. urgency: "High", "Medium", or "Low"
    4. keywords: List of 5 most important keywords
    5. entities: IMPORTANT - Only include entities that are EXPLICITLY mentioned in the email. Do not infer or assume any entities.
       DO NOT include any entities with null values. Only include entities that have actual values.
       DO NOT include nested objects with null values. Only include the specific entity fields that have values.

       For example, if only customer_type has a value, include it directly:
       {{
         "customer_type": "Customer",
         "store_id": "112",
         "order_id": "ORD789456"
       }}

       NOT like this:
       {{
         "Customer Information": {{
           "customer_type": "Customer",
           "customer_priority": null,
           ...
         }}
       }}

       A. ServiceNow Records (only if explicitly mentioned):
          - incident_number: ServiceNow incident numbers (e.g., "INC0023487")
          - change_request: Change request numbers (e.g., "CHG123456")
          - problem_number: Problem record numbers (e.g., "PRB789012")
          - task_number: Task numbers (e.g., "TASK123456")
          - request_number: Request numbers (e.g., "REQ123456")

       B. Customer Information (only if explicitly mentioned):
          - customer_type: "Employee", "Customer", "Partner", "Vendor", "Contractor", "External User", "Internal User", "Guest", "End User"
          - customer_priority: "Critical", "High", "Medium", "Low", "P1", "P2", "P3", "P4"
          - customer_impact: "High", "Medium", "Low", "None", "Business Critical", "Business Important", "Business Normal"
          - customer_location: "Office", "Remote", "Home", "Field", "Branch", "Headquarters", "Data Center", "Store", "Site"
          - customer_department: "IT", "HR", "Finance", "Sales", "Marketing", "Operations", "Customer Service", "Support", "Development", "Engineering", "Product"
          - customer_role: "Manager", "Director", "VP", "C-Level", "Admin", "User", "Developer", "Analyst", "Specialist", "Consultant", "Coordinator"

       C. ServiceNow Services (only if explicitly mentioned):
          - business_service: One of these exact values:
            * "IT Service Management" (for Service Desk, Help Desk, ITSM)
            * "IT Operations Management" (for ITOM, Infrastructure)
            * "IT Business Management" (for ITBM, Project Management)
            * "Customer Service Management" (for CSM, Customer Support)
            * "Human Resources Service Delivery" (for HRSD, HR Services)
            * "Security Operations" (for SecOps, Security)
            * "Governance, Risk, and Compliance" (for GRC, Compliance)

       D. Ticket Information (only if explicitly mentioned):
          - priority: "Critical", "High", "Medium", "Low"
          - category: The main category of the issue
          - subcategory: More specific category
          - assignment_group: Team or group
          - affected_ci: Affected configuration item
          - state: "New", "In Progress", "Pending", "Resolved", "Closed"

       E. Contact Information (only if explicitly mentioned):
          - sender_email: Email address of the sender
          - recipient_email: Email address of the recipient

    6. summary: Brief 25-word summary
    7. generated_reply: Professional response that:
       - Acknowledges the specific issue
       - References any incident numbers
       - Indicates investigation will occur
       - DOES NOT ask for information that is already provided in the email
       - Uses information already available (like order IDs, customer names, etc.) without asking for them again

    Email to analyze:
    Subject: {subject}
    Body: {body}
    {additional_details_text}

    Return ONLY a valid JSON object. No explanations or markdown. DO NOT include any null values in the entities.
    """
    
    logger.info("Attempting to use primary model: mistralai/Mistral-7B-Instruct-v0.1")
    logger.info("Complete prompt being sent to model:\n%s", prompt)
    
    # Use try-except for API call to handle potential Together AI service issues
    try:
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
            logger.info("Falling back to rule-based analysis")
            # Return a default response with our extracted entities when API completely fails
            return {
                "sentiment": "Neutral",
                "urgency": rule_based_urgency,
                "keywords": [],
                "generated_reply": "Thank you for your email. I will review and respond to your message shortly.",
                "entities": entities,
                "intent": "Other",
                "summary": subject if subject else "Email received"
            }

    content = response.choices[0].message.content.strip()
    logger.info("Raw model output:\n%s", content)

    try:
        cleaned = clean_json_response(content)
        logger.debug("Cleaned JSON: %s", cleaned)

        result = json.loads(cleaned)
        
        # Validate the result has all required fields
        expected_keys = ["sentiment", "urgency", "keywords", "generated_reply", "intent", "summary", "entities"]
        if not all(key in result for key in expected_keys):
            missing_keys = [key for key in expected_keys if key not in result]
            logger.warning("Missing expected keys in LLM response: %s", str(missing_keys))
            logger.warning("Available keys in response: %s", str(list(result.keys())))
            # Add any missing keys with default values
            if "sentiment" not in result:
                logger.info("Adding default sentiment: Neutral")
                result["sentiment"] = "Neutral"
            if "urgency" not in result:
                logger.info("Adding default urgency: %s", str(rule_based_urgency))
                result["urgency"] = rule_based_urgency
            if "keywords" not in result:
                logger.info("Adding default keywords: []")
                result["keywords"] = []
            if "generated_reply" not in result:
                logger.info("Adding default response")
                result["generated_reply"] = "I received your email and will get back to you shortly."
            if "intent" not in result:
                logger.info("Adding default intent: Other")
                result["intent"] = "Other"
            if "summary" not in result:
                logger.info("Adding default summary")
                result["summary"] = subject if subject else "Email received"
            if "entities" not in result:
                logger.info("Using extracted entities")
                result["entities"] = entities
        
        # Ensure entity structure is correct
        if "entities" not in result or not isinstance(result["entities"], dict):
            # Use our regex-extracted entities
            result["entities"] = entities
        else:
            # Merge LLM-identified entities with our regex entities, giving priority to regex ones
            result["entities"] = {**result["entities"], **entities}
        
        # Remove business_service if it's just "Desk"
        if result["entities"].get("business_service") == "Desk":
            result["entities"].pop("business_service")
        
        # Normalize urgency to match enum values
        if result.get("urgency") and isinstance(result["urgency"], str):
            urgency_lower = result["urgency"].lower()
            if "high" in urgency_lower:
                result["urgency"] = UrgencyEnum.HIGH.value
            elif "medium" in urgency_lower or "med" in urgency_lower:
                result["urgency"] = UrgencyEnum.MEDIUM.value
            elif "low" in urgency_lower:
                result["urgency"] = UrgencyEnum.LOW.value
            else:
                result["urgency"] = rule_based_urgency
        else:
            result["urgency"] = rule_based_urgency
            
        # Normalize intent to match enum values
        if result.get("intent") and isinstance(result["intent"], str):
            intent_lower = result["intent"].lower()
            # Check for follow-up first as it's a specific case
            if any(phrase in intent_lower for phrase in INTENT_KEYWORDS["follow-up"]):
                result["intent"] = IntentEnum.FOLLOW_UP.value
            elif "request" in intent_lower:
                result["intent"] = IntentEnum.REQUEST.value
            elif "information" in intent_lower:
                result["intent"] = IntentEnum.INFORMATION.value
            elif "question" in intent_lower:
                result["intent"] = IntentEnum.QUESTION.value
            elif "task" in intent_lower and "assignment" in intent_lower:
                result["intent"] = IntentEnum.TASK_ASSIGNMENT.value
            elif "incident" in intent_lower:
                result["intent"] = IntentEnum.INCIDENT.value
            elif "change" in intent_lower:
                result["intent"] = IntentEnum.CHANGE.value
            elif "problem" in intent_lower:
                result["intent"] = IntentEnum.PROBLEM.value
            else:
                result["intent"] = IntentEnum.OTHER.value
        else:
            result["intent"] = rule_based_intent
            
        # Normalize sentiment to match enum values
        if result.get("sentiment") and isinstance(result["sentiment"], str):
            sentiment_lower = result["sentiment"].lower()
            if "positive" in sentiment_lower:
                result["sentiment"] = SentimentEnum.POSITIVE.value
            elif "negative" in sentiment_lower:
                result["sentiment"] = SentimentEnum.NEGATIVE.value
            else:
                result["sentiment"] = SentimentEnum.NEUTRAL.value
        else:
            result["sentiment"] = SentimentEnum.NEUTRAL.value
            
        # Ensure keywords is a list
        if not isinstance(result.get("keywords", []), list):
            result["keywords"] = []
            
        # Ensure generated_reply is a string and not empty
        if not result.get("generated_reply") or not isinstance(result["generated_reply"], str):
            result["generated_reply"] = "I received your email and will get back to you shortly."
            
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Error parsing response: %s", str(e))
        # Return a reasonable default response with our extracted entities
        return {
            "sentiment": "Neutral",
            "urgency": rule_based_urgency,
            "keywords": [],
            "generated_reply": "Thank you for your email. I will review and respond to your message shortly.",
            "entities": entities,
            "intent": "Other",
            "summary": subject if subject else "Email received"
        }
