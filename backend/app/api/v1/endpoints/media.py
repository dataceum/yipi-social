"""
Presigned-upload endpoints for user media (profile pictures, voice bio
recordings — see Profile.profile_picture_url / Profile.bio_recording_url
in app/models/profile.py).

The actual file bytes never pass through this API: the client requests a
presigned S3 URL here, PUTs the file directly to S3 with it, then saves
the returned asset_url onto their own profile via the existing
PATCH /users/{id} endpoint. This keeps large uploads (photos, audio) off
the FastAPI process entirely, matching the S3 + CloudFront (OAC)
architecture described in README.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.services import s3

media_router = APIRouter(prefix="/media", tags=["Media"])

# kind -> {content_type: file_extension}. Deliberately an allowlist, not a
# blocklist — anything not explicitly listed here is rejected.
_ALLOWED_CONTENT_TYPES: dict[str, dict[str, str]] = {
    "profile_picture": {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    },
    "bio_recording": {
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
        "audio/wav": "wav",
    },
}

# Advisory only — enforced client-side, not by the presigned URL itself.
# See the size-limit note in app/services/s3.py.
_MAX_SIZE_MB: dict[str, int] = {
    "profile_picture": 5,
    "bio_recording": 10,
}


class UploadUrlRequest(SQLModel):
    kind: str  # "profile_picture" | "bio_recording"
    content_type: str


class UploadUrlResponse(SQLModel):
    upload_url: str
    method: str = "PUT"
    # The client's PUT request must include exactly these headers, or S3
    # will reject the presigned signature.
    headers: dict[str, str]
    asset_url: str
    max_size_mb: int
    expires_in: int


@media_router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    summary="Get a presigned S3 URL to upload a profile picture or bio recording",
)
async def create_upload_url(
    payload: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
) -> UploadUrlResponse:
    if not settings.S3_MEDIA_BUCKET:
        # Fails loudly instead of silently generating a URL against an
        # empty bucket name — a clear signal during deploy that
        # S3_MEDIA_BUCKET was never set for this environment.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media uploads are not configured on this server.",
        )

    allowed = _ALLOWED_CONTENT_TYPES.get(payload.kind)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kind must be 'profile_picture' or 'bio_recording'.",
        )

    extension = allowed.get(payload.content_type)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported content_type '{payload.content_type}' for {payload.kind}. "
                f"Allowed: {', '.join(allowed)}."
            ),
        )

    key = s3.build_object_key(
        kind=payload.kind, user_id=current_user.id, file_extension=extension
    )
    upload_url = s3.presign_put(key=key, content_type=payload.content_type)

    return UploadUrlResponse(
        upload_url=upload_url,
        headers={"Content-Type": payload.content_type},
        asset_url=s3.public_asset_url(key),
        max_size_mb=_MAX_SIZE_MB[payload.kind],
        expires_in=settings.MEDIA_UPLOAD_URL_EXPIRE_SECONDS,
    )
