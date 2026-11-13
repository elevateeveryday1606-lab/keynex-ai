import os
import json
import urllib.parse
import urllib.request
import urllib.error

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Keynex AI")

INSTAGRAM_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0")


class Comment(BaseModel):
    username: str
    text: str
    likes: int = 0


class CommentRequest(BaseModel):
    comments: List[Comment]


def instagram_get(endpoint, params=None):
    if not INSTAGRAM_TOKEN:
        raise HTTPException(500, "Instagram access token is missing.")

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

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8")
        raise HTTPException(error.code, details)

    except Exception:
        raise HTTPException(502, "Could not connect to Instagram.")


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/instagram/account")
def instagram_account():
    if not INSTAGRAM_USER_ID:
        raise HTTPException(500, "Instagram User ID is missing.")

    return instagram_get(
        INSTAGRAM_USER_ID,
        {"fields": "id,username,account_type,media_count"}
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
        {"fields": "id,username"}
    )


@app.post("/select-comments")
def select_comments(data: CommentRequest):
    valid_comments = [
        comment for comment in data.comments
        if comment.text.strip()
    ]

    selected = sorted(
        valid_comments,
        key=lambda comment: comment.likes,
        reverse=True
    )

    return {
        "selected_comments": [
            comment.model_dump()
            for comment in selected[:10]
        ]
    }
