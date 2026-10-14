"""Optional OCI Object Storage adapter. Local development never enables it by default."""

import os
from pathlib import Path
from typing import BinaryIO

import oci


class OCIStorageConfigurationError(RuntimeError):
    pass


def oci_storage_enabled() -> bool:
    return os.getenv("POSTBRIDGE_MEDIA_STORAGE", "local").lower() == "oci"


def _client() -> oci.object_storage.ObjectStorageClient:
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


def upload_file(source: str | Path | BinaryIO, object_name: str, content_type: str | None = None) -> None:
    namespace = os.getenv("OCI_NAMESPACE")
    bucket = os.getenv("OCI_BUCKET_NAME")
    if not namespace or not bucket:
        raise OCIStorageConfigurationError("OCI_NAMESPACE and OCI_BUCKET_NAME are required.")
    should_close = False
    if isinstance(source, (str, Path)):
        source = open(source, "rb")
        should_close = True
    try:
        _client().put_object(
            namespace_name=namespace,
            bucket_name=bucket,
            object_name=object_name,
            put_object_body=source,
            content_type=content_type,
        )
    finally:
        if should_close:
            source.close()
