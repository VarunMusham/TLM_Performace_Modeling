"""Strict JSON input and atomic, non-overwriting artifact publication."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import tempfile


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        _invalid_constant(value)
    return number


def parse_json(text):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=_invalid_constant, parse_float=_finite_float)


def load_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


@contextmanager
def exclusive_text(path):
    """Publish complete bytes using a same-filesystem, no-clobber hard link.

    Local NTFS and POSIX filesystems support this operation. An unsupported
    filesystem raises an error instead of falling back to a partial final file.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Artifact already exists: {path}")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def dump(path, value):
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with exclusive_text(path) as stream:
        stream.write(text)
