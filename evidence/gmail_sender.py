"""
PROVCHAIN — Gmail Sender
========================
Dispatches legal notices using the Gmail API.
"""

import os
import base64
import logging
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger("provchain.gmail_sender")

# Scopes required to send emails
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def get_gmail_service():
    """
    Authenticates and returns the Gmail API service instance.
    Uses credentials.json and token.json from the path specified in settings.
    """
    from core.config import get_settings
    settings = get_settings()
    
    creds = None
    if os.path.exists(settings.GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(settings.GMAIL_TOKEN_PATH, SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(settings.GMAIL_CREDENTIALS_PATH):
                logger.warning(
                    f"Gmail {settings.GMAIL_CREDENTIALS_PATH} not found. "
                    "Email dispatch will be disabled. Download from GCP Console."
                )
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GMAIL_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(settings.GMAIL_TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service


def send_notice_email(to_email: str, subject: str, body: str) -> bool:
    """
    Sends the generated legal notice email via Gmail API.
    
    Args:
        to_email: Platform's abuse contact email.
        subject: Email subject.
        body: The generated legal notice body.
        
    Returns:
        True if sent successfully, False otherwise.
    """
    service = get_gmail_service()
    if not service:
        return False
        
    try:
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to_email
        message['From'] = 'me'  # 'me' implies the authenticated user
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        logger.info(f"Email sent successfully. Message Id: {send_message['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email via Gmail API: {e}")
        return False
