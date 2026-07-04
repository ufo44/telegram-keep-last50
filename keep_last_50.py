import argparse
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime

from telethon import TelegramClient, errors


DEFAULT_CHANNEL = "@bknovosti"
DEFAULT_KEEP = 50


def log_line(session: str, message: str) -> None:
    text = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(text, flush=True)
    Path(session).with_suffix(".log").open("a", encoding="utf-8").write(text + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all Telegram channel messages except the latest N messages."
    )
    parser.add_argument("--api-id", default=os.getenv("TG_API_ID"))
    parser.add_argument(
        "--api-hash",
        default=os.getenv("TG_API_HASH"),
    )
    parser.add_argument("--channel", default=os.getenv("TG_CHANNEL", DEFAULT_CHANNEL))
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--max-delete",
        type=int,
        default=0,
        help="Stop after deleting/selecting this many old messages. 0 means no limit.",
    )
    parser.add_argument("--progress-every", type=int, default=500)
    parser.add_argument(
        "--show-selected",
        action="store_true",
        help="Print IDs and basic info for selected old messages.",
    )
    parser.add_argument("--phone", default=os.getenv("TG_PHONE"))
    parser.add_argument("--code", default=os.getenv("TG_CODE"))
    parser.add_argument("--password", default=os.getenv("TG_PASSWORD"))
    parser.add_argument(
        "--send-code",
        action="store_true",
        help="Send a Telegram login code to --phone and save temporary auth state.",
    )
    parser.add_argument(
        "--session",
        default=str(Path(__file__).with_name("telegram_cleanup")),
        help="Telethon session path without .session suffix.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete messages. Without this flag, the script only previews.",
    )
    return parser.parse_args()


def state_path(session: str) -> Path:
    return Path(session).with_suffix(".auth_state.json")


async def ensure_login(client: TelegramClient, args: argparse.Namespace) -> None:
    if await client.is_user_authorized():
        log_line(args.session, "Already authorized.")
        return

    if args.send_code:
        if not args.phone:
            raise SystemExit("--phone is required with --send-code")
        log_line(args.session, f"Sending login code to {args.phone}.")
        sent = await client.send_code_request(args.phone)
        state_path(args.session).write_text(
            json.dumps(
                {"phone": args.phone, "phone_code_hash": sent.phone_code_hash},
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise SystemExit("Login code sent. Re-run with --code CODE to finish login.")

    auth_state_file = state_path(args.session)
    if not args.code:
        raise SystemExit(
            "No Telegram session yet. First run with --phone +79991234567 --send-code, "
            "then re-run with --code 12345."
        )

    if not auth_state_file.exists():
        raise SystemExit("Missing auth state. Run --phone ... --send-code first.")

    auth_state = json.loads(auth_state_file.read_text(encoding="utf-8"))
    phone = auth_state["phone"]
    phone_code_hash = auth_state["phone_code_hash"]

    try:
        log_line(args.session, "Signing in with Telegram login code.")
        await client.sign_in(
            phone=phone,
            code=args.code,
            phone_code_hash=phone_code_hash,
        )
    except errors.SessionPasswordNeededError:
        if not args.password:
            raise SystemExit("Telegram account requires 2FA password. Re-run with --password.")
        log_line(args.session, "Signing in with Telegram 2FA password.")
        await client.sign_in(password=args.password)
    finally:
        if await client.is_user_authorized() and auth_state_file.exists():
            auth_state_file.unlink()


async def main() -> None:
    args = parse_args()
    if args.keep < 0:
        raise SystemExit("--keep must be 0 or greater")
    if not args.api_id:
        raise SystemExit("--api-id or TG_API_ID is required")
    if not args.api_hash:
        raise SystemExit("--api-hash or TG_API_HASH is required")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be 1 or greater")
    if args.progress_every < 1:
        raise SystemExit("--progress-every must be 1 or greater")
    if args.max_delete < 0:
        raise SystemExit("--max-delete must be 0 or greater")

    client = TelegramClient(args.session, int(args.api_id), args.api_hash)

    log_line(args.session, "Connecting to Telegram.")
    await client.connect()
    try:
        await ensure_login(client, args)
        log_line(args.session, f"Resolving channel {args.channel}.")
        entity = await client.get_entity(args.channel)
        log_line(args.session, "Reading messages.")

        kept_ids = []
        pending_delete_ids = []
        scanned = 0
        selected_for_deletion = 0
        deleted = 0
        skipped_system = 0

        async for message in client.iter_messages(entity):
            scanned += 1
            if type(message.action).__name__ == "MessageActionChannelCreate":
                skipped_system += 1
                if args.show_selected:
                    log_line(
                        args.session,
                        f"Skipped undeletable channel-create service message id={message.id}.",
                    )
                continue

            if len(kept_ids) < args.keep:
                kept_ids.append(message.id)
            else:
                if args.max_delete and selected_for_deletion >= args.max_delete:
                    break

                selected_for_deletion += 1
                pending_delete_ids.append(message.id)
                if args.show_selected:
                    log_line(
                        args.session,
                        "Selected old message "
                        f"id={message.id} date={message.date} "
                        f"action={type(message.action).__name__ if message.action else '-'}",
                    )

                if args.execute and len(pending_delete_ids) >= args.batch_size:
                    await client.delete_messages(entity, pending_delete_ids)
                    deleted += len(pending_delete_ids)
                    pending_delete_ids.clear()
                    print(
                        f"Scanned {scanned}; deleted {deleted} old messages...",
                        flush=True,
                    )
                    log_line(args.session, f"Deleted {deleted} old messages so far.")

            if scanned % args.progress_every == 0 and not args.execute:
                print(
                    f"Scanned {scanned}; selected {selected_for_deletion} old messages...",
                    flush=True,
                )

        stopped_by_limit = bool(args.max_delete and selected_for_deletion >= args.max_delete)

        print(f"Channel: {args.channel}")
        print(f"Scanned messages: {scanned}")
        print(f"Keeping latest: {len(kept_ids)}")
        print(f"Skipped system channel-create messages: {skipped_system}")
        print(f"Messages selected for deletion: {selected_for_deletion}")
        if stopped_by_limit:
            print(f"Stopped after --max-delete {args.max_delete}. Run again for next batch.")

        if kept_ids:
            print(f"Newest kept id: {max(kept_ids)}")
            print(f"Oldest kept id: {min(kept_ids)}")

        if not selected_for_deletion:
            print("Nothing to delete.")
            return

        if not args.execute:
            print("Dry run only. Re-run with --execute to delete selected messages.")
            return

        if pending_delete_ids:
            await client.delete_messages(entity, pending_delete_ids)
            deleted += len(pending_delete_ids)

        print(f"Done. Deleted {deleted} messages.")
        log_line(args.session, f"Done. Deleted {deleted} messages.")
    finally:
        log_line(args.session, "Disconnecting.")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
