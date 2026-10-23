import base64
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from backend.services.publishing import (
    InstagramPublishingAdapter,
    PublishInput,
    PublishingAdapterRegistry,
    UnavailablePublishingAdapter,
)


class FakeContentRepository:
    def __init__(self):
        self.media = []

    def upsert_media(self, items):
        self.media.extend(items)

    def create_tracked(self, user_id, media_id):
        return SimpleNamespace(id="tracked-1")


def _request(mime_type="image/jpeg"):
    output = BytesIO()
    Image.new("RGBA" if mime_type == "image/png" else "RGB", (8, 8), (255, 0, 0, 128) if mime_type == "image/png" else (255, 0, 0)).save(
        output, format="PNG" if mime_type == "image/png" else "JPEG"
    )
    return PublishInput(
        caption="Caption", hashtags="#tag", mime_type=mime_type,
        encoded_media=base64.b64encode(output.getvalue()).decode(),
    )


def test_fake_unavailable_adapter_uses_the_shared_contract():
    adapter = UnavailablePublishingAdapter("FutureNetwork")
    registry = PublishingAdapterRegistry([adapter])
    assert registry.capabilities("user-1")[0].available is False
    assert registry.get("FutureNetwork").validate(_request()).status == "unavailable"
    assert registry.get("FutureNetwork").publish("user-1", _request()).status == "unavailable"
    assert registry.get("FutureNetwork").status("user-1", "post") == "unavailable"


def test_instagram_adapter_validates_publishes_and_normalizes_result():
    repository = FakeContentRepository()
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user", status="connected")
    uploaded = []
    adapter = InstagramPublishingAdapter(
        account_loader=lambda user_id: account,
        token_loader=lambda value: "server-side-token",
        repository_loader=lambda: repository,
        uploader=lambda data, name, mime: uploaded.append((data, name, mime)) or "https://temporary.example/image.jpg",
        provider_publisher=lambda token, user_id, url, caption: {
            "id": "provider-post-1", "media_type": "IMAGE", "media_url": url,
            "permalink": "https://instagram.example/p/1", "caption": caption,
            "timestamp": datetime(2026, 10, 22, tzinfo=timezone.utc).isoformat(),
        },
    )

    assert adapter.capability("user-1").available is True
    assert adapter.validate(_request("image/png")) is None
    result = adapter.publish("user-1", _request())
    assert result.status == "published"
    assert result.provider_post_id == "provider-post-1"
    assert result.tracked_post_id == "tracked-1"
    assert uploaded[0][2] == "image/jpeg"
    assert repository.media[0].caption == "Caption\n\n#tag"
    assert adapter.status("user-1", result.provider_post_id) == "published"


def test_instagram_adapter_converts_stored_png_to_jpeg_before_publishing():
    repository = FakeContentRepository()
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user", status="connected")
    source = base64.b64decode(_request("image/png").encoded_media)
    uploaded = []
    adapter = InstagramPublishingAdapter(
        account_loader=lambda user_id: account,
        token_loader=lambda value: "server-side-token",
        repository_loader=lambda: repository,
        object_loader=lambda name: source,
        uploader=lambda data, name, mime: uploaded.append((data, name, mime)) or "https://temporary.example/converted.jpg",
        provider_publisher=lambda token, user_id, url, caption: {
            "id": "provider-png", "media_type": "IMAGE", "media_url": url,
            "permalink": "https://instagram.example/p/png", "caption": caption,
            "timestamp": datetime(2026, 10, 22, tzinfo=timezone.utc).isoformat(),
        },
    )
    request = PublishInput(caption="PNG", hashtags="", mime_type="image/png", object_name="draft-assets/user-1/image.png")

    result = adapter.publish("user-1", request)

    assert result.status == "published"
    assert uploaded[0][0].startswith(b"\xff\xd8\xff")
    assert uploaded[0][1].endswith(".jpg")
    assert uploaded[0][2] == "image/jpeg"


def test_instagram_adapter_reuses_stored_private_object(monkeypatch):
    repository = FakeContentRepository()
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user", status="connected")
    temporary_urls = []
    adapter = InstagramPublishingAdapter(
        account_loader=lambda user_id: account,
        token_loader=lambda value: "server-side-token",
        repository_loader=lambda: repository,
        uploader=lambda *args: (_ for _ in ()).throw(AssertionError("stored media must not be uploaded again")),
        temporary_url_factory=lambda name, lifetime_minutes: temporary_urls.append((name, lifetime_minutes)) or "https://temporary.example/image.jpg",
        provider_publisher=lambda token, user_id, url, caption: {
            "id": "provider-post-2", "media_type": "IMAGE", "media_url": url,
            "permalink": "https://instagram.example/p/2", "caption": caption,
            "timestamp": datetime(2026, 10, 22, tzinfo=timezone.utc).isoformat(),
        },
    )
    request = PublishInput(
        caption="Stored", hashtags="#private", mime_type="image/jpeg",
        object_name="draft-assets/user-1/image.jpg",
    )

    result = adapter.publish("user-1", request)

    assert result.status == "published"
    assert temporary_urls == [("draft-assets/user-1/image.jpg", 60)]
    assert repository.media[0].instagram_media_id == "provider-post-2"
