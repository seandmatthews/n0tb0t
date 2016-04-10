from __future__ import print_function
import httplib2
import os

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

# If modifying these scopes, delete your previously saved credentials
SCOPES = 'https://www.googleapis.com/auth/drive.file https://spreadsheets.google.com/feeds'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'n0tb0t'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    credential_dir = os.path.join(cur_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'n0tb0t-credentials.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def ensure_file_exists(credentials, filename):
    """
    Checks to see if a file exists in a users google drive.
    If it doesn't exist, creates the file.

    Only checks the first thousand files,
    because I don't want to mess with next page tokens.
    """

    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    results = service.files().list(
        pageSize=1000, fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        print('No files found.')
        found = False
    else:
        found = False
        for item in items:
            if item['name'] == filename:
                found = True
                print("Found: {}".format(filename))
                break

    if not found:
        print("Creating: {}".format(filename))
        body = {
          'mimeType': 'application/vnd.google-apps.spreadsheet',
          'name': filename,
        }
        service.files().create(body=body).execute(http=http)

    return bool(found)

if __name__ == '__main__':
    credentials = get_credentials()
    print(ensure_file_exists(credentials, 'google test'))