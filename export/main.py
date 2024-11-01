#!/usr/bin/env python3
"""The main telegram-export script.
Handles arguments and config, then calls the Exporter.
"""
import asyncio

from telethon import TelegramClient

from export.dumper import Dumper
from export.exporter import Exporter
from export.main_stuff import load_config, parse_args


async def main(loop):
    """
    The main telegram-export program. Goes through the
    configured dialogs and dumps them into the database.
    """
    args = parse_args()
    config = load_config(args.config_file)
    dumper = Dumper(config["Dumper"])

    exporter = Exporter(client, config, dumper, loop)
    try:
        if args.download_past_media:
            await exporter.download_past_media()
        else:
            await exporter.start()
    except asyncio.CancelledError:
        pass
    finally:
        await exporter.close()

    exporter.logger.info("Finished!")
    return asyncio.all_tasks()


client = TelegramClient("me", 24641509, "0837c48fa58ac670cd37836e17fbebd7")
with client:
    loop = asyncio.get_event_loop()
    try:
        ret = loop.run_until_complete(main(loop)) or 0
    except KeyboardInterrupt:
        ret = 1
