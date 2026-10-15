from __future__ import annotations

import asyncio
from typing import Any

import cloudinary.uploader
import pytest
from cloudinary.exceptions import BadRequest as CloudinaryBadRequest
from cloudinary.exceptions import GeneralError as CloudinaryGeneralError

from api.shared.exceptions import AppError
from api.shared.image_storage import ImageStorage, StoredImage
from database.config.settings import Settings, settings


@pytest.fixture
def cloudinary_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "demo-cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "demo-key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "demo-secret")


def test_upload_sends_image_to_cloudinary_and_returns_url_and_public_id(
    monkeypatch: pytest.MonkeyPatch, cloudinary_credentials: None
) -> None:
    calls: list[tuple[bytes, dict[str, Any]]] = []

    def fake_upload(file: bytes, **options: Any) -> dict[str, Any]:
        calls.append((file, options))
        return {
            "secure_url": "https://res.cloudinary.com/demo-cloud/image/upload/x.png",
            "public_id": "campus_cultural/events/x",
        }

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)

    image = asyncio.run(ImageStorage().upload(b"image-bytes", "campus_cultural/events"))

    assert image == StoredImage(
        url="https://res.cloudinary.com/demo-cloud/image/upload/x.png",
        public_id="campus_cultural/events/x",
    )
    assert calls == [
        (
            b"image-bytes",
            {
                "folder": "campus_cultural/events",
                "resource_type": "image",
                "cloud_name": "demo-cloud",
                "api_key": "demo-key",
                "api_secret": "demo-secret",
            },
        )
    ]


def test_upload_without_credentials_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "")

    with pytest.raises(AppError) as exc_info:
        asyncio.run(ImageStorage().upload(b"image-bytes", "campus_cultural/events"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "image_storage_unavailable"


def test_upload_rejected_by_cloudinary_returns_bad_request(
    monkeypatch: pytest.MonkeyPatch, cloudinary_credentials: None
) -> None:
    def fake_upload(file: bytes, **options: Any) -> dict[str, Any]:
        raise CloudinaryBadRequest("Invalid image file")

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)

    with pytest.raises(AppError) as exc_info:
        asyncio.run(ImageStorage().upload(b"not-an-image", "campus_cultural/events"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "invalid_image"


def test_upload_when_cloudinary_fails_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch, cloudinary_credentials: None
) -> None:
    def fake_upload(file: bytes, **options: Any) -> dict[str, Any]:
        raise CloudinaryGeneralError("Server error")

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)

    with pytest.raises(AppError) as exc_info:
        asyncio.run(ImageStorage().upload(b"image-bytes", "campus_cultural/events"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "image_storage_unavailable"


def test_delete_removes_image_from_cloudinary_and_its_cdn_cache(
    monkeypatch: pytest.MonkeyPatch, cloudinary_credentials: None
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_destroy(public_id: str, **options: Any) -> dict[str, Any]:
        calls.append((public_id, options))
        return {"result": "ok"}

    monkeypatch.setattr(cloudinary.uploader, "destroy", fake_destroy)

    asyncio.run(ImageStorage().delete("campus_cultural/events/x"))

    assert calls == [
        (
            "campus_cultural/events/x",
            {
                "resource_type": "image",
                "invalidate": True,
                "cloud_name": "demo-cloud",
                "api_key": "demo-key",
                "api_secret": "demo-secret",
            },
        )
    ]


def test_delete_of_image_already_gone_logs_nothing(
    monkeypatch: pytest.MonkeyPatch,
    cloudinary_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        cloudinary.uploader, "destroy", lambda public_id, **options: {"result": "not found"}
    )

    asyncio.run(ImageStorage().delete("campus_cultural/events/x"))

    assert caplog.records == []


def test_delete_when_cloudinary_fails_logs_warning_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    cloudinary_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fake_destroy(public_id: str, **options: Any) -> dict[str, Any]:
        raise CloudinaryGeneralError("Server error")

    monkeypatch.setattr(cloudinary.uploader, "destroy", fake_destroy)

    asyncio.run(ImageStorage().delete("campus_cultural/events/x"))

    assert "Could not delete image campus_cultural/events/x" in caplog.text


def test_delete_with_unexpected_result_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    cloudinary_credentials: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        cloudinary.uploader, "destroy", lambda public_id, **options: {"result": "error"}
    )

    asyncio.run(ImageStorage().delete("campus_cultural/events/x"))

    assert "Cloudinary did not delete image campus_cultural/events/x" in caplog.text


def test_delete_without_credentials_logs_warning_and_does_not_call_cloudinary(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "")

    def fake_destroy(public_id: str, **options: Any) -> dict[str, Any]:
        raise AssertionError("Cloudinary should not be called")

    monkeypatch.setattr(cloudinary.uploader, "destroy", fake_destroy)

    asyncio.run(ImageStorage().delete("campus_cultural/events/x"))

    assert "Cloudinary is not configured" in caplog.text


def test_production_requires_cloudinary_credentials() -> None:
    with pytest.raises(ValueError, match="CLOUDINARY_CLOUD_NAME"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql://user:pass@host/db",
            jwt_secret_key="x" * 64,
            seed_default_admin=False,
            cors_origins="https://campus-cultural.example",
            cloudinary_cloud_name="",
            cloudinary_api_key="",
            cloudinary_api_secret="",
        )
