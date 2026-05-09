from __future__ import annotations

import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_MAGIC_BYTES: dict[bytes, str] = {
    b"%PDF": "application/pdf",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def validate_file_bytes(content: bytes, declared_type: str) -> bool:
    for magic, mime in _MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime == declared_type
    return False


class EvidenceRepository:
    def __init__(self, settings):
        self._bucket = settings.s3_bucket_name
        self._prefix = settings.s3_evidence_prefix
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def _make_key(self, payment_id: str, filename: str) -> str:
        ext = os.path.splitext(filename)[-1].lower() or ".bin"
        return f"{self._prefix}/{payment_id}/{uuid.uuid4()}{ext}"

    async def upload(
        self,
        payment_id: str,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> str:
        key = self._make_key(payment_id, filename)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    async def get_presigned_url(self, s3_key: str, expires: int = 3600) -> str:
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": s3_key},
            ExpiresIn=expires,
        )

    async def delete(self, s3_key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=s3_key)

    async def check_connectivity(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
            return True
        except (BotoCoreError, ClientError):
            return False
