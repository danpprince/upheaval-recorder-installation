import base64
from datetime import datetime
from email.mime.text import MIMEText
import httplib2
import pickle
import os
import time

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = ['https://www.googleapis.com/auth/gmail.send', 
          'https://www.googleapis.com/auth/drive.readonly']
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'upheaval notifier'

UPDATE_PERIOD = 5 # min

def CreateMessage(sender, to, subject, message_text):
    """Create a message for an email.

    Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

    Returns:
    An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_string())}

def SendMessage(service, user_id, message):
    """Send an email message.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

    Returns:
    Sent Message.
    """
    try:
        message = (service.users().messages().send(userId=user_id, body=message).execute())
        print('Message Id: {}'.format(message['id']))
        return message
    except Exception as e:
        print('An error occurred: %s' % e)

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'gmail-python-quickstart.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def main():
    sender = 'danpprince@gmail.com'
    to     = ', '.join(['danpprince@gmail.com', 'mpuckett2@udayton.edu'])

    previous_files = []
    with open('upheaval_files.pkl', 'r') as f:
        previous_files = pickle.load(f)

    while True:
        print('Running at ' + str(datetime.now()))

        # Get the files currently in the Drive folder
        query_str = "'0B4BZrYisXMkDMzdpNGo1OW1CTmM' in parents"
        try:
            credentials = get_credentials()
            http = credentials.authorize(httplib2.Http())
            gmail_service = discovery.build('gmail', 'v1', http=http)
            drive_service = discovery.build('drive', 'v3', http=http)

            results = drive_service.files().list(q=query_str, pageSize=100).execute()
            items = results.get('files', [])
        except Exception as e:
            print('Error getting new files: ' + str(e))
            time.sleep(UPDATE_PERIOD * 60)
            continue

        if not items:
            print('No files found.')
        else:
            print('Files found:')
            for item in items:
                print('{}'.format(item['name']))

        current_files = set([item['name'] for item in items])

        # Compare the files currently in the Drive folder with the previous ones
        diff_files = current_files - set(previous_files)

        if diff_files:
            subject = str(len(diff_files)) + ' new UPHEAVAL recordings'

            files_str = ''
            for f in diff_files:
                files_str = files_str + str(f) + '\n'

            message_text = 'New files in the upheaval folder:\n' + files_str
            msg = CreateMessage(sender, to, subject, message_text)
            print('sending message: {}'.format(files_str))

            msg = SendMessage(gmail_service, 'me', msg)
            print('sent message')

            # Save the new file list
            with open('upheaval_files.pkl', 'w') as f:
                pickle.dump(current_files, f)

            previous_files = current_files

        time.sleep(UPDATE_PERIOD * 60)

if __name__ == '__main__':
    main()
