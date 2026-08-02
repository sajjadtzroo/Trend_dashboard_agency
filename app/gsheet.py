"""Read the configured Google Sheet tab via a service account -> list of rows.

Creds resolution (first that's set): GOOGLE_SA_JSON_B64 (prod, CLI-safe) ->
GOOGLE_SA_JSON (raw) -> GOOGLE_SA_FILE (local path).
"""
import base64
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import (GSHEET_ID, GSHEET_TAB, GOOGLE_SA_JSON_B64,
                     GOOGLE_SA_JSON, GOOGLE_SA_FILE)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _creds():
    if GOOGLE_SA_JSON_B64:
        info = json.loads(base64.b64decode(GOOGLE_SA_JSON_B64))
        return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    if GOOGLE_SA_JSON:
        return service_account.Credentials.from_service_account_info(json.loads(GOOGLE_SA_JSON), scopes=_SCOPES)
    if GOOGLE_SA_FILE:
        return service_account.Credentials.from_service_account_file(GOOGLE_SA_FILE, scopes=_SCOPES)
    raise RuntimeError("Google Sheets not configured (set GOOGLE_SA_JSON_B64 / GOOGLE_SA_JSON / GOOGLE_SA_FILE)")


def fetch_rows() -> list[list]:
    """Return the tab's cell grid as a list of rows (list of str), including the
    banner/header rows — matches the Sales-Funnel CSV layout the importer expects."""
    if not GSHEET_ID:
        raise RuntimeError("GSHEET_ID not set")
    svc = build("sheets", "v4", credentials=_creds(), cache_discovery=False)
    resp = svc.spreadsheets().values().get(spreadsheetId=GSHEET_ID, range=f"'{GSHEET_TAB}'").execute()
    return resp.get("values", [])
