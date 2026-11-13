
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="Keynex AI",
    description="Turn social media comments into songs."
)

class Comment(BaseModel):
    username: str
    text: str
    likes: int = 0

class CommentRequest(BaseModel):
    comments: List[Comment]

@app.get("/")
def home():
    return {"message": "Welcome to Keynex AI!"}

@app.post("/select-comments")
def select_comments(data: CommentRequest):
    selected = sorted(
        data.comments,
        key=lambda comment: comment.likes,
        reverse=True
    )

    return {
        "selected_comments": [
            comment.model_dump()
            for comment in selected[:10]
        ]
    }
