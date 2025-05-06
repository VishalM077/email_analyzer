# Email Analysis API: Technical Implementation Guide

## System Architecture

The Email Analysis API is built on a modern Python stack with the following components:

- **FastAPI**: High-performance web framework for building APIs
- **Together AI**: AI model service providing language model capabilities
- **Pydantic**: Data validation and settings management
- **Uvicorn**: ASGI server for hosting the FastAPI application

### File Structure

```
├── main.py              # FastAPI application and API endpoints
├── email_agent.py       # Core email analysis logic
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (API keys)
├── Dockerfile           # Container definition
└── docker-compose.yml   # Container orchestration
```

## Installation Options

### Option 1: Direct Installation

#### Prerequisites

- Python 3.7 or higher
- Together AI API key

#### Steps

1. Clone the repository or download the source files
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your Together AI API key:
   ```
   TOGETHER_API_KEY=your_api_key_here
   ```
5. Start the server:
   ```
   uvicorn main:app --host 0.0.0.0 --port 5000
   ```

### Option 2: Docker Deployment

#### Prerequisites

- Docker and Docker Compose
- Together AI API key

#### Steps

1. Clone the repository or download the source files
2. Create a `.env` file with your Together AI API key:
   ```
   TOGETHER_API_KEY=your_api_key_here
   ```
3. Build and start the container:
   ```
   docker-compose up -d
   ```

The API will be available at `http://localhost:5000` by default.

## Key Components

### 1. Email Request Processing

The `EmailRequest` model in `main.py` validates incoming requests:

```python
class EmailRequest(BaseModel):
    email_subject: str = Field(..., min_length=1, max_length=500)
    email_body: str = Field(..., min_length=1, max_length=10000)
    sender: str = Field(...)
    recipient: Optional[str] = Field(None)
    urgency_override: Optional[str] = Field(None, pattern="^(High|Medium|Low)$")
    additional_details: Optional[Dict[str, Any]] = Field(None)
```

### 2. Entity Extraction

The system uses comprehensive regular expressions to extract structured data from email text:

```python
ENTITY_PATTERNS = {
    # ServiceNow record identifiers
    "incident_number": re.compile(r"(?:incident|ticket|case)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "change_request": re.compile(r"(?:change|CR)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "problem_number": re.compile(r"(?:problem|PR)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "task_number": re.compile(r"(?:task|TASK)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),
    "request_number": re.compile(r"(?:request|REQ)\s+(?:number|#|no|id)?\s*(?:is|:)?\s*[#]?([A-Z0-9]+)", re.IGNORECASE),

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
    "business_service": re.compile(r"(?:business|service)\s*(?:is|:)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE),
    "state": re.compile(r"(?:state|status)\s+(?:is|:)?\s*(new|in progress|pending|resolved|closed|cancelled)", re.IGNORECASE),
    "short_description": re.compile(r"(?:description|issue|problem)\s*(?:is|:)?\s*(.+?)(?=\n|$)", re.IGNORECASE),
}
```

### 3. AI Model Configuration

The system uses a primary model with a fallback option:

```python
# Primary model
model="mistralai/Mistral-7B-Instruct-v0.1"

# Fallback model
model="togethercomputer/llama-2-7b-chat"
```

### 4. Docker Configuration

The Dockerfile uses uvicorn for running the FastAPI application:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

## API Endpoints

### Main Endpoint

#### POST `/generate_reply`

Analyzes an email and returns insights with a suggested reply.

**Request Body:**

```json
{
  "email_subject": "Subject line",
  "email_body": "Email content...",
  "sender": "sender@example.com",
  "recipient": "recipient@example.com", // Optional
  "urgency_override": "High", // Optional
  "additional_details": {
    // Optional
    "customer_name": "John Doe",
    "department": "IT",
    "location": "Building A"
  }
}
```

**Success Response (200 OK):**

```json
{
  "intent": "Incident",
  "sentiment": "Negative",
  "urgency": "High",
  "keywords": ["email", "access", "client", "important", "id"],
  "summary": "Customer unable to access email and missing important client messages.",
  "entities": {
    "customer_name": "Priya",
    "user_id": "EMP9987",
    "sender_email": "priya.kapoor@company.com",
    "recipient_email": "helpdesk@company.com"
  },
  "generated_reply": "We apologize for the inconvenience. We will investigate the email access issue for your account (EMP9987) immediately."
}
```

### Additional Endpoints

#### GET `/`

Returns a simple status message indicating the API is running.

#### GET `/health`

Returns detailed health check information including a timestamp and version.

## Error Handling

The API implements comprehensive error handling:

1. **Request Validation**: Ensures all required fields are present and valid
2. **AI Service Errors**: Handles failures in the AI service connection
3. **Processing Errors**: Manages unexpected issues during email analysis
4. **Response Validation**: Ensures all response fields meet expected formats

All errors return appropriate HTTP status codes with descriptive messages.

## Logging

The system includes structured logging to track usage and troubleshoot issues:

```python
logger.info("Processing email from %s, subject: %s", email_request.sender, email_request.email_subject)
# ...
logger.info("Email processed in %.2f seconds. Intent: %s, Urgency: %s", processing_time, result.intent, result.urgency)
```

Logs include:

- Request details (sender, subject)
- Processing time
- Analysis results (intent, urgency)
- Any errors encountered

## Performance Optimization

### AI Model Selection

The system uses a primary model with a fallback option:

- Primary: "mistralai/Mistral-7B-Instruct-v0.1"
- Fallback: "togethercomputer/llama-2-7b-chat"

### Timeout Management

All AI requests include timeouts to prevent hanging connections:

```python
response = client.chat.completions.create(
    # ... other parameters ...
    timeout=30,  # 30-second timeout
)
```

## Security Considerations

1. **API Key Protection**:

   - Store Together AI API key in environment variables
   - Never commit API keys to version control
   - Rotate API keys regularly

2. **Input Validation**:

   - Validate all incoming requests
   - Sanitize email content
   - Implement rate limiting

3. **Error Handling**:
   - Don't expose internal errors to clients
   - Log errors securely
   - Implement proper error recovery

## Maintenance

### Regular Updates

1. **Dependencies**:

   - Keep all Python packages up to date
   - Test updates in a staging environment
   - Maintain a changelog

2. **Pattern Updates**:

   - Regularly review and update entity patterns
   - Add new patterns based on common use cases
   - Test pattern changes thoroughly

3. **Model Updates**:
   - Monitor AI model performance
   - Update to newer model versions when available
   - Test new models before deployment

## Troubleshooting

### Common Issues

1. **AI Service Errors**:

   - Check API key validity
   - Verify network connectivity
   - Monitor rate limits

2. **Entity Extraction Issues**:

   - Review pattern matches
   - Check for new entity formats
   - Update patterns as needed

3. **Performance Issues**:
   - Monitor response times
   - Check resource utilization
   - Review logging for bottlenecks

### Debugging Tools

1. **Logging**:

   - Enable debug logging for detailed information
   - Review error logs for patterns
   - Monitor performance metrics

2. **Testing**:
   - Use test cases for common scenarios
   - Implement automated testing
   - Maintain a test suite

## Future Enhancements

1. **Additional Entity Types**:

   - Add support for more ServiceNow fields
   - Improve pattern matching accuracy
   - Add custom entity extraction

2. **Enhanced AI Analysis**:

   - Implement multi-model analysis
   - Add sentiment analysis for specific entities
   - Improve response generation

3. **Integration Features**:
   - Add webhook support
   - Implement event-based processing
   - Add support for batch processing
