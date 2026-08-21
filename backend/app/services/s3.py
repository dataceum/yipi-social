"""
Thin wrapper around boto3 S3 for issuing presigned upload URLs for user
media (profile pictures, voice bio recordings).

Credentials: boto3's default credential chain is used, so in production
(ECS) this picks up the task's IAM role automatically — no keys are baked
into the image or task definition. settings.AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY are only ever read here for local development
against a real bucket; leave them unset in every real environment and the
client below falls straight through to the task role.

Note on size limits: a plain presigned PUT URL (what this module issues)
does not itself enforce a max upload size — that requires a presigned POST
with a content-length-range policy condition instead. We intentionally
keep this simpler PUT-based flow and enforce the size limit client-side
(see media.py's max_size_mb in the response) plus an S3 bucket lifecycle
rule as a backstop. This is a known, documented simplification — tighten
it to presigned POST + policy conditions if that gap matters for your
threat model.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings


@lru_cache
def _s3_client():
    kwargs = {
        "region_name": settings.AWS_REGION,
        # Force SigV4 + virtual-hosted-style addressing so presigned URLs
        # work uniformly across regions, including ones that don't
        # support the legacy SigV2 signer.
        "config": BotoConfig(signature_version="s3v4"),
    }
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def build_object_key(*, kind: str, user_id: int, file_extension: str) -> str:
    """
    Namespace uploads by kind and owner so a bucket lifecycle rule or IAM
    policy could scope by prefix later, and so keys never collide across
    users. The random UUID segment means re-uploading never overwrites a
    prior asset (and never needs a cache-busting query string on read).
    """
    prefix = {
        "profile_picture": "profile-pictures",
        "bio_recording": "bio-recordings",
    }[kind]
    return f"{prefix}/{user_id}/{uuid.uuid4().hex}.{file_extension.lstrip('.')}"


def presign_put(*, key: str, content_type: str) -> str:
    """
    A presigned PUT URL the client uploads directly to — the file bytes
    never pass through this API process. The URL is bound to both the
    exact key and Content-Type; the client's PUT request must send the
    same Content-Type header or S3 will reject the signature.
    """
    return _s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_MEDIA_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.MEDIA_UPLOAD_URL_EXPIRE_SECONDS,
    )


def public_asset_url(key: str) -> str:
    """
    Build the URL clients should store (via PATCH /users/{id}) and read
    from after upload. Prefers CloudFront — the bucket itself blocks all
    public access per README.md's OAC architecture — and only falls back
    to a raw S3 URL when no CloudFront domain is configured yet, which is
    only usable against a bucket that still allows public reads (local/dev
    bring-up before CloudFront exists).
    """
    if settings.CLOUDFRONT_MEDIA_DOMAIN:
        return f"https://{settings.CLOUDFRONT_MEDIA_DOMAIN}/{key}"
    return f"https://{settings.S3_MEDIA_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
