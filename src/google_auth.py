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


def get_credentials(credentials_parent_dir, client_secret_dir=None):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    credential_dir = os.path.join(credentials_parent_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'n0tb0t-credentials.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        if client_secret_dir is not None:
            client_secret_path = os.path.join(client_secret_dir, CLIENT_SECRET_FILE)
        else:
            client_secret_path = CLIENT_SECRET_FILE
        flow = client.flow_from_clientsecrets(client_secret_path, SCOPES)
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
        pageSize=1000, fields="nextPageToken, files(id, name, trashed)").execute()
    items = results.get('files', [])
    found = False
    if not items:
        print('No files found.')
    else:
        for item in items:
            if item["name"] == filename and item["trashed"] is False:
                file_id = item["id"]
                found = True
                print("Found: {}".format(filename))
                break

    if not found:
        print("Creating: {}".format(filename))
        files_body = {
          'mimeType': 'application/vnd.google-apps.spreadsheet',
          'name': filename,
        }
        service.files().create(body=files_body).execute(http=http)

        results = service.files().list(
                pageSize=1000, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])
        for item in items:
            if item["name"] == filename:
                file_id = item["id"]
                print("Found: {}".format(filename))
                break
        permissions_body = {
            'role': 'reader',
            'type': 'anyone'
        }
        service.permissions().create(fileId=file_id, body=permissions_body).execute(http=http)

    return found, file_id

if __name__ == '__main__':
    from inspect import getsourcefile
    current_path = os.path.abspath(getsourcefile(lambda: 0))
    current_dir = os.path.dirname(current_path)
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    my_credentials = get_credentials(credentials_parent_dir=parent_dir, client_secret_dir=parent_dir)
    print(ensure_file_exists(my_credentials, 'google test'))
