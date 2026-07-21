"""
AWS S3 storage layer for repository metadata and indexing artifacts.

This module persists everything produced by the ingestion pipeline for a
single repository so it can be re-loaded later without re-cloning, re-chunking,
re-summarizing, or re-embedding the repository.

S3 layout
---------
repos/
    {repo_id}/
        metadata/
            repo_info.json       -> repo_url, repo_name, latest_commit, indexed_at
            chunk_hashes.json     -> {"src/auth.py::login": "hash1", ...}
        summaries/
            file_summaries.json   -> [{"file": "...", "summary": "..."}, ...]
            repo_summary.json     -> {"summary": "..."}
        vectorstore/
            faiss.index            -> serialized FAISS index
            metadata.pkl           -> pickled chunk metadata for the FAISS index

Configuration
-------------
The following environment variables are required (typically loaded from a
``.env`` file via ``python-dotenv``):

- ``AWS_REGION``      AWS region the S3 bucket lives in.
- ``S3_BUCKET_NAME``  Name of the S3 bucket used for storage.

AWS credentials themselves are resolved by boto3's default credential chain
(environment variables, shared credentials file, IAM role, etc.).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JSONType = Union[Dict[str, Any], List[Any]]


class S3StorageError(Exception):
    """Raised when an S3 operation fails for a reason other than a missing object."""


# ---------------------------------------------------------------------------
# Client / configuration helpers
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3_client():
    """Return a cached, lazily-initialized S3 client.

    Returns:
        A boto3 S3 client configured with the ``AWS_REGION`` environment
        variable (if set).
    """
    global _s3_client
    if _s3_client is None:
        region = os.getenv("AWS_REGION")
        _s3_client = boto3.client("s3", region_name=region)
    return _s3_client


def _get_bucket_name() -> str:
    """Return the configured S3 bucket name.

    Raises:
        S3StorageError: If the ``S3_BUCKET_NAME`` environment variable is not set.
    """
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise S3StorageError("S3_BUCKET_NAME environment variable is not set.")
    return bucket


# ---------------------------------------------------------------------------
# S3 key helpers
# ---------------------------------------------------------------------------

def _metadata_key(repo_id: str, filename: str) -> str:
    return f"repos/{repo_id}/metadata/{filename}"


def _summaries_key(repo_id: str, filename: str) -> str:
    return f"repos/{repo_id}/summaries/{filename}"


def _vectorstore_key(repo_id: str, filename: str) -> str:
    return f"repos/{repo_id}/vectorstore/{filename}"


# ---------------------------------------------------------------------------
# Generic JSON helpers
# ---------------------------------------------------------------------------

def save_json_to_s3(bucket: str, key: str, data: JSONType) -> None:
    """Serialize ``data`` to JSON and upload it to ``s3://{bucket}/{key}``.

    Args:
        bucket: Target S3 bucket name.
        key: Target S3 object key.
        data: A JSON-serializable dict or list.

    Raises:
        S3StorageError: If the upload fails.
    """
    client = _get_s3_client()
    body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
    except (BotoCoreError, ClientError) as exc:
        raise S3StorageError(
            f"Failed to upload JSON to s3://{bucket}/{key}: {exc}"
        ) from exc

    logger.info("Uploaded JSON to s3://%s/%s (%d bytes)", bucket, key, len(body))


def load_json_from_s3(bucket: str, key: str) -> Optional[JSONType]:
    """Download and parse a JSON object from ``s3://{bucket}/{key}``.

    Args:
        bucket: Source S3 bucket name.
        key: Source S3 object key.

    Returns:
        The parsed JSON content as a dict or list, or ``None`` if the object
        does not exist (handled gracefully and logged as a warning).

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing, or if the object content is not valid JSON.
    """
    client = _get_s3_client()

    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            logger.warning("Object not found: s3://%s/%s", bucket, key)
            return None
        raise S3StorageError(
            f"Failed to download JSON from s3://{bucket}/{key}: {exc}"
        ) from exc
    except BotoCoreError as exc:
        raise S3StorageError(
            f"Failed to download JSON from s3://{bucket}/{key}: {exc}"
        ) from exc

    try:
        data = json.loads(response["Body"].read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise S3StorageError(
            f"Invalid JSON content at s3://{bucket}/{key}: {exc}"
        ) from exc

    logger.info("Downloaded JSON from s3://%s/%s", bucket, key)
    return data


# ---------------------------------------------------------------------------
# Generic binary file helpers
# ---------------------------------------------------------------------------

def _upload_file(local_path: str, bucket: str, key: str, description: str) -> str:
    """Upload a local file to S3.

    Args:
        local_path: Path to the local file to upload.
        bucket: Target S3 bucket name.
        key: Target S3 object key.
        description: Human-readable description used in log/error messages.

    Returns:
        The S3 object key the file was uploaded to.

    Raises:
        FileNotFoundError: If ``local_path`` does not exist.
        S3StorageError: If the upload fails.
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"{description} not found at: {local_path}")

    client = _get_s3_client()

    try:
        client.upload_file(local_path, bucket, key)
    except (BotoCoreError, ClientError) as exc:
        raise S3StorageError(
            f"Failed to upload {description} to s3://{bucket}/{key}: {exc}"
        ) from exc

    logger.info("Uploaded %s from %s to s3://%s/%s", description, local_path, bucket, key)
    return key


