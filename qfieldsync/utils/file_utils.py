"""
/***************************************************************************
 QFieldSync
                              -------------------
        begin                : 2016
        copyright            : (C) 2016 by OPENGIS.ch
        email                : info@opengis.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import hashlib
import logging
import os
import platform
import shutil
import stat
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Optional, TypedDict, Union

# OneDrive Files On-Demand file attributes (Windows)
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
_ETAG_BLOCKSIZE = 65536


PathLike = Union[Path, str]


logger = logging.getLogger(__name__)


class DirectoryTreeType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class DirectoryTreeDict(TypedDict):
    type: DirectoryTreeType
    path: Path
    content: list["DirectoryTreeDict"]


def path_to_dict(path: PathLike, dirs_only: bool = False) -> DirectoryTreeDict:
    path = Path(path)
    node: DirectoryTreeDict = {
        # default `type`, will be updated if it's a file
        "type": DirectoryTreeType.DIRECTORY,
        "path": path,
        "content": [],
    }

    if path.is_dir():
        node["type"] = DirectoryTreeType.DIRECTORY

        if dirs_only:
            glob_pattern = "*/"
        else:
            glob_pattern = "*"

        for subpath in path.glob(glob_pattern):
            if dirs_only and not subpath.is_dir():
                continue

            if ".qfieldsync" in str(subpath):
                continue

            node["content"].append(path_to_dict(subpath, dirs_only=dirs_only))
    elif not dirs_only:
        node["type"] = DirectoryTreeType.FILE

    node["content"].sort(key=lambda node: node["path"].name)

    return node


def mkdir(
    path: PathLike,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    """
    Create a directory at a given path and explicitly assign write permissions to make Windows happy.

    This function mimics the API of `Path.mkdir`.

    Apparently the passed `mode` value on `os.mkdir` and `Path.mkdir` is not respected by Windows prior to 3.13.
    What is more, in 3.13 Windows will handle only 0o700, the rest of the values will be ignored.

    See: https://docs.python.org/3/library/os.html#os.mkdir

    Args:
        path: the path to be created
        mode: The mode to be applied on the directory at the time of creation. Defaults to 0o777.
        parents: Whether to create directories recursively if missing. Defaults to False.
        exist_ok: Whether to not throw if the directory already exists. Defaults to False.

    """
    path = Path(path)
    # calling `mkdir` might trigger a `PermissionError` and other. The caller must handle the error.
    path.mkdir(mode, parents, exist_ok)

    current_permission = stat.S_IMODE(path.stat().st_mode)
    write_flags = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    # calling `chmod` might trigger a `PermissionError`. The parent must handle the error.
    path.chmod(current_permission | write_flags)


def calc_etag(filename: Union[str, Path], part_size: int = 8 * 1024 * 1024) -> str:
    """
    Calculate ETag as in Object Storage (S3) of a local file.

    ETag is a MD5. But for the multipart uploaded files, the MD5 is computed from the concatenation of the MD5s of each uploaded part.

    See the inspiration of this implementation here: https://stackoverflow.com/a/58239738/1226137

    Args:
        filename (str): the local filename
        part_size (int): the size of the Object Storage part. Most Object Storages use 8MB. Defaults to 8*1024*1024.

    Returns:
        str: the calculated ETag value

    """
    with _open_with_onedrive_retry(filename, "rb") as f:
        file_size = os.fstat(f.fileno()).st_size

        if file_size <= part_size:
            # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
            hasher = hashlib.md5()  # noqa: S324

            buf = f.read(_ETAG_BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(_ETAG_BLOCKSIZE)

            return hasher.hexdigest()
        else:
            # Say you uploaded a 14MB file and your part size is 5MB.
            # Calculate 3 MD5 checksums corresponding to each part, i.e. the checksum of the first 5MB, the second 5MB, and the last 4MB.
            # Then take the checksum of their concatenation.
            # Since MD5 checksums are hex representations of binary data, just make sure you take the MD5 of the decoded binary concatenation, not of the ASCII or UTF-8 encoded concatenation.
            # When that's done, add a hyphen and the number of parts to get the ETag.
            md5sums = []
            for data in iter(lambda: f.read(part_size), b""):
                # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
                md5sums.append(hashlib.md5(data).digest())  # noqa: S324

            # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
            final_md5sum = hashlib.md5(b"".join(md5sums))  # noqa: S324

            return "{}-{}".format(final_md5sum.hexdigest(), len(md5sums))


def _is_onedrive_cloud_file(filename: PathLike) -> bool:
    """
    Check if a file is a OneDrive cloud-only (dehydrated) placeholder.

    OneDrive Files On-Demand marks files that are not downloaded locally
    with special file attributes. These files cannot be opened directly
    and must first be hydrated (downloaded) by OneDrive.

    Returns:
        `True` if the file is a cloud-only OneDrive placeholder, `False` otherwise.

    """
    if platform.system() != "Windows":
        return False

    try:
        import ctypes  # noqa: PLC0415

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(filename))  # pyright: ignore[reportAttributeAccessIssue]
        if attrs == -1:  # INVALID_FILE_ATTRIBUTES
            return False

        return bool(
            attrs
            & (_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS | _FILE_ATTRIBUTE_RECALL_ON_OPEN)
        )
    except Exception:
        return False


def _open_with_onedrive_retry(
    filename: PathLike,
    mode: str = "rb",
    max_retries: int = 5,
    retry_delay_s: float = 2.0,
):
    """
    Open a file with retry logic to handle OneDrive Files On-Demand.

    When files reside in a OneDrive-synced folder, they may be cloud-only
    (dehydrated) or temporarily locked by the OneDrive sync process.
    A plain ``open()`` then raises ``PermissionError``.

    This helper detects that situation and retries with increasing delay,
    giving OneDrive time to hydrate / release the file.

    Args:
        filename: Path to the file to open.
        mode: File open mode (default ``"rb"``).
        max_retries: Number of retries after the first failure.
        retry_delay_s: Base delay in seconds between retries (doubles each attempt).

    Returns:
        An open file object (same as ``open()``).  The caller is responsible
        for closing it (use ``with`` statement).

    Raises:
        PermissionError: If all retries are exhausted.

    """
    last_error: Optional[PermissionError] = None

    for attempt in range(max_retries + 1):
        try:
            return open(filename, mode)
        except PermissionError as err:  # noqa: PERF203
            last_error = err

            if attempt >= max_retries:
                raise

            is_onedrive = _is_onedrive_cloud_file(filename)
            delay_s = retry_delay_s * (2**attempt)

            logger.info(
                "PermissionError opening '%s' (attempt %d/%d, OneDrive placeholder: %s). Retrying in %.1f s…",
                filename,
                attempt + 1,
                max_retries,
                is_onedrive,
                delay_s,
            )

            time.sleep(delay_s)

    assert last_error is not None

    # all retries exhausted, raise the last error
    raise last_error


def rmtree_onedrive_safe(
    path: Path, max_retries: int = 5, retry_delay_s: float = 2.0
) -> None:
    """
    Remove a directory tree with handling for OneDrive-locked files.

    OneDrive Files On-Demand can hold locks on directories and files inside
    synced folders, causing ``shutil.rmtree` to fail with `PermissionError`.
    This helper retries the removal with increasing delay and clears
    read-only attributes on individual files when needed.
    """

    def _onerror(func: Callable, fpath: str, _exc_info) -> None:
        """Error handler: clear read-only flag and retry the failed operation."""
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            shutil.rmtree(str(path), onerror=_onerror)
            return
        except PermissionError as err:  # noqa: PERF203
            last_error = err

            if attempt < max_retries:
                delay_s = retry_delay_s * (2**attempt)

                logger.info(
                    "PermissionError removing '%s' (attempt %d/%d, possibly locked by OneDrive). Retrying in %.1f s…",
                    path,
                    attempt + 1,
                    max_retries,
                    delay_s,
                )

                time.sleep(delay_s)

    # Final fallback: leave it and log a warning rather than crashing
    logger.info(
        "Could not fully remove '%s' after %d attempts: %s. Continuing anyway.",
        path,
        max_retries,
        last_error,
    )
