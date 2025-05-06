import requests
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any, List, Optional
from email_agent import analyze_email, SentimentEnum, UrgencyEnum, IntentEnum
import logging
import time

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

# Define the request model with validation
class EmailRequest(BaseModel):
    email_subject: str = Field(..., min_length=1, max_length=500, description="The subject line of the email")
    email_body: str = Field(..., min_length=1, max_length=10000, description="The main content of the email")
    sender: str = Field(..., description="Email address or name of the sender")
    recipient: Optional[str] = Field(None, description="Email address or name of the recipient")
    additional_details: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional additional context for ServiceNow ticket creation"
    )

# Define the response model with enhanced fields
class EmailResponse(BaseModel):
    intent: str
    sentiment: str
    urgency: str
    keywords: List[str]
    summary: str
    entities: Dict[str, Any]
    generated_reply: str

@app.get("/")
async def root():
    return {"message": "Email Analysis API is running. Send POST requests to /generate_reply"}

@app.get("/health")
async def health_check():
    """Health check endpoint to verify the service is running correctly"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

@app.post("/generate_reply", response_model=EmailResponse, status_code=status.HTTP_200_OK)
async def generate_reply(email_request: EmailRequest):
    """
    Analyzes an email and generates a suggested reply based on its content.
    
    The analysis includes:
    - Intent detection (question, request, etc.)
    - Sentiment analysis
    - Urgency assessment
    - Keyword extraction
    - Entity recognition (dates, order numbers, etc.)
    - Email summarization
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

        # Use the enhanced analyzer
        analysis = analyze_email(email_text, additional_details=email_request.additional_details, request_data=request_data)

        # Extract and normalize the response content
        response_content = analysis.get("generated_reply", "Could not generate a reply.")
        
        # Ensure response_content is a string, if it's a dict, extract the body
        if isinstance(response_content, dict):
            response_content = response_content.get("body", str(response_content))

        # Return properly structured response with all the enhanced fields
        result = EmailResponse(
            intent=analysis.get("intent", "Other"),
            sentiment=analysis.get("sentiment", "Neutral"),
            urgency=analysis.get("urgency", "Medium"),
            keywords=analysis.get("keywords", [])[:5],  # Limit to max 5 keywords
            summary=analysis.get("summary", ""),
            entities=analysis.get("entities", {}),
            generated_reply=response_content
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Email processed in {processing_time:.2f} seconds. Intent: {result.intent}, Urgency: {result.urgency}")
        
        return result
    except KeyError as e:
        logger.error(f"Missing expected key: {str(e)}")
        # Handling missing keys in the analysis response
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Missing expected key: {str(e)}")
    except ValueError as e:
        logger.error(f"Invalid response structure: {str(e)}")
        # Handling malformed response
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Invalid response structure: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        # General error handling
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing the request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Email Analysis API server")
    uvicorn.run(app, host="0.0.0.0", port=5000)
