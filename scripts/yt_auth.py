#!/usr/bin/env python3
"""One-time local helper: obtain a YouTube refresh token.

Prereqs:
  1. Google Cloud project -> enable "YouTube Data API v3".
  2. OAuth consent screen -> add yourself as test user
     (or publish the app; while in "testing" refresh tokens expire in ~7 days).
  3. Create OAuth client id of type "Desktop app".
  4. pip install google-auth-oauthlib

Run:
  set YT_CLIENT_ID=...      (PowerShell: $env:YT_CLIENT_ID="...")
  set YT_CLIENT_SECRET=...
  python scripts/yt_auth.py

It opens a browser, you approve, and it prints the refresh token to paste into
the YT_REFRESH_TOKEN GitHub secret.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    cid = os.environ.get("YT_CLIENT_ID")
    secret = os.environ.get("YT_CLIENT_SECRET")
    if not (cid and secret):
        raise SystemExit("set YT_CLIENT_ID and YT_CLIENT_SECRET first")

    client_config = {
        "installed": {
            "client_id": cid,
            "client_secret": secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n=== add these GitHub secrets ===")
    print("YT_CLIENT_ID     =", cid)
    print("YT_CLIENT_SECRET =", secret)
    print("YT_REFRESH_TOKEN =", creds.refresh_token)


if __name__ == "__main__":
    sys.exit(main())
