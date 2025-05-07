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
    - Communication details"""

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