def _download_file(bucket: str, key: str, local_path: str, description: str) -> Optional[str]:
    """Download a file from S3 to a local path.

    Args:
        bucket: Source S3 bucket name.
        key: Source S3 object key.
        local_path: Local path to write the downloaded file to. Parent
            directories are created if needed.
        description: Human-readable description used in log/error messages.

    Returns:
        ``local_path`` if the download succeeded, or ``None`` if the object
        does not exist (handled gracefully and logged as a warning).

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    client = _get_s3_client()

    local_dir = os.path.dirname(os.path.abspath(local_path))
    if local_dir:
        os.makedirs(local_dir, exist_ok=True)

    try:
        client.download_file(bucket, key, local_path)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey"):
            logger.warning("%s not found: s3://%s/%s", description, bucket, key)
            return None
        raise S3StorageError(
            f"Failed to download {description} from s3://{bucket}/{key}: {exc}"
        ) from exc
    except BotoCoreError as exc:
        raise S3StorageError(
            f"Failed to download {description} from s3://{bucket}/{key}: {exc}"
        ) from exc

    logger.info("Downloaded %s from s3://%s/%s to %s", description, bucket, key, local_path)
    return local_path


# ---------------------------------------------------------------------------
# Repo metadata: repo_info.json
# ---------------------------------------------------------------------------

def upload_repo_metadata(repo_id: str, repo_info: Dict[str, Any]) -> str:
    """Upload repository metadata to ``repos/{repo_id}/metadata/repo_info.json``.

    Args:
        repo_id: Unique identifier for the repository.
        repo_info: Dict matching the format::

            {
                "repo_url": "...",
                "repo_name": "...",
                "latest_commit": "...",
                "indexed_at": "..."
            }

    Returns:
        The S3 object key the data was uploaded to.

    Raises:
        S3StorageError: If the upload fails.
    """
    bucket = _get_bucket_name()
    key = _metadata_key(repo_id, "repo_info.json")
    save_json_to_s3(bucket, key, repo_info)
    return key


def download_repo_metadata(repo_id: str) -> Dict[str, Any]:
    """Download repository metadata from ``repos/{repo_id}/metadata/repo_info.json``.

    Args:
        repo_id: Unique identifier for the repository.

    Returns:
        The repo metadata dict, or an empty dict if it has not been uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _metadata_key(repo_id, "repo_info.json")
    data = load_json_from_s3(bucket, key)
    return data if data is not None else {}


# ---------------------------------------------------------------------------
# Chunk hashes: chunk_hashes.json
# ---------------------------------------------------------------------------

