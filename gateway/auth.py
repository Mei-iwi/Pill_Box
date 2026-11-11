"""Optional, server-configured bearer identities for the local prototype.

No credentials are shipped. Use HTTPS before exposing bearer tokens remotely.
"""

import json
import os
import secrets

from flask import g, jsonify, request

from .db import connect


def configure_auth(app, test_config):
    identities = (test_config or {}).get("AUTH_IDENTITIES")
    if identities is None and os.getenv("PILLBOX_AUTH_FILE"):
        with open(os.environ["PILLBOX_AUTH_FILE"], encoding="utf-8") as source:
            identities = json.load(source)
    if identities is not None:
        if not isinstance(identities, dict) or not identities:
            raise ValueError("Auth identities must be a nonempty token mapping")
        for token, identity in identities.items():
            if (
                len(token) < 24
                or token.startswith("REPLACE_")
                or identity.get("role") not in ("family", "nurse", "admin")
                or not isinstance(identity.get("actor_id"), str)
                or not isinstance(identity.get("devices"), list)
            ):
                raise ValueError("Invalid configured auth identity")
    app.config["AUTH_IDENTITIES"] = identities
    if os.getenv("PILLBOX_DEPLOYMENT") == "care" and identities is None:
        raise ValueError("care deployment requires PILLBOX_AUTH_FILE")

    @app.before_request
    def authorize():
        g.identity = None
        if not request.path.startswith("/api/") or identities is None:
            return None
        authorization = request.headers.get("Authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        g.identity = next(
            (
                identity
                for known, identity in identities.items()
                if secrets.compare_digest(token.encode(), known.encode())
            ),
            None,
        )
        if g.identity is None:
            return jsonify(error="authentication required"), 401
        identity = g.identity
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(error="JSON object required"), 400
        role = identity["role"]
        if request.path.startswith("/api/refill") and role not in ("nurse", "admin"):
            return jsonify(error="caregiver role required"), 403
        if (
            request.method == "POST"
            and request.path.endswith("/commands")
            and role not in ("nurse", "admin")
        ):
            return jsonify(error="caregiver role required"), 403
        if body.get("command") == "UPDATE_SCHEDULE" and role != "admin":
            return jsonify(error="admin role required"), 403
        device = (request.view_args or {}).get("device_id") or body.get("box_id")
        if request.path in (
            "/api/refill/confirm",
            "/api/refill/authorize",
            "/api/refill/end",
        ) and body.get("verification_id"):
            if not isinstance(body["verification_id"], str):
                return jsonify(error="invalid verification ID"), 400
            with connect(app.config["DB_PATH"]) as db:
                row = db.execute(
                    "SELECT box_id FROM refill_verifications WHERE verification_id=?",
                    (body["verification_id"],),
                ).fetchone()
                device = row["box_id"] if row else None
        if device and role != "admin" and device not in identity["devices"]:
            return jsonify(error="device not assigned to identity"), 403


def scoped(records, key):
    if g.identity is None or g.identity["role"] == "admin":
        return records
    return [record for record in records if record[key] in g.identity["devices"]]


def actor(body):
    return g.identity["actor_id"] if g.identity else body.get("actor_id")
