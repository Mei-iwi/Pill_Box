"""Inspect Lab 9 alarm notifications. Sending is opt-in and requires SMTP TLS."""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage

from .db import connect, utc_now


def dispatch(path, send=False, limit=20, transport=None):
    with connect(path) as db:
        pending = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM alert_notifications WHERE status IN ('PENDING','FAILED') AND attempts<3 ORDER BY id LIMIT ?",
                (limit,),
            )
        ]
    if not send:
        return {"mode": "dry-run", "pending": len(pending), "sent": 0}
    sender = transport or smtp_send
    sent = 0
    for item in pending:
        with connect(path) as db:
            claimed = db.execute(
                "UPDATE alert_notifications SET status='SENDING',attempts=attempts+1 WHERE id=? AND status IN ('PENDING','FAILED') AND attempts<3",
                (item["id"],),
            ).rowcount
        if not claimed:
            continue
        try:
            sender(item)
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            with connect(path) as db:
                db.execute(
                    "UPDATE alert_notifications SET status='FAILED',last_error=? WHERE id=?",
                    (str(exc)[:240], item["id"]),
                )
        else:
            with connect(path) as db:
                db.execute(
                    "UPDATE alert_notifications SET status='SENT',sent_at=?,last_error=NULL WHERE id=?",
                    (utc_now(), item["id"]),
                )
            sent += 1
    return {"mode": "send", "pending": len(pending), "sent": sent}


def smtp_send(item):
    host, origin, destination = (
        os.getenv(name, "")
        for name in ("PILLBOX_SMTP_HOST", "PILLBOX_SMTP_FROM", "PILLBOX_SMTP_TO")
    )
    if not all((host, origin, destination)):
        raise ValueError("Set PILLBOX_SMTP_HOST, PILLBOX_SMTP_FROM and PILLBOX_SMTP_TO")
    port = int(os.getenv("PILLBOX_SMTP_PORT", "587"))
    user, password = (
        os.getenv("PILLBOX_SMTP_USER", ""),
        os.getenv("PILLBOX_SMTP_PASSWORD", ""),
    )
    if bool(user) != bool(password):
        raise ValueError("SMTP username and password must be configured together")
    message = EmailMessage()
    message["From"], message["To"] = origin, destination
    message["Subject"] = (
        f"Pillbox {item['device_id']} {item['transition']} {item['severity']}"
    )
    message.set_content(
        f"Hộp: {item['device_id']}\nLoại: {item['kind']}\nMức: {item['severity']}\nTrạng thái: {item['transition']}\nThời điểm: {item['created_at']}"
    )
    context = ssl.create_default_context()
    client = (
        smtplib.SMTP_SSL(host, port, timeout=5, context=context)
        if port == 465
        else smtplib.SMTP(host, port, timeout=5)
    )
    with client:
        if port != 465:
            client.starttls(context=context)
        if user:
            client.login(user, password)
        client.send_message(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="gateway/data/pillbox.db")
    parser.add_argument(
        "--send", action="store_true", help="Explicitly deliver via configured SMTP TLS"
    )
    args = parser.parse_args()
    print(dispatch(args.db, send=args.send))


if __name__ == "__main__":
    main()
