import argparse
from datetime import datetime, timezone
from pathlib import Path

from backend.storage.oci_object_storage import upload_file


parser = argparse.ArgumentParser(description="Upload a PostgreSQL dump to OCI Object Storage")
parser.add_argument("file", type=Path)
parser.add_argument("--prefix", default="database-backups")
args = parser.parse_args()
if not args.file.is_file():
    parser.error("backup file does not exist")
stamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
upload_file(args.file, f"{args.prefix.strip('/')}/{stamp}/{args.file.name}", "application/octet-stream")
