from colorlog import ColoredFormatter
import logging
from os import getenv

logger = None

def configure_logging(level = "DEBUG"):
    global logger
    if not logger:
        COLORS = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red'
        }
        formatter = ColoredFormatter(
              '%(log_color)s%(asctime)s %(levelname)5s%(reset)s - %(light_black)s%(filename)s:%(lineno)d %(funcName)s%(reset)s - %(log_color)s%(message)s%(reset)s',
              datefmt='%H:%M:%S',
              reset=True,
              log_colors=COLORS
        )
        # Stream handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger= logging.getLogger(__name__)
        logger.addHandler(stream_handler)
        logger.setLevel(level)
    return logger
