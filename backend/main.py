import os
import json
import urllib.parse
import urllib.request

from io import BytesIO
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from collections import defaultdict

from PIL import Image, UnidentifiedImageError
import pytesseract
from pytesseract import Output

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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

    params = dict(params or {})
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
    except Exception:
        raise HTTPException(
            502, "Could not connect to Instagram."
        )


def validate_reel_url(value):
    parsed = urlparse(value)

    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in (
            "instagram.com",
            "www.instagram.com"
        )
    ):
        raise HTTPException(
            400, "Please enter a valid Instagram Reel link."
        )

    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2 or parts[0] != "reel":
        raise HTTPException(
            400, "The link must be an Instagram Reel."
        )


def read_screenshot(content):
    try:
        image = Image.open(BytesIO(content))
        image.verify()

        image = Image.open(BytesIO(content)).convert("RGB")

    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            400, "Keynex could not read one of the screenshots."
        )

    try:
        data = pytesseract.image_to_data(
            image,
            output_type=Output.DICT,
            config="--psm 6"
        )

        grouped_lines = defaultdict(list)

        for i, word in enumerate(data["text"]):
            word = word.strip()

            if not word:
                continue

            key = (
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i]
            )

            grouped_lines[key].append(word)

        lines = [
            " ".join(words)
            for words in grouped_lines.values()
        ]

        full_text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        ).strip()

        return {
            "recognized_text": full_text,
            "recognized_lines": lines
        }

    except Exception:
        raise HTTPException(
            500,
            "OCR failed. Please check that Tesseract is installed."
        )


@app.get("/")
def home():
    return FileResponse(
        Path(__file__).parent / "index.html"
    )


@app.get("/instagram/account")
def instagram_account():
    if not INSTAGRAM_USER_ID:
        raise HTTPException(
            500, "Instagram User ID is missing."
        )

    return instagram_get(
        INSTAGRAM_USER_ID,
        {"fields": "id,username"}
    )


@app.get("/instagram/media")
def instagram_media():
    if not INSTAGRAM_USER_ID:
        raise HTTPException(
            500, "Instagram User ID is missing."
        )

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


@app.post("/prepare-production")
async def prepare_production(
    reel_url: str = Form(...),
    music_style: str = Form(...),
    screenshots: List[UploadFile] = File(...),
    referee_video: UploadFile = File(...)
):
    validate_reel_url(reel_url)

    if not music_style.strip():
        raise HTTPException(
            400, "Please choose a music style."
        )

    if not screenshots:
        raise HTTPException(
            400, "Please upload comment screenshots."
        )

    screenshot_results = []

    for screenshot in screenshots:
        if (
            not screenshot.content_type
            or not screenshot.content_type.startswith("image/")
        ):
            raise HTTPException(
                400, "Every comment screenshot must be an image."
            )

        content = await screenshot.read()

        if not content:
            raise HTTPException(
                400, "An uploaded screenshot is empty."
            )

        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                400, "Each screenshot must be under 15 MB."
            )

        ocr_result = read_screenshot(content)

        screenshot_results.append({
            "filename": screenshot.filename,
            "size_bytes": len(content),
            "received": True,
            "recognized_text": ocr_result["recognized_text"],
            "recognized_lines": ocr_result["recognized_lines"]
        })

    if (
        not referee_video.content_type
        or not referee_video.content_type.startswith("video/")
    ):
        raise HTTPException(
            400, "Please upload a referee video."
        )

    video_content = await referee_video.read()

    if not video_content:
        raise HTTPException(
            400, "The referee video is empty."
        )

    if len(video_content) > 100 * 1024 * 1024:
        raise HTTPException(
            400, "The referee video must be under 100 MB."
        )

    return {
        "status": "ocr_completed",
        "reel_url": reel_url,
        "music_style": music_style,
        "screenshots_received": len(screenshot_results),
        "screenshots": screenshot_results,
        "referee_video": {
            "filename": referee_video.filename,
            "size_bytes": len(video_content),
            "received": True
        },
        "next_step": "Structure the recognised text into usernames, comments and like counts."
    }


@app.post("/arrange-song")
def arrange_song(data: SongRequest):

    valid_comments = [
        comment for comment in data.comments
        if comment.text.strip()
    ]

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
