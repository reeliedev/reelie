"""
Object storage (Cloudflare R2 / S3-compatible). Holds uploaded creator videos
and generated clips. Both the API (presign uploads, build clip URLs) and the
worker (upload clips, download uploaded videos) use this.

Configured via STORAGE_* env (see config). When unconfigured, `enabled()` is
False and callers fall back to local disk (dev only).
"""

from __future__ import annotations

from app import config

_client = None


def enabled() -> bool:
    return config.STORAGE_ENABLED


def _c():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config as BotoConfig
        _client = boto3.client(
            "s3",
            endpoint_url=config.STORAGE_ENDPOINT,
            aws_access_key_id=config.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=config.STORAGE_SECRET_ACCESS_KEY,
            region_name=config.STORAGE_REGION,
            config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
        )
    return _client


def public_url(key: str) -> str:
    return f"{config.STORAGE_PUBLIC_URL}/{key.lstrip('/')}"


def presign_put(key: str, content_type: str = "application/octet-stream",
                expires: int = 3600) -> str:
    """A presigned PUT URL so the browser/app uploads a file directly to storage."""
    return _c().generate_presigned_url(
        "put_object",
        Params={"Bucket": config.STORAGE_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires)


def put_file(key: str, path: str, content_type: str | None = None) -> str:
    extra = {"ContentType": content_type} if content_type else {}
    _c().upload_file(path, config.STORAGE_BUCKET, key, ExtraArgs=extra)
    return public_url(key)


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    _c().put_object(Bucket=config.STORAGE_BUCKET, Key=key, Body=data, ContentType=content_type)
    return public_url(key)


def download_to(key: str, path: str) -> None:
    _c().download_file(config.STORAGE_BUCKET, key, path)


def exists(key: str) -> bool:
    try:
        _c().head_object(Bucket=config.STORAGE_BUCKET, Key=key)
        return True
    except Exception:
        return False
