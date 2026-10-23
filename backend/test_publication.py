import base64
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from backend import instagram_api
from backend.auth import AuthenticatedUser


class FakeContentRepository:
    def __init__(self):
        self.media = []

    def upsert_media(self, items):
        self.media.extend(items)
        return items

    def create_tracked(self, user_id, media_id):
        return SimpleNamespace(id="tracked-1", user_id=user_id, media_id=media_id)


def _image_data(format_name: str) -> str:
    output = BytesIO()
    Image.new("RGBA" if format_name == "PNG" else "RGB", (8, 8), (80, 120, 240, 128) if format_name == "PNG" else (80, 120, 240)).save(output, format=format_name)
    return base64.b64encode(output.getvalue()).decode()


def test_instagram_publication_uploads_private_asset_publishes_and_tracks(monkeypatch):
    repository = FakeContentRepository()
    user = AuthenticatedUser(id="user-1", email="creator@example.test", token_hash="hash")
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user-1", status="connected")
    monkeypatch.setattr(instagram_api, "_active_account", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "_access_token", lambda value: "token")
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: repository)
    monkeypatch.setattr(instagram_api, "upload_bytes_with_temporary_read_url", lambda *args, **kwargs: "https://objectstorage.example/p/object.jpg")
    monkeypatch.setattr(instagram_api, "publish_instagram_image", lambda *args, **kwargs: {
        "id": "published-1", "media_type": "IMAGE", "media_url": "https://cdn.example/post.jpg",
        "permalink": "https://instagram.com/p/example", "caption": "Caption\n\n#tag",
        "timestamp": datetime(2026, 10, 22, tzinfo=timezone.utc).isoformat(),
    })

    result = instagram_api.publish(instagram_api.PublishRequest(
        platforms=["Instagram", "Threads"], caption="Caption", hashtags="#tag",
        image=instagram_api.PublishImage(mime_type="image/jpeg", data=_image_data("JPEG")),
    ), user)

    assert result["results"][0]["status"] == "published"
    assert result["results"][0]["tracked_post_id"] == "tracked-1"
    assert result["results"][1]["platform"] == "Threads"
    assert result["results"][1]["status"] == "unavailable"
    assert repository.media[0].instagram_media_id == "published-1"


def test_instagram_publication_converts_png_before_external_publish(monkeypatch):
    uploads = []
    def upload(*args, **kwargs):
        uploads.append(args)
        return "https://objectstorage.example/p/converted.jpg"
    monkeypatch.setattr(instagram_api, "upload_bytes_with_temporary_read_url", upload)
    account = SimpleNamespace(id="account-1", instagram_user_id="ig-user-1", status="connected")
    monkeypatch.setattr(instagram_api, "_active_account", lambda user_id: account)
    monkeypatch.setattr(instagram_api, "_access_token", lambda value: "token")
    monkeypatch.setattr(instagram_api, "get_content_repository", lambda: FakeContentRepository())
    monkeypatch.setattr(instagram_api, "publish_instagram_image", lambda *args, **kwargs: {
        "id": "published-png", "media_type": "IMAGE", "media_url": "https://cdn.example/post.jpg",
        "permalink": "https://instagram.com/p/png", "caption": "Caption",
        "timestamp": datetime(2026, 10, 22, tzinfo=timezone.utc).isoformat(),
    })
    user = AuthenticatedUser(id="user-1", email="creator@example.test", token_hash="hash")
    result = instagram_api.publish(instagram_api.PublishRequest(
        platforms=["Instagram"], caption="Caption", image=instagram_api.PublishImage(
            mime_type="image/png", data=_image_data("PNG")),
    ), user)
    assert result["results"][0]["status"] == "published"
    assert uploads[0][0].startswith(b"\xff\xd8\xff")
    assert uploads[0][2] == "image/jpeg"
