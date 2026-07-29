"""Chat attachment schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AttachmentKind = Literal["image", "text", "pdf"]


class ChatAttachmentResponse(BaseModel):
    """Metadata returned after upload / list."""

    id: str
    kind: AttachmentKind
    originalFilename: str
    mimeType: str
    sizeBytes: int
    width: int | None = None
    height: int | None = None
    thumbnailUrl: str | None = None
    url: str | None = None
    createdAt: datetime


class ChatAttachmentContentPart(BaseModel):
    """Internal helper for building model content parts."""

    kind: AttachmentKind
    originalFilename: str
    mimeType: str
    storagePath: str
    extractedText: str | None = None
