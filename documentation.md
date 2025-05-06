# Email Analysis API Documentation

## Overview

The Email Analysis API is an intelligent system that automatically analyzes emails and provides valuable insights about their content. Using advanced AI and comprehensive pattern matching, the system can understand email context, extract important information, and generate appropriate responses. It is specifically designed to handle various types of ServiceNow emails including incidents, requests, problems, and changes.

## Key Features

- **Intent Detection**: Identifies the primary purpose of an email (Incident, Request, Question, Information, Change, Problem, etc.)
- **Sentiment Analysis**: Determines if the email tone is Positive, Neutral, or Negative
- **Urgency Assessment**: Classifies emails as High, Medium, or Low urgency using comprehensive keyword matching
- **Keyword Extraction**: Identifies up to 5 key topics from the email content
- **Entity Recognition**: Automatically detects and extracts important information like:
  - ServiceNow record numbers (Incidents, Changes, Problems, Tasks, Requests)
  - User information (IDs, usernames, contact details)
  - Technical details (Error codes, IP addresses, MAC addresses)
  - Time and date information
  - Location and organizational details
  - ServiceNow specific fields (Priority, Category, Assignment Group, etc.)
- **Smart Summarization**: Creates brief summaries of email content (25 words or less)
- **Response Generation**: Creates appropriate reply templates based on email content

## How It Works

The system combines rule-based processing with advanced AI language models to analyze emails:

1. **Text Processing**: Initial analysis using comprehensive keywords and patterns to identify:
   - Urgency levels
   - Intent classification
   - Entity extraction
2. **AI Analysis**: Deep content analysis using Together AI's language models:
   - Primary Model: mistralai/Mistral-7B-Instruct-v0.1
   - Fallback Model: togethercomputer/llama-2-7b-chat
3. **Response Generation**: Creation of contextually appropriate reply templates

## Using the API

### Basic Request

To analyze an email, send a POST request to the `/generate_reply` endpoint with the following JSON structure:

```json
{
  "email_subject": "Your email subject line",
  "email_body": "The main content of the email...",
  "sender": "sender@example.com",
  "recipient": "recipient@example.com", // Optional
  "urgency_override": "High", // Optional: can be "High", "Medium", or "Low"
  "additional_details": {
    // Optional: Additional context for ServiceNow ticket creation
    "customer_name": "John Doe",
    "department": "IT",
    "location": "Building A"
  }
}
```

### Example Request

```json
{
  "email_subject": "Cannot Access Email - Urgent",
  "email_body": "Hi,\n\nMy email has stopped working since this morning. I'm missing important client messages. My ID is EMP9987.\n\nPlease resolve this ASAP.\n\nThanks,\nPriya Kapoor",
  "sender": "priya.kapoor@company.com",
  "recipient": "helpdesk@company.com",
  "urgency_override": "High",
  "additional_details": {
    "customer_name": "Priya"
  }
}
```

### Example Response

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

## Understanding the Response

Each response contains the following information:

| Field             | Description                                    | Example                                                |
| ----------------- | ---------------------------------------------- | ------------------------------------------------------ |
| `intent`          | Primary purpose of the email                   | "Incident", "Request", "Question", "Change", "Problem" |
| `sentiment`       | Overall tone of the email                      | "Positive", "Neutral", "Negative"                      |
| `urgency`         | How time-sensitive the email appears to be     | "High", "Medium", "Low"                                |
| `keywords`        | Up to 5 main topics from the content           | ["email", "access", "client", "id"]                    |
| `summary`         | Brief summary of the email content             | "Customer unable to access email"                      |
| `entities`        | Important information extracted from the email | User IDs, error codes, locations, etc.                 |
| `generated_reply` | A suggested response to the email              | "We apologize for the inconvenience..."                |

## Use Cases

### ServiceNow Integration

- Automatically create and categorize ServiceNow tickets
- Extract relevant information for ticket fields
- Generate appropriate responses based on ticket type
- Handle various ServiceNow record types:
  - Incidents
  - Change Requests
  - Problem Records
  - Service Requests
  - Tasks

### Email Management

- Automatically categorize and tag incoming emails
- Create intelligent email routing rules
- Generate quick response templates for common requests
- Prioritize emails based on urgency and impact

### Data Collection

- Extract structured data from unstructured email content
- Gather metrics on common issues and requests
- Track sentiment trends over time
- Monitor service quality and response times

## API Endpoints

| Endpoint          | Method | Description                          |
| ----------------- | ------ | ------------------------------------ |
| `/`               | GET    | Health check endpoint                |
| `/health`         | GET    | Detailed health check with timestamp |
| `/generate_reply` | POST   | Analyze email and generate reply     |

## Technical Notes

- **Response Time**: Typical analysis takes 2-5 seconds per email
- **Rate Limits**: For optimal performance, limit to 10 requests per minute
- **Maximums**:
  - Email subject: 500 characters
  - Email body: 10,000 characters
  - Additional details: No strict limit, but keep reasonable

## Integration Tips

### Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Request successful
- `400 Bad Request`: Invalid parameters (e.g., incorrect urgency_override value)
- `500 Internal Server Error`: Server-side processing error

Always implement error handling in your integration to manage these scenarios gracefully.

### Field Validation

- `email_subject`: Required, 1-500 characters
- `email_body`: Required, 1-10,000 characters
- `sender`: Required
- `recipient`: Optional
- `urgency_override`: Optional, must be "High", "Medium", or "Low"
- `additional_details`: Optional, dictionary of key-value pairs

## Example Integration Code

### Python

```python
import requests

api_url = "http://your-server:5000/generate_reply"

email_data = {
    "email_subject": "Bug in CRM System",
    "email_body": "Hi Support Team,\n\nWhile updating customer records in the CRM, the system crashes. Error code: ERR_5009. This happens consistently when adding notes.\n\nPlease investigate.\n\nThanks,\nMichael",
    "sender": "michael@company.com",
    "recipient": "crm.support@company.com",
    "urgency_override": "Medium",
    "additional_details": {
        "customer_name": "Michael"
    }
}

response = requests.post(api_url, json=email_data)
analysis = response.json()

print(f"Email Intent: {analysis['intent']}")
print(f"Extracted Error Code: {analysis['entities'].get('error_code')}")
print(f"Suggested Reply: {analysis['generated_reply']}")
```

### JavaScript

```javascript
async function analyzeEmail() {
  const response = await fetch("http://your-server:5000/generate_reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email_subject: "Bug in CRM System",
      email_body:
        "Hi Support Team,\n\nWhile updating customer records in the CRM, the system crashes. Error code: ERR_5009. This happens consistently when adding notes.\n\nPlease investigate.\n\nThanks,\nMichael",
      sender: "michael@company.com",
      recipient: "crm.support@company.com",
      urgency_override: "Medium",
      additional_details: {
        customer_name: "Michael",
      },
    }),
  });

  const analysis = await response.json();
  console.log("Email summary:", analysis.summary);
  console.log("Extracted entities:", analysis.entities);
  console.log("Suggested reply:", analysis.generated_reply);
}
```

## Support

For any questions or issues with the Email Analysis API, please contact your system administrator or IT support team.
