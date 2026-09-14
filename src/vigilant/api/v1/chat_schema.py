from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class FileRef(BaseModel):
    """Open WebUI's typical shape for a non-image file attachment: either
    an inline base64 data URI, or a pre-uploaded file id the backend must
    resolve against Open WebUI's own files API."""

    file_data: str | None = None
    file_id: str | None = None
    filename: str | None = None


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    file: FileRef


class ImageUrlRef(BaseModel):
    url: str


class ImagePart(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageUrlRef


ContentPart = Annotated[TextPart | FilePart | ImagePart, Field(discriminator="type")]


class ChatMessage(BaseModel):
    """A single message in a chat completion request. `content` accepts
    either plain text (legacy/simple clients) or a list of typed parts
    (Open WebUI and other multimodal-capable clients)."""

    role: str
    content: str | list[ContentPart]
