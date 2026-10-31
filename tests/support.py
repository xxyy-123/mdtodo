"""Shared helpers for the test suite."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import uuid
from typing import Iterator


@contextlib.contextmanager
def temp_workspace() -> Iterator[str]:
    """Create a throwaway directory that is always writable on Windows.

    ``tempfile.mkdtemp`` creates directories with mode ``0o700``, which some
    Windows sandboxes translate into an ACL that denies the owning process
    further writes. Using ``os.makedirs`` with the platform default gives a
    directory the process can actually use.
    """
    base = tempfile.gettempdir()
    path = os.path.join(base, f"mdtodo-test-{uuid.uuid4().hex[:12]}")
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
