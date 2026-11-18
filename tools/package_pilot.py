"""Create an offline customer ZIP from an explicit public-file allowlist."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tlm_lab import __version__
from tlm_lab.runner import digest

FOLDERS = ("tlm_lab", "sdk", "examples", "configs", "rtl", "docs", "adapters", "platform", "tools", "tests", "vendor")
FILES = ("README.md", "CMakeLists.txt", "tlm-lab.py", "tlm-lab.cmd", ".gitattributes", ".gitignore")


def package(output, root=ROOT):
    output, root = Path(output).resolve(), Path(root).resolve()
    if output.exists():
        raise FileExistsError(f"Package already exists: {output}")
    files = [root/name for name in FILES]
    for name in FOLDERS:
        files.extend(path for path in (root/name).rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Package source escapes distribution: {path}")
    names = {path.relative_to(root).as_posix(): path for path in files}
    manifest = {"version": __version__, "files_sha256": {name: digest(path) for name, path in sorted(names.items())},
                "excludes": ["runs", "private", ".deps", "build*", ".git", "dist"],
                "requirements": "Python 3.9+ for demo/core; customer build tools for customer IP"}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="pilot-", suffix=".zip", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(names.items()):
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != manifest["files_sha256"][name]:
                    raise ValueError(f"Source changed while packaging: {name}; retry after edits finish")
                archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data, compress_type=zipfile.ZIP_DEFLATED)
            archive.writestr(zipfile.ZipInfo("PACKAGE-MANIFEST.json", date_time=(2026, 1, 1, 0, 0, 0)),
                             json.dumps(manifest, indent=2, sort_keys=True)+"\n", compress_type=zipfile.ZIP_DEFLATED)
        os.link(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"package": str(output), "version": __version__, "sha256": digest(output), "bytes": output.stat().st_size,
            "files": len(names)+1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=f"dist/tlm-performance-lab-{__version__}.zip")
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.output), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(2, f"ERROR: {error}\n")
