import logging
import os
from logging.handlers import QueueListener
from ui import insert_log

std_logger = None
ql = None
debug_global = False


def logger():
    global std_logger
    if std_logger is None:
        init_logger(False)
    return std_logger


def init_logger(debug=False):
    global std_logger
    global debug_global
    debug_global = debug
    log_dir_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "log")
    if not os.path.exists(log_dir_path):
        os.mkdir(log_dir_path)
    # Init handlers
    err_file_handler = logging.FileHandler(filename=os.path.join(log_dir_path, "error.log"), mode="a")
    std_file_handler = logging.FileHandler(filename=os.path.join(log_dir_path, "3seas.log"), mode="a")
    # filter to appropriate levels
    std_file_handler.addFilter(StdFilter(debug=debug))
    std_file_handler.setLevel(logging.DEBUG)
    err_file_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter(fmt="%(asctime)s - [%(levelname)s]: %(message)s")
    std_file_handler.setFormatter(formatter)
    err_file_handler.setFormatter(formatter)
    std_logger = logging.getLogger("3-Seas Logger")
    std_logger.addHandler(err_file_handler)
    std_logger.addHandler(std_file_handler)
    std_logger.setLevel(logging.DEBUG)


def setup_interactive_logging():
    global debug_global
    ui_handler = UIHandler(logging.DEBUG if debug_global else logging.INFO)
    ui_handler.setFormatter(logging.Formatter(fmt="%(asctime)s [%(levelname)s]: %(message)s", datefmt="%H:%M:%S"))
    logger().addHandler(ui_handler)


class StdFilter(logging.Filter):
    def __init__(self, name="", debug=False):
        logging.Filter.__init__(self, name)
        self.debug = debug

    def filter(self, record):
        return logging.ERROR > record.levelno >= (logging.DEBUG if self.debug else logging.INFO)


class UIHandler(logging.Handler):
    def __init__(self, level=logging.INFO):
        logging.Handler.__init__(self, level)

    def emit(self, record):
        msg = self.format(record)
        try:
            insert_log(msg)
        except Exception:
            pass


def init_notif_server(queue):
    global ql
    ql = QueueListener(queue, *logger().handlers)
    ql.start()
    logger().debug("GDrive notification queue listening...")


def stop_notif_server():
    global ql
    ql.stop()
    logger().debug("GDrive notification queue halted.")
