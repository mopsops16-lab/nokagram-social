#!/usr/bin/env python3
"""Upload a rendered short to YouTube (Shorts = vertical <=3min).

Required env (GitHub secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Optional:
  YT_PRIVACY   public|unlisted|private   (default: public)
  YT_PUBLISH_AT  RFC3339 e.g. 2026-01-01T09:00:00Z  (schedules the upload)
"""

import argparse
import json
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN_URI = "https://oauth2.googleapis.com/token"
CATEGORY_ID = "28"  # Science & Technology


def client():
    cid = os.environ.get("YT_CLIENT_ID")
    secret = os.environ.get("YT_CLIENT_SECRET")
    refresh = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        raise SystemExit(
            "missing YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN"
        )
    creds = Credentials(
        None,
        refresh_token=refresh,
        token_uri=TOKEN_URI,
        client_id=cid,
        client_secret=secret,
    )
    return build("youtube", "v3", credentials=creds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True, help="path to out/<id>.json")
    args = ap.parse_args()

    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)

    video = meta["file"]
    if not os.path.exists(video):
        raise SystemExit(f"video not found: {video}")

    privacy = os.environ.get("YT_PRIVACY", "public")
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    publish_at = os.environ.get("YT_PUBLISH_AT")
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:4900],
            "tags": meta.get("tags", [])[:500],
            "categoryId": CATEGORY_ID,
        },
        "status": status,
    }

    yt = client()
    media = MediaFileUpload(video, mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = req.next_chunk()
    vid = response["id"]
    print(f"uploaded: https://youtu.be/{vid}  (privacy={status['privacyStatus']})")


if __name__ == "__main__":
    sys.exit(main())
