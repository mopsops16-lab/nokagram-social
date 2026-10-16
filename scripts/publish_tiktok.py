#!/usr/bin/env python3
"""Upload a rendered short to TikTok via the Content Posting API (Direct Post).

IMPORTANT: TikTok requires your app to pass an audit for public posting.
Until then every post is forced to SELF_ONLY (private). See README.

Required env:
  TIKTOK_ACCESS_TOKEN   OAuth token with scope video.publish
Optional:
  TIKTOK_PRIVACY        PUBLIC_TO_EVERYONE|MUTUAL_FOLLOW_FRIENDS|SELF_ONLY
                        (default: SELF_ONLY)
"""

import argparse
import json
import os
import sys
import time

import requests

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
MAX_CHUNK = 64 * 1024 * 1024


def init_upload(token, title, size, privacy):
    body = {
        "post_info": {
            "title": title[:2200],
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": min(size, MAX_CHUNK),
            "total_chunk_count": (size + MAX_CHUNK - 1) // MAX_CHUNK,
        },
    }
    r = requests.post(
        INIT_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=body,
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise SystemExit(f"tiktok init error: {data}")
    return data["data"]["publish_id"], data["data"]["upload_url"]


def put_file(upload_url, path, size):
    with open(path, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(MAX_CHUNK)
            end = offset + len(chunk) - 1
            r = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end}/{size}",
                },
                data=chunk,
                timeout=300,
            )
            r.raise_for_status()
            offset = end + 1


def poll(token, publish_id, tries=20):
    for _ in range(tries):
        r = requests.post(
            STATUS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        state = data.get("status")
        print("status:", state)
        if state in ("PUBLISH_COMPLETE", "FAILED"):
            return state
        time.sleep(6)
    return "TIMEOUT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True, help="path to out/<id>.json")
    args = ap.parse_args()

    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("missing TIKTOK_ACCESS_TOKEN (needs audited app)")

    with open(args.meta, encoding="utf-8") as f:
        meta = json.load(f)

    video = meta["file"]
    size = os.path.getsize(video)
    privacy = os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY")
    title = meta["title"]

    publish_id, upload_url = init_upload(token, title, size, privacy)
    print("publish_id:", publish_id, "privacy:", privacy)
    put_file(upload_url, video, size)
    print("upload done, polling...")
    state = poll(token, publish_id)
    print(f"result: {state}")
    if state != "PUBLISH_COMPLETE":
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