def upload_chunk_hashes(repo_id: str, chunk_hashes: Dict[str, str]) -> str:
    """Upload chunk hashes to ``repos/{repo_id}/metadata/chunk_hashes.json``.

    Args:
        repo_id: Unique identifier for the repository.
        chunk_hashes: Dict mapping ``"{file}::{symbol}"`` to a content hash,
            e.g. ``{"src/auth.py::login": "hash1"}``.

    Returns:
        The S3 object key the data was uploaded to.

    Raises:
        S3StorageError: If the upload fails.
    """
    bucket = _get_bucket_name()
    key = _metadata_key(repo_id, "chunk_hashes.json")
    save_json_to_s3(bucket, key, chunk_hashes)
    return key


def download_chunk_hashes(repo_id: str) -> Dict[str, str]:
    """Download chunk hashes from ``repos/{repo_id}/metadata/chunk_hashes.json``.

    Args:
        repo_id: Unique identifier for the repository.

    Returns:
        A dict mapping ``"{file}::{symbol}"`` to a content hash, or an empty
        dict if it has not been uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _metadata_key(repo_id, "chunk_hashes.json")
    data = load_json_from_s3(bucket, key)
    return data if data is not None else {}


# ---------------------------------------------------------------------------
# File summaries: file_summaries.json
# ---------------------------------------------------------------------------

def upload_file_summaries(repo_id: str, file_summaries: List[Dict[str, str]]) -> str:
    """Upload file summaries to ``repos/{repo_id}/summaries/file_summaries.json``.

    Args:
        repo_id: Unique identifier for the repository.
        file_summaries: List of dicts matching the format::

            [{"file": "src/auth.py", "summary": "..."}]

    Returns:
        The S3 object key the data was uploaded to.

    Raises:
        S3StorageError: If the upload fails.
    """
    bucket = _get_bucket_name()
    key = _summaries_key(repo_id, "file_summaries.json")
    save_json_to_s3(bucket, key, file_summaries)
    return key


def download_file_summaries(repo_id: str) -> List[Dict[str, str]]:
    """Download file summaries from ``repos/{repo_id}/summaries/file_summaries.json``.

    Args:
        repo_id: Unique identifier for the repository.

    Returns:
        A list of ``{"file": ..., "summary": ...}`` dicts, or an empty list
        if it has not been uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _summaries_key(repo_id, "file_summaries.json")
    data = load_json_from_s3(bucket, key)
    return data if data is not None else []


# ---------------------------------------------------------------------------
# Repo summary: repo_summary.json
# ---------------------------------------------------------------------------

def upload_repo_summary(repo_id: str, repo_summary: Union[str, Dict[str, Any]]) -> str:
    """Upload the repository summary to ``repos/{repo_id}/summaries/repo_summary.json``.

    Args:
        repo_id: Unique identifier for the repository.
        repo_summary: Either the summary text as a string, or a dict already
            matching the format ``{"summary": "..."}``.

    Returns:
        The S3 object key the data was uploaded to.

    Raises:
        S3StorageError: If the upload fails.
    """
    payload = {"summary": repo_summary} if isinstance(repo_summary, str) else repo_summary

    bucket = _get_bucket_name()
    key = _summaries_key(repo_id, "repo_summary.json")
    save_json_to_s3(bucket, key, payload)
    return key


def download_repo_summary(repo_id: str) -> Dict[str, str]:
    """Download the repository summary from ``repos/{repo_id}/summaries/repo_summary.json``.

    Args:
        repo_id: Unique identifier for the repository.

    Returns:
        A dict ``{"summary": "..."}``, or an empty dict if it has not been
        uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _summaries_key(repo_id, "repo_summary.json")
    data = load_json_from_s3(bucket, key)
    return data if data is not None else {}


# ---------------------------------------------------------------------------
# FAISS index: faiss.index
# ---------------------------------------------------------------------------

def upload_faiss_index(repo_id: str, faiss_index_path: str) -> str:
    """Upload a local FAISS index file to ``repos/{repo_id}/vectorstore/faiss.index``.

    Args:
        repo_id: Unique identifier for the repository.
        faiss_index_path: Path to the local FAISS index file.

    Returns:
        The S3 object key the file was uploaded to.

    Raises:
        FileNotFoundError: If ``faiss_index_path`` does not exist.
        S3StorageError: If the upload fails.
    """
    bucket = _get_bucket_name()
    key = _vectorstore_key(repo_id, "faiss.index")
    return _upload_file(faiss_index_path, bucket, key, "FAISS index")


def download_faiss_index(repo_id: str, local_path: str) -> Optional[str]:
    """Download the FAISS index for a repo to a local path.

    Args:
        repo_id: Unique identifier for the repository.
        local_path: Local path to write the FAISS index file to. Parent
            directories are created if needed.

    Returns:
        ``local_path`` if the download succeeded, or ``None`` if no index
        has been uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _vectorstore_key(repo_id, "faiss.index")
    return _download_file(bucket, key, local_path, "FAISS index")


