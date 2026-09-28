"""Temporary workspaces owned by the native client smoke fixtures."""
from contextlib import contextmanager
import errno
import tempfile
import time


@contextmanager
def temporary_workspace(*, prefix):
    directory = tempfile.TemporaryDirectory(prefix=prefix)
    try:
        yield directory.name
    finally:
        # A client can finish while a background Git clone is still exiting.
        # Retry only its transient directory race; never hide other failures.
        for attempt in range(6):
            try:
                directory.cleanup()
                break
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST) or attempt == 5:
                    raise
                time.sleep(0.2 * (attempt + 1))
