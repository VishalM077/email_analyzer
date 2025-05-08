import os
import re
import json
import logging
from typing import Dict, Any, Optional
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

def clean_json_response(content: str) -> str:
    """
    Removes Markdown-style code block from the model's response and cleans the JSON.
    """
    # If the output starts with ``` and ends with ```, strip them
    if content.startswith("```") and content.endswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)  # remove ```json or ```
        content = content.rstrip("`").rstrip()  # remove trailing backticks
    
    # Try to find JSON object in the response if not properly formatted
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    
    # Clean control characters and normalize newlines
    content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)  # remove control characters
    content = content.replace('\r\n', '\n').replace('\r', '\n')  # normalize newlines
    
    # Ensure the content is a valid JSON string
    try:
        # First try to parse as is
        json.loads(content)
    except json.JSONDecodeError:
        # If that fails, try to extract just the generated_reply field
        reply_match = re.search(r'"generated_reply"\s*:\s*"([^"]*)"', content)
        if reply_match:
            content = f'{{"generated_reply": "{reply_match.group(1)}"}}'
        else:
            # If all else fails, return a default response
            content = '{"generated_reply": "Thank you for your email. I will review and respond to your message shortly."}'
    
    return content.strip()

def analyze_email_content(text: str) -> dict:
    """
    Analyzes email content using LLM to determine sentiment, intent, urgency, keywords,
    and extract entities
    """
    # Prepare the prompt for the LLM
    prompt = f"""You are an AI assistant that analyzes email content and extracts structured information for downstream processing in a ServiceNow ITSM environment.

Analyze the following email and return a JSON object with only the information that is clearly present or confidently inferable from the content. Do not guess or invent values. If a field is not mentioned or implied, do not include it.

EMAIL:
\"\"\"
{text}
\"\"\"

Return a JSON object with any of the following **top-level keys** and a nested **entities** dictionary:

---

### TOP-LEVEL KEYS:

- "category": Classify the sender as either:
  - "customer" — if the sender is an end user requesting help, reporting an issue, or giving feedback.
  - "agent" — if the sender is a support staff providing an update, resolution, or internal communication.

- "intent": One of:
  - "report_issue"
  - "request_support"
  - "provide_update"
  - "confirm_resolution"
  - "escalation"
  - "follow_up"
  - "request_information"
  - "share_information"
  - "complaint"
  - "feedback"
  - "other"

- "urgency": One of:
  - "low"
  - "medium"
  - "high"

- "sentiment": One of:
  - "positive"
  - "neutral"
  - "negative"

- "keywords": A list of up to 10 important and relevant terms or phrases from the email.

---

### ENTITIES (if present, include under a key called "entities"):

The "entities" dictionary should contain **only the fields that are clearly present or implied** in the email. Each field is explained below:

#### Ticket and Record Information
- "record_type": The kind of record mentioned in the email, such as:
  - "incident" (for outage or break/fix issues)
  - "case" (customer service case)
  - "request" (a general request for service)
  - "request_item" (a specific item under a request, usually prefixed with RITM)
  - "change_request" (a formal request to change a system or configuration)
  - "ticket" (a generic term — try to infer type if possible)
- "record_number": The unique ID of the record, such as INC0012345, RITM0004567, CHG0001234, CS0005678.
- "record_table": The system table name for lookup, such as:
  - "incident"
  - "sn_customerservice_case"
  - "sc_request"
  - "sc_req_item"
  - "change_request"

#### Contact and User Info
- "reporter_name": Name of the sender of email
- "sender_email": Sender’s email address
- "recipient_email": Recipient’s email address
- "company_name": Organization or customer name
- "location": Any physical or organizational location (e.g., New York, Floor 3, HR department)

#### Issue and Context
- "issue": Description of the reported problem or request
- "product": Product name or model mentioned (e.g., Dell XPS, SAP, Outlook)
- "service": Service referenced (e.g., payroll, email, VPN)
- "ci_name": Configuration item (specific system or hardware being discussed)
- "category": Business category of the issue (e.g., Hardware, Software, Access)
- "sub_category": More specific sub-classification (e.g., Laptop, VPN, Login)
- "error_code": Any numeric or string error code mentioned in the email

#### Action History & Status
- "resolution": Any solution or workaround mentioned by the sender
- "status_request": If the sender is asking for an update or the current state
- "next_steps": Any action requested or expected to be taken next
- "action_taken": Troubleshooting or steps already performed by the sender

#### Workflow & External References
- "order_id": If the email references a specific order or purchase
- "date_time": Any time or date explicitly mentioned
- "reason": The cause or explanation for an issue or delay
- "has_attachments": Boolean value (true/false) if the email mentions an attachment
- "reference_links": Any URLs or hyperlinks included or mentioned in the email

---

### FINAL INSTRUCTIONS:

Return only a properly formatted JSON object. Do not include keys that are not confidently extractable. Do not include nulls or empty fields. Infer intent, urgency, and sentiment only if clearly implied by the text.
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
        )
        logger.info("Successfully used Llama-3.3-70B-Instruct-Turbo model")
    except Exception as e:
        logger.error("Model failed: %s", str(e))
        return {
            "category": "Customer",
            "intent": "other",
            "urgency": "medium",
            "sentiment": "neutral",
            "keywords": [],
            "entities": {}
        }

    content = response.choices[0].message.content.strip()
    logger.info("Raw model output:\n%s", content)

    try:
        cleaned = clean_json_response(content)
        logger.debug("Cleaned JSON: %s", cleaned)

        result = json.loads(cleaned)
        
        # Validate the result has all required fields
        expected_keys = ["category", "intent", "urgency", "sentiment", "keywords", "entities"]
        if not all(key in result for key in expected_keys):
            missing_keys = [key for key in expected_keys if key not in result]
            logger.warning("Missing expected keys in LLM response: %s", str(missing_keys))
            # Add any missing keys with default values
            if "category" not in result:
                result["category"] = "Customer"
            if "intent" not in result:
                result["intent"] = "other"
            if "urgency" not in result:
                result["urgency"] = "medium"
            if "sentiment" not in result:
                result["sentiment"] = "neutral"
            if "keywords" not in result:
                result["keywords"] = []
            if "entities" not in result:
                result["entities"] = {}
            
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Error parsing response: %s", str(e))
        return {
            "category": "Customer",
            "intent": "other",
            "urgency": "medium",
            "sentiment": "neutral",
            "keywords": [],
            "entities": {}
        }

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
    result = analyze_email_content(full_email_content)
    
    return result

def analyze_email(email_text: str) -> dict:
    """
    Analyzes email content and generates an appropriate reply
    """
    # Prepare the prompt for the LLM
    prompt = f"""Analyze this email and generate an appropriate reply:

