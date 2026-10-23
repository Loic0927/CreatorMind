from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from backend.storage import oci_object_storage


class FakeClient:
    def __init__(self):
        self.base_client = SimpleNamespace(endpoint="https://objectstorage.example")
        self.puts = []
        self.requests = []

    def put_object(self, **kwargs):
        body = kwargs["put_object_body"]
        self.puts.append({**kwargs, "put_object_body": body.read() if isinstance(body, BytesIO) else body})

    def create_preauthenticated_request(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(data=SimpleNamespace(access_uri="/p/token/n/ns/b/bucket/o/image.jpg"))


def test_private_upload_and_temporary_object_url_are_separate(monkeypatch):
    client = FakeClient()
    monkeypatch.setenv("OCI_NAMESPACE", "ns")
    monkeypatch.setenv("OCI_BUCKET_NAME", "private-bucket")
    monkeypatch.setattr(oci_object_storage, "_client", lambda: client)
    monkeypatch.setattr(oci_object_storage, "_oci_module", lambda: SimpleNamespace(
        object_storage=SimpleNamespace(models=SimpleNamespace(
            CreatePreauthenticatedRequestDetails=lambda **values: SimpleNamespace(**values)
        ))
    ))

    oci_object_storage.upload_private_bytes(b"image", "draft-assets/user/image.jpg", "image/jpeg")
    url = oci_object_storage.create_temporary_read_url("draft-assets/user/image.jpg", lifetime_minutes=60)

    assert client.puts[0]["bucket_name"] == "private-bucket"
    assert client.puts[0]["put_object_body"] == b"image"
    details = client.requests[0]["create_preauthenticated_request_details"]
    assert details.access_type == "ObjectRead"
    assert details.object_name == "draft-assets/user/image.jpg"
    lifetime = details.time_expires - datetime.now(timezone.utc)
    assert 59 * 60 < lifetime.total_seconds() <= 60 * 60
    assert url == "https://objectstorage.example/p/token/n/ns/b/bucket/o/image.jpg"


def test_upload_with_temporary_url_uploads_once(monkeypatch):
    uploaded = []
    monkeypatch.setattr(oci_object_storage, "upload_private_bytes", lambda *args: uploaded.append(args))
    monkeypatch.setattr(oci_object_storage, "create_temporary_read_url", lambda name, lifetime_minutes: f"https://temporary/{name}?minutes={lifetime_minutes}")

    url = oci_object_storage.upload_bytes_with_temporary_read_url(
        b"jpeg", "publication-assets/user/image.jpg", "image/jpeg", lifetime_minutes=15,
    )

    assert len(uploaded) == 1
    assert url.endswith("?minutes=15")
