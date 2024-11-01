#!/usr/bin/env python3
"""The main telegram-export script.
Handles arguments and config, then calls the Exporter.
"""
import asyncio
import difflib
import logging
import os
from contextlib import suppress

from telethon import TelegramClient, utils

from export.dumper import Dumper
from export.exporter import Exporter
from export.formatters import NAME_TO_FORMATTER
from export.main_stuff import parse_args, load_config
from export.utils import parse_proxy_str

logger = logging.getLogger("")


NO_USERNAME = "<no username>"


def fmt_dialog(dialog, id_pad=0, username_pad=0):
    """
    Space-fill a row with given padding values
    to ensure alignment when printing dialogs.
    """
    username = getattr(dialog.entity, "username", None)
    username = "@" + username if username else NO_USERNAME
    return "{:<{id_pad}} | {:<{username_pad}} | {}".format(
        utils.get_peer_id(dialog.entity),
        username,
        dialog.name,
        id_pad=id_pad,
        username_pad=username_pad,
    )


def find_fmt_dialog_padding(dialogs):
    """
    Find the correct amount of space padding
    to give dialogs when printing them.
    """
    no_username = NO_USERNAME[:-1]
    return (
        max(len(str(utils.get_peer_id(dialog.entity))) for dialog in dialogs),
        max(
            len(getattr(dialog.entity, "username", no_username) or no_username)
            for dialog in dialogs
        )
        + 1,
    )


def find_dialog(dialogs, query, top=25, threshold=0.7):
    """
    Iterate through dialogs and return, sorted,
    the best matches for a given query.
    """
    seq = difflib.SequenceMatcher(b=query, autojunk=False)
    scores = []
    for index, dialog in enumerate(dialogs):
        seq.set_seq1(dialog.name)
        name_score = seq.ratio()
        if query.lower() in dialog.name.lower():
            boost = (index / len(dialogs)) / 25
            name_score = max(name_score, 0.75 + boost)
        if getattr(dialog.entity, "username", None):
            seq.set_seq1(dialog.entity.username)
            username_score = seq.ratio()
        else:
            username_score = 0
        if getattr(dialog.entity, "phone", None):
            seq.set_seq1(dialog.entity.phone)
            phone_score = seq.ratio()
        else:
            phone_score = 0

        scores.append((dialog, max(name_score, username_score, phone_score)))
    scores.sort(key=lambda t: t[1], reverse=True)
    matches = tuple(score[0] for score in scores if score[1] > threshold)
    num_not_shown = 0 if len(matches) <= top else len(matches) - top
    return matches[:top], num_not_shown


async def list_or_search_dialogs(args, client):
    """List the user's dialogs and/or search them for a query"""
    dialogs = (await client.get_dialogs(limit=None))[::-1]
    if args.list_dialogs:
        id_pad, username_pad = find_fmt_dialog_padding(dialogs)
        for dialog in dialogs:
            print(fmt_dialog(dialog, id_pad, username_pad))

    if args.search_string:
        print('Searching for "{}"...'.format(args.search_string))
        found, num_not_shown = find_dialog(dialogs, args.search_string)
        if not found:
            print('Found no good results with "{}".'.format(args.search_string))
        elif len(found) == 1:
            print("Top match:", fmt_dialog(found[0]), sep="\n")
        else:
            if num_not_shown > 0:
                print(
                    "Showing top {} matches of {}:".format(
                        len(found), len(found) + num_not_shown
                    )
                )
            else:
                print("Showing top {} matches:".format(len(found)))
            id_pad, username_pad = find_fmt_dialog_padding(found)
            for dialog in found:
                print(fmt_dialog(dialog, id_pad, username_pad))

    await client.disconnect()


async def main(loop):
    """
    The main telegram-export program. Goes through the
    configured dialogs and dumps them into the database.
    """
    args = parse_args()
    config = load_config(args.config_file)
    dumper = Dumper(config["Dumper"])

    if args.contexts:
        dumper.config["Whitelist"] = args.contexts

    if args.format:
        formatter = NAME_TO_FORMATTER[args.format](dumper.conn)
        fmt_contexts = args.format_contexts or formatter.iter_context_ids()
        for cid in fmt_contexts:
            formatter.format(cid, config["Dumper"]["OutputDirectory"])
        return

    proxy = args.proxy_string or dumper.config.get("Proxy")
    if proxy:
        proxy = parse_proxy_str(proxy)

    absolute_session_name = os.path.join(
        config["Dumper"]["OutputDirectory"], config["TelegramAPI"]["SessionName"]
    )
    if config.has_option("TelegramAPI", "SecondFactorPassword"):
        client = await TelegramClient(
            absolute_session_name,
            config["TelegramAPI"]["ApiId"],
            config["TelegramAPI"]["ApiHash"],
            loop=loop,
            proxy=proxy,
        ).start(
            config["TelegramAPI"]["PhoneNumber"],
            password=config["TelegramAPI"]["SecondFactorPassword"],
        )
    else:
        client = await TelegramClient(
            absolute_session_name,
            config["TelegramAPI"]["ApiId"],
            config["TelegramAPI"]["ApiHash"],
            loop=loop,
            proxy=proxy,
        ).start(config["TelegramAPI"]["PhoneNumber"])

    if args.list_dialogs or args.search_string:
        return await list_or_search_dialogs(args, client)

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


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        ret = loop.run_until_complete(main(loop)) or 0
    except KeyboardInterrupt:
        ret = 1
    for task in asyncio.Task.all_tasks():
        task.cancel()
        if hasattr(task._coro, "__name__") and task._coro.__name__ == "main":
            continue
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
    loop.stop()
    loop.close()
    exit(ret)
