"""Firestore client for the cabinet monitor.

Speaks the same REST API, with the same anonymous auth and the same nursery
code, as the web app's js/sync.js - the Pi is just another device on the
nursery. Two documents:

  nurseries/<code>        the shared nursery. The Pi NEVER overwrites it:
                          it pulls, merges its sensor entries in with the
                          exact semantics store.js uses (by id, newest
                          updatedAt wins, tombstones respected), and pushes
                          the merged whole back. test_pi.py proves the
                          Python merge and the JS merge agree byte-for-byte
                          on who wins.

  nurseries/<code>-live   a small document the Pi owns outright: current
                          air, per-plant moisture, relay states, chill.
                          The app renders it as the Live sensors card.
                          Same collection, so the existing security rules
                          already cover it.
"""

from __future__ import annotations

import json
import time

import requests

AUTH_BASE = "https://identitytoolkit.googleapis.com"
FIRESTORE_BASE = "https://firestore.googleapis.com"
SIZE_WARN_BYTES = 800 * 1024   # the app warns here too; the hard ceiling is 1 MiB


class Cloud:
    def __init__(self, config):
        self.project_id = config["projectId"]
        self.api_key = config["apiKey"]
        self.code = config["code"]
        self.auth_base = config.get("authBase", AUTH_BASE)
        self.firestore_base = config.get("firestoreBase", FIRESTORE_BASE)
        self._token = None
        self._token_expiry = 0

    # ------------------------------------------------------------- auth

    def token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        response = requests.post(
            "%s/v1/accounts:signUp?key=%s" % (self.auth_base, self.api_key),
            json={"returnSecureToken": True},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["idToken"]
        self._token_expiry = time.time() + int(payload.get("expiresIn", 3600))
        return self._token

    def _doc_url(self, suffix=""):
        return "%s/v1/projects/%s/databases/(default)/documents/nurseries/%s%s" % (
            self.firestore_base, self.project_id, self.code, suffix)

    # -------------------------------------------------------- documents

    def fetch_nursery(self):
        response = requests.get(
            self._doc_url(),
            headers={"Authorization": "Bearer " + self.token()},
            timeout=30,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        raw = response.json().get("fields", {}).get("data", {}).get("stringValue")
        return json.loads(raw) if raw else None

    def push_nursery(self, snapshot):
        body = json.dumps(snapshot, separators=(",", ":"))
        if len(body) > SIZE_WARN_BYTES:
            raise RuntimeError(
                "Nursery document is %d KB, close to Firestore's 1 MB ceiling. "
                "Export a backup from the app and trim old readings." % (len(body) // 1024))
        response = requests.patch(
            self._doc_url(),
            headers={"Authorization": "Bearer " + self.token()},
            json={"fields": {
                "data": {"stringValue": body},
                "updatedAt": {"stringValue": now_iso()},
            }},
            timeout=30,
        )
        response.raise_for_status()

    def push_live(self, live):
        response = requests.patch(
            self._doc_url("-live"),
            headers={"Authorization": "Bearer " + self.token()},
            json={"fields": {
                "data": {"stringValue": json.dumps(live, separators=(",", ":"))},
            }},
            timeout=30,
        )
        response.raise_for_status()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".000Z"


# ---------------------------------------------------------------- merge

def _stamp(record):
    return record.get("updatedAt") or record.get("createdAt") or ""


def merge_lists(mine, theirs):
    """Port of store.js mergeLists: by id, the newest write wins, and
    tombstoned records take part like any other version."""
    by_id = {}
    order = []

    def absorb(record):
        if not record or not record.get("id"):
            return
        existing = by_id.get(record["id"])
        if existing is None:
            by_id[record["id"]] = record
            order.append(record["id"])
        elif _stamp(record) > _stamp(existing):
            by_id[record["id"]] = record

    for record in mine:
        absorb(record)
    for record in theirs:
        absorb(record)
    return [by_id[i] for i in order]


def merge_snapshot(base, incoming):
    """Port of store.js mergeSnapshot, minus the localStorage side effects."""
    base = base or {"version": 1, "plants": [], "entries": [], "completions": []}
    return {
        "version": 1,
        "plants": merge_lists(base.get("plants", []), incoming.get("plants", [])),
        "entries": merge_lists(base.get("entries", []), incoming.get("entries", [])),
        "completions": merge_lists(base.get("completions", []),
                                   incoming.get("completions", [])),
    }


def merge_entries_into(snapshot, entries):
    """Fold the daemon's sensor entries into a fetched nursery snapshot."""
    return merge_snapshot(snapshot, {"plants": [], "entries": entries, "completions": []})
