import argparse
import configparser
import logging
import os
import re

import appdirs

import tqdm
from export.dumper import logger
from export.formatters import NAME_TO_FORMATTER


class TqdmLoggingHandler(logging.Handler):
    """Redirect all logging messages through tqdm.write()"""

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.tqdm.write(msg)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def load_config(filename):
    """Load config from the specified file and return the parsed config"""
    config_dir = appdirs.user_config_dir("telegram-export")

    if not filename:
        filename = os.path.join(config_dir, "config.ini")

    if not os.path.isfile(filename):
        logger.warning(
            "No config file! Make one in {} and find an example "
            "config at https://github.com/expectocode/"
            "telegram-export/blob/master/config.ini.example."
            "Alternatively, use --config-file FILE".format(filename)
        )
        exit(1)

    defaults = {
        "SessionName": "exporter",
        "OutputDirectory": ".",
        "MediaWhitelist": "",
        "MaxSize": "1MB",
        "LogLevel": "INFO",
        "DBFileName": "export",
        "InvalidationTime": "7200",
        "ChunkSize": "100",
        "MaxChunks": "0",
        "LibraryLogLevel": "WARNING",
        "MediaFilenameFmt": "usermedia/{name}-{context_id}/{type}-{filename}",
    }

    config = configparser.ConfigParser(defaults)
    config.read(filename)

    level = config["Dumper"].get("LogLevel").upper()
    handler = TqdmLoggingHandler(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    handler.setLevel(getattr(logging, level))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level))
    level = config["Dumper"].get("LibraryLogLevel").upper()
    telethon_logger = logging.getLogger("telethon")
    telethon_logger.setLevel(getattr(logging, level))
    telethon_logger.addHandler(handler)

    config["Dumper"]["OutputDirectory"] = os.path.abspath(
        os.path.expanduser(config["Dumper"]["OutputDirectory"])
    )
    os.makedirs(config["Dumper"]["OutputDirectory"], exist_ok=True)

    config["Dumper"]["InvalidationTime"] = str(
        config["Dumper"].getint("InvalidationTime", 7200) * 60
    )

    max_size = config["Dumper"].get("MaxSize")
    m = re.match(r"(\d+(?:\.\d*)?)\s*([kmg]?b)?", max_size, re.IGNORECASE)
    if not m:
        raise ValueError("Invalid file size given for MaxSize")

    max_size = int(
        float(m.group(1))
        * {
            "B": 1024**0,
            "KB": 1024**1,
            "MB": 1024**2,
            "GB": 1024**3,
        }.get((m.group(2) or "MB").upper())
    )
    config["Dumper"]["MaxSize"] = str(max_size)
    return config


def parse_args():
    """Parse command-line arguments to the script"""
    parser = argparse.ArgumentParser(
        description="Download Telegram data (users, chats, messages, and media) into a database (and display the saved data)"
    )
    parser.add_argument(
        "--list-dialogs", action="store_true", help="list dialogs and exit"
    )

    parser.add_argument(
        "--search-dialogs",
        type=str,
        dest="search_string",
        help="like --list-dialogs but searches for a dialog " "by name/username/phone",
    )

    parser.add_argument(
        "--config-file", default=None, help="specify a config file. Default config.ini"
    )

    parser.add_argument(
        "--contexts",
        type=str,
        help="list of contexts to act on eg --contexts=12345, "
        "@username (see example config whitelist for "
        "full rules). Overrides whitelist/blacklist. "
        "The = is required when providing multiple values.",
    )

    parser.add_argument(
        "--format-contexts",
        type=int,
        nargs="+",
        help="list of contexts to format eg --format-contexts="
        "12345 -1006789. Only ContextIDs are accepted, "
        "not usernames or phone numbers.",
    )

    parser.add_argument(
        "--format",
        type=str,
        help="formats the dumped messages with the specified "
        "formatter and exits. You probably want to use "
        "this in conjunction with --format-contexts.",
        choices=NAME_TO_FORMATTER,
    )

    parser.add_argument(
        "--download-past-media",
        action="store_true",
        help="download past media instead of dumping "
        "new data (files that were seen before "
        "but not downloaded).",
    )

    parser.add_argument(
        "--proxy",
        type=str,
        dest="proxy_string",
        help="set proxy string. "
        "Examples: socks5://user:password@127.0.0.1:1080. "
        "http://localhost:8080",
    )
    return parser.parse_args()
