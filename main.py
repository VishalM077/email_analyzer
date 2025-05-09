import requests
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any, List, Optional
from email_agent import analyze_email, extract_entities
import logging
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("email_api.log")
    ]
)

logger = logging.getLogger("email_analysis_api")

app = FastAPI(
    title="Email Analysis API",
    description="An API that analyzes emails and extracts key information using Together AI LLMs",
    version="1.0.0",
)

# Define the request models with validation
class EmailRequest(BaseModel):
    email_subject: str = Field(..., min_length=1, max_length=500, description="The subject line of the email")
    email_body: str = Field(..., min_length=1, max_length=10000, description="The main content of the email")
    sender: str = Field(..., description="Email address or name of the sender")
    recipient: Optional[str] = Field(None, description="Email address or name of the recipient")
    additional_details: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional additional context for ServiceNow ticket creation"
    )

class EmailContentRequest(BaseModel):
    email_content: str = Field(..., min_length=1, max_length=10500, description="The complete email content including subject and body")
    details_provided: Optional[Dict[str, Any]] = Field(None, description="Optional additional details to include in the reply")

# Define the response models with enhanced fields
class EntityExtractionResponse(BaseModel):
    category: str
    intent: str
    urgency: str
    sentiment: str
    keywords: List[str]
    entities: Dict[str, Any]

class ReplyGenerationResponse(BaseModel):
    generated_reply: str

@app.get("/")
async def root():
    return {"message": "Email Analysis API is running. Send POST requests to /extract_entities or /generate_reply"}

@app.get("/health")
async def health_check():
    """Health check endpoint to verify the service is running correctly"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

@app.post("/extract_entities", response_model=EntityExtractionResponse, status_code=status.HTTP_200_OK)
async def extract_entities_endpoint(email_request: EmailRequest):
    """
    Analyzes an email and extracts entities, intent, sentiment, urgency, and keywords.
    
    The analysis includes:
    - Category detection (Customer/Agent)
    - Intent detection (report_issue, request_support, etc.)
    - Sentiment analysis (positive, neutral, negative, stressed, angry)
    - Urgency assessment (low, medium, high, critical)
    - Keyword extraction
    - Entity recognition (dates, order numbers, etc.)
    """
    try:
        start_time = time.time()
        logger.info(f"Processing email from {email_request.sender}, subject: {email_request.email_subject}")
        
        # Construct full email content
        email_text = f"Email Subject: {email_request.email_subject}\n\n Email Body: {email_request.email_body}"

        # Convert request to dict for passing to analyze_email
        request_data = {
            "email_subject": email_request.email_subject,
            "email_body": email_request.email_body,
            "sender": email_request.sender,
            "recipient": email_request.recipient,
            "additional_details": email_request.additional_details
        }

        # Extract entities and basic analysis
        analysis = extract_entities(email_text, additional_details=email_request.additional_details, request_data=request_data)
        
        # Return properly structured response with all the enhanced fields
        result = EntityExtractionResponse(
            category=analysis.get("category", "Customer"),
            intent=analysis.get("intent", "other"),
            sentiment=analysis.get("sentiment", "neutral"),
            urgency=analysis.get("urgency", "medium"),
            keywords=analysis.get("keywords", [])[:10],  # Limit to max 10 keywords
            entities=analysis.get("entities", {})
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Email processed in {processing_time:.2f} seconds. Category: {result.category}, Intent: {result.intent}, Urgency: {result.urgency}")
        
        return result
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing the request: {str(e)}")

@app.post("/generate_reply", response_model=ReplyGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_reply_endpoint(email_content: EmailContentRequest):
    """
    Generates a reply based on the email content and optional details.
    
    The reply generation:
    - Acknowledges the specific issue
    - References any incident numbers
    - Includes provided details if available
    - Indicates investigation will occur
    - Uses information already available
    """
    try:
        start_time = time.time()
        logger.info("Generating reply for email content")
        
        # Prepare the full content for the LLM with clear separation
        full_content = f"""Email Content:
{email_content.email_content}

Additional Details:
{json.dumps(email_content.details_provided, indent=2) if email_content.details_provided else "No additional details provided"}"""
        
        # Generate reply using the full content
        analysis = analyze_email(full_content)
        
        # Extract and normalize the response content
        response_content = analysis.get("generated_reply", "Could not generate a reply.")
        
        # Ensure response_content is a string, if it's a dict, extract the body
        if isinstance(response_content, dict):
            response_content = response_content.get("body", str(response_content))
        
        result = ReplyGenerationResponse(
            generated_reply=response_content
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Reply generated in {processing_time:.2f} seconds")
        
        return result
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating reply: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Email Analysis API server")
    uvicorn.run(app, host="0.0.0.0", port=5000)
