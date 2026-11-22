"""Optional OCI Object Storage adapter. Local development never enables it by default."""

import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any


class OCIStorageConfigurationError(RuntimeError):
    pass


def oci_storage_enabled() -> bool:
    return os.getenv("POSTBRIDGE_MEDIA_STORAGE", "local").lower() == "oci"


def _oci_module() -> Any:
    try:
        import oci
    except ImportError as exc:
        raise OCIStorageConfigurationError("The OCI SDK is not installed.") from exc
    return oci


def _client() -> Any:
    oci = _oci_module()
    config_file = os.getenv("OCI_CONFIG_FILE")
    if config_file:
        config = oci.config.from_file(
            file_location=config_file,
            profile_name=os.getenv("OCI_CONFIG_PROFILE", "DEFAULT"),
        )
    else:
        required = ("OCI_USER_OCID", "OCI_TENANCY_OCID", "OCI_FINGERPRINT", "OCI_PRIVATE_KEY_PATH", "OCI_REGION")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise OCIStorageConfigurationError("Missing OCI configuration: " + ", ".join(missing))
        config = {
            "user": os.environ["OCI_USER_OCID"],
            "tenancy": os.environ["OCI_TENANCY_OCID"],
            "fingerprint": os.environ["OCI_FINGERPRINT"],
            "key_file": os.environ["OCI_PRIVATE_KEY_PATH"],
            "region": os.environ["OCI_REGION"],
        }
    oci.config.validate_config(config)
    return oci.object_storage.ObjectStorageClient(config)


def _bucket() -> dict[str, str]:
    namespace, bucket = os.getenv("OCI_NAMESPACE"), os.getenv("OCI_BUCKET_NAME")
    if not namespace or not bucket:
        raise OCIStorageConfigurationError("OCI_NAMESPACE and OCI_BUCKET_NAME are required.")
    return {"namespace_name": namespace, "bucket_name": bucket}


def upload_private_bytes(body: bytes, object_name: str, content_type: str) -> None:
    """Upload bytes without changing the bucket's private visibility."""
    target = _bucket()
    _client().put_object(**target, object_name=object_name, put_object_body=BytesIO(body), content_type=content_type)


def upload_bytes_with_temporary_read_url(
    body: bytes, object_name: str, content_type: str, *, lifetime_minutes: int = 60
) -> str:
    """Upload a private object and return a short-lived object-read URL."""
    upload_private_bytes(body, object_name, content_type)
    return create_temporary_read_url(object_name, lifetime_minutes=lifetime_minutes)


def download_private_bytes(object_name: str, *, max_bytes: int = 10 * 1024 * 1024) -> bytes:
    """Read one private object with a strict size limit for server-side processing."""
    target = _bucket()
    body = _client().get_object(**target, object_name=object_name).data.raw.read(max_bytes + 1)
    if not body or len(body) > max_bytes:
        raise OCIStorageConfigurationError("Stored media is empty or exceeds the processing limit.")
    return body


def delete_private_prefix(prefix: str) -> int:
    """Delete every private object under ``prefix`` and return how many were removed."""
    if not prefix.endswith("/"):
        raise ValueError("Prefix must end with '/' so it cannot match a sibling folder.")
    target = _bucket()
    client = _client()
    deleted, start = 0, None
    while True:
        page = client.list_objects(**target, prefix=prefix, start=start).data
        for item in page.objects:
            client.delete_object(**target, object_name=item.name)
            deleted += 1
        start = page.next_start_with
        if not start:
            return deleted


def create_temporary_read_url(object_name: str, *, lifetime_minutes: int = 60) -> str:
    """Create a short-lived read URL for one already-private object."""
    target = _bucket()
    client = _client()
    now = datetime.now(UTC)
    details = _oci_module().object_storage.models.CreatePreauthenticatedRequestDetails(
        name=f"postbridge-publish-{now.strftime('%Y%m%d%H%M%S')}",
        access_type="ObjectRead",
        object_name=object_name,
        time_expires=now + timedelta(minutes=lifetime_minutes),
    )
    response = client.create_preauthenticated_request(**target, create_preauthenticated_request_details=details)
    return f"{str(client.base_client.endpoint).rstrip('/')}{response.data.access_uri}"
