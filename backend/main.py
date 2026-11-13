
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Keynex AI")

class Comment(BaseModel):
    username: str
    text: str
    likes: int = 0

class CommentRequest(BaseModel):
    comments: List[Comment]

@app.get("/")
def home():
    return FileResponse(
        Path(__file__).parent / "index.html"
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
