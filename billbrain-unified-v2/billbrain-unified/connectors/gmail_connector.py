import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import Config

class GmailConnector:
    def __init__(self):
        self.creds = self._authenticate()
        self.service = build('gmail', 'v1', credentials=self.creds)

    def _authenticate(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', Config.GMAIL_SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', Config.GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def fetch_potential_bills(self, limit=20):
        """Fetches latest emails that haven't been processed by BillBrain."""
        # Query: Look for emails without our custom label
        query = "-label:BillBrain-Processed" 
        
        results = self.service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
        messages = results.get('messages', [])
        
        extracted_data = []
        for msg in messages:
            # Fetch the full message detail
            full_msg = self.service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = full_msg.get('payload', {})
            headers = payload.get('headers', [])

            # --- 1. Extract Headers ---
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")

            # --- 2. Extract Body ---
            body = ""
            if 'parts' in payload:
                # Multipart message: look for text/plain
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
            elif 'body' in payload and 'data' in payload['body']:
                # Single part message
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

            extracted_data.append({
                "external_id": msg['id'],
                "subject": subject,
                "sender": sender,
                "body": body
            })
            
        return extracted_data
        

    def mark_as_processed(self, msg_id):
        """Applies a label to the email in Gmail so we don't fetch it again."""
        label_name = "BillBrain-Processed"
        
        # 1. Ensure the label exists
        labels = self.service.users().labels().list(userId='me').execute().get('labels', [])
        label_id = next((l['id'] for l in labels if l['name'] == label_name), None)
        
        if not label_id:
            label_body = {'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
            label_id = self.service.users().labels().create(userId='me', body=label_body).execute()['id']

        # 2. Add the label to the message
        # Just add the label, don't remove anything
        self.service.users().messages().batchModify(
            userId='me',
            body={'ids': [msg_id], 'addLabelIds': [label_id], 'removeLabelIds': []} 
        ).execute()

if __name__ == "__main__":
    # Test fetch
    connector = GmailConnector()
    bills = connector.fetch_potential_bills(limit=3)
    for b in bills:
        print(f"Found: {b['subject']} from {b['sender']}")