# ---------------------------------------------------------------------------
# Vector store metadata pickle: metadata.pkl
# ---------------------------------------------------------------------------

def upload_metadata_pickle(repo_id: str, metadata_path: str) -> str:
    """Upload a local vector-store metadata pickle to ``repos/{repo_id}/vectorstore/metadata.pkl``.

    Args:
        repo_id: Unique identifier for the repository.
        metadata_path: Path to the local metadata pickle file.

    Returns:
        The S3 object key the file was uploaded to.

    Raises:
        FileNotFoundError: If ``metadata_path`` does not exist.
        S3StorageError: If the upload fails.
    """
    bucket = _get_bucket_name()
    key = _vectorstore_key(repo_id, "metadata.pkl")
    return _upload_file(metadata_path, bucket, key, "vector store metadata pickle")


def download_metadata_pickle(repo_id: str, local_path: str) -> Optional[str]:
    """Download the vector-store metadata pickle for a repo to a local path.

    Args:
        repo_id: Unique identifier for the repository.
        local_path: Local path to write the metadata pickle file to. Parent
            directories are created if needed.

    Returns:
        ``local_path`` if the download succeeded, or ``None`` if no metadata
        pickle has been uploaded yet.

    Raises:
        S3StorageError: If the download fails for a reason other than the
            object being missing.
    """
    bucket = _get_bucket_name()
    key = _vectorstore_key(repo_id, "metadata.pkl")
    return _download_file(bucket, key, local_path, "vector store metadata pickle")


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    repo_id = "repo_123"

    # --- Repo metadata -----------------------------------------------------
    upload_repo_metadata(
        repo_id,
        {
            "repo_url": "https://github.com/example/example-repo",
            "repo_name": "example-repo",
            "latest_commit": "a1b2c3d4e5f6",
            "indexed_at": "2024-01-01T12:00:00Z",
        },
    )
    print("repo_info.json:", download_repo_metadata(repo_id))

    # --- Chunk hashes --------------------------------------------------------
    upload_chunk_hashes(
        repo_id,
        {
            "src/auth.py::login": "hash1",
            "src/auth.py::logout": "hash2",
        },
    )
    print("chunk_hashes.json:", download_chunk_hashes(repo_id))

    # --- File summaries ------------------------------------------------------
    upload_file_summaries(
        repo_id,
        [
            {"file": "src/auth.py", "summary": "Handles user login and logout."},
        ],
    )
    print("file_summaries.json:", download_file_summaries(repo_id))

    # --- Repo summary ---------------------------------------------------------
    upload_repo_summary(repo_id, "This repository implements a simple authentication service.")
    print("repo_summary.json:", download_repo_summary(repo_id))

    # --- FAISS index ------------------------------------------------------------
    faiss_index_path = "data/vectorstore/faiss.index"
    if os.path.exists(faiss_index_path):
        upload_faiss_index(repo_id, faiss_index_path)
        download_faiss_index(repo_id, "data/downloaded/faiss.index")

    # --- Vector store metadata pickle --------------------------------------------
    metadata_path = "data/vectorstore/metadata.pkl"
    if os.path.exists(metadata_path):
        upload_metadata_pickle(repo_id, metadata_path)
        download_metadata_pickle(repo_id, "data/downloaded/metadata.pkl")
