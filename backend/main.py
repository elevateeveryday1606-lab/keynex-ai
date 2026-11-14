import os
import json
import urllib.parse
import urllib.request

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Keynex AI")


INSTAGRAM_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0")


class Comment(BaseModel):
    username: str
    text: str
    comment_url: Optional[str] = None


class SongRequest(BaseModel):
    reel_url: str
    comments: List[Comment]


def instagram_get(endpoint, params=None):
    if not INSTAGRAM_TOKEN:
        raise HTTPException(
            500, "Instagram access token is missing."
        )

    params = params or {}
    params["access_token"] = INSTAGRAM_TOKEN

    url = (
        f"https://graph.facebook.com/{API_VERSION}/"
        f"{endpoint}?"
        f"{urllib.parse.urlencode(params)}"
    )

    request = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except Exception as error:
        raise HTTPException(
            502, "Could not connect to Instagram."
        )


@app.get("/")
def home():
    return FileResponse(
        Path(__file__).parent / "index.html"
    )


@app.get("/instagram/account")
def instagram_account():
    if not INSTAGRAM_USER_ID:
        raise HTTPException(500, "Instagram User ID is missing.")

    return instagram_get(
        INSTAGRAM_USER_ID,
        {"fields": "id,username"}
    )


@app.get("/instagram/media")
def instagram_media():
    if not INSTAGRAM_USER_ID:
        raise HTTPException(500, "Instagram User ID is missing.")

    return instagram_get(
        f"{INSTAGRAM_USER_ID}/media",
        {
            "fields": "id,caption,media_type,permalink,timestamp",
            "limit": 25
        }
    )


@app.get("/instagram/media/{media_id}/comments")
def instagram_comments(media_id: str):
    return instagram_get(
        f"{media_id}/comments",
        {
            "fields": "id,text,username,timestamp,like_count",
            "limit": 100
        }
    )


@app.post("/arrange-song")
def arrange_song(data: SongRequest):

    valid_comments = [
        comment for comment in data.comments
        if comment.text.strip()
    ]

    # Preserve the submitted order and exact comment wording.
    sections = [
        ("Intro", 1),
        ("Verse 1", 4),
        ("Chorus", 2),
        ("Verse 2", 4),
        ("Bridge", 2),
        ("Outro", 1000)
    ]

    song_sections = []
    position = 0

    for section_name, maximum in sections:
        if position >= len(valid_comments):
            break

        section_comments = valid_comments[
            position:position + maximum
        ]

        if section_comments:
            song_sections.append({
                "section": section_name,
                "comments": [
                    comment.model_dump()
                    for comment in section_comments
                ]
            })

        position += len(section_comments)

    return {
        "reel_url": data.reel_url,
        "song_sections": song_sections,
        "total_comments": len(valid_comments),
        "wording_preserved": True
    }