{email_text}

Please provide a JSON response with the following structure:
{{
    "generated_reply": "Your suggested reply to the email, properly formatted with line breaks for clarity."
}}

CRITICAL INSTRUCTIONS:
1. If the "details_provided" section contains resolution information:
    - Acknowledge the original issue.
    - Inform the user that the issue has been resolved.
    - Suggest next steps for verification.
    - Reference specific details from the original email (e.g., printer model, error codes, etc.).
    - Ensure the reply is formatted with clear line breaks between the sections for readability.
    
2. If no resolution is provided:
    - Acknowledge the issue and indicate it will be investigated.
    - Reference specific details from the email.
    - Suggest temporary workarounds if mentioned.
    - Ensure the reply is formatted with clear line breaks between the sections for readability.

3. Always:
    - Be professional and helpful in tone.
    - Reference specific details from the email.
    - Keep the reply concise but informative.
    - Use proper formatting with line breaks between sections to enhance readability.

Example with resolution:
Input: 
{{
  "email_content": "Dear IT Support,\n\nWe are currently facing a problem with the network printer in our office. Employees on the 2nd floor are unable to print documents as the printer displays an error message: 'Printer Offline'. This issue started around 11:30 AM today and is affecting about 6 employees in our Marketing team. The printer model is Canon imageCLASS MF733Cdw, and it is connected to the network.\n\nActions taken so far:\n- Checked the printer's network connection\n- Restarted the printer\n- Attempted to print from multiple computers\n\nDespite these efforts, the printer remains offline and employees are unable to print. We suspect there may be an issue with the network settings or printer drivers.\n\nRequest:\nCould you please investigate this issue and provide assistance? If possible, we would appreciate a temporary workaround until it is fully resolved.\n\nBest regards,\nJohn Doe\nMarketing Manager\njohn.doe@company.com\nExt: 1452",
  "details_provided": {{
    "resolution": "The issue was resolved at 1:15 PM"
  }}
}}

Output: {{
  "generated_reply": "Dear John,\n\nThank you for reaching out regarding the network printer issue in your office. I'm pleased to inform you that the issue was resolved at 1:15 PM today.\n\nThe Canon imageCLASS MF733Cdw printer should now be operating normally, and all employees on the 2nd floor should be able to print documents without encountering the 'Printer Offline' error.\n\nPlease verify that the printer is functioning as expected and let us know if you experience any further issues or if there's anything else we can assist with.\n\nBest regards,\nIT Support Team"
}}

Example without resolution:
Output: {{
  "generated_reply": "Dear John,\n\nThank you for bringing the network printer issue to our attention. We understand that the Canon imageCLASS MF733Cdw printer is showing a 'Printer Offline' error and is affecting employees on the 2nd floor.\n\nWe will investigate the issue further to identify the cause of the 'Printer Offline' error. In the meantime, please ensure that the printer is properly connected to the network and check if there are any pending print jobs in the queue.\n\nWe will keep you updated on our progress and provide additional guidance if needed.\n\nBest regards,\nIT Support Team"
}}"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
        )
        logger.info("Successfully used Llama-3.3-70B-Instruct-Turbo model")
    except Exception as e:
        logger.error("Model failed: %s", str(e))
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
