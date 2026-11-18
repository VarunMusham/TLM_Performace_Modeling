"""Offline, workspace-local native WDT setup from pinned dependency source."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import uuid
from .config import integer, require
from .external import relative_path
from .runner import ROOT, digest, process
from .storage import dump, load_json


def extract_source(archive, destination):
    """Extract regular files/directories only; never follow archive links."""
    destination = Path(destination).resolve()
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            name = member.name.rstrip("/")
            target = destination/relative_path(name)
            require(member.isdir() or member.isfile(), f"Unsupported archive entry: {member.name}")
            require(target.resolve().is_relative_to(destination), "Archive path escapes destination")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(member.mode & 0o777)


def setup_wdt(compiler=None, generator="Ninja", jobs=4):
    integer(jobs, "jobs", 1, 32)
    require(shutil.which("cmake"), "CMake is missing. Install CMake or use the Python-only demo.")
    if generator == "Ninja":
        require(shutil.which("ninja"), "Ninja is missing. Install Ninja or choose --generator for your existing build tool.")
    compiler = compiler or shutil.which("g++") or shutil.which("cl") or shutil.which("c++")
    require(compiler and shutil.which(compiler), "No C++ compiler found. Open your compiler's developer shell or pass --compiler PATH.")
    compiler = str(Path(shutil.which(compiler)).resolve())
    dependency = load_json(ROOT/"vendor"/"systemc"/"dependency.json")
    archive = ROOT/"vendor"/"systemc"/dependency["archive"]
    print("Checking bundled SystemC source (no network downloads)...", flush=True)
    require(digest(archive) == dependency["sha256"], "Bundled SystemC archive hash differs; restore vendor/systemc before building")
    deps = ROOT/".deps"
    deps.mkdir(exist_ok=True)
    source_cache = deps/("systemc-source-"+dependency["sha256"][:12])
    if not source_cache.exists():
        print("Extracting SystemC source into the workspace...", flush=True)
        with tempfile.TemporaryDirectory(prefix="systemc-extract-", dir=deps) as temporary:
            extracted = Path(temporary)/"source"
            extracted.mkdir()
            extract_source(archive, extracted)
            hashes = {path.relative_to(extracted).as_posix(): digest(path) for path in extracted.rglob("*") if path.is_file()}
            dump(extracted/"source-hashes.json", hashes)
            extracted.rename(source_cache)
    hashes = load_json(source_cache/"source-hashes.json")
    require(all(digest(source_cache/relative_path(name)) == expected for name, expected in hashes.items()),
            "Cached SystemC source changed. Restore the cached files or use a fresh distribution folder.")
    identity = {"archive_sha256": dependency["sha256"], "compiler": compiler, "compiler_sha256": digest(compiler), "generator": generator}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    build, install = deps/("systemc-build-"+key), deps/("systemc-install-"+key)
    native = ROOT/"build-pilot"
    logs = ROOT/"runs"/("setup-"+uuid.uuid4().hex[:12])
    logs.mkdir(parents=True)
    records = []
    configuration = ["cmake", "-S", source_cache/"systemc-2.3.4", "-B", build, "-G", generator,
                     "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_STANDARD=14", "-DBUILD_SHARED_LIBS=OFF",
                     "-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON", "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
                     "-DCMAKE_CXX_COMPILER="+compiler, "-DCMAKE_INSTALL_PREFIX="+str(install)]
    if os.name == "nt" and Path(compiler).name in {"g++.exe", "c++.exe", "g++", "c++"}:
        configuration.append("-DCMAKE_ASM_FLAGS=-x assembler-with-cpp")
    commands = [("configure-systemc", configuration),
                ("build-systemc", ["cmake", "--build", build, "--config", "Release", "--parallel", str(jobs)]),
                ("install-systemc", ["cmake", "--install", build, "--config", "Release"]),
                ("configure-wdt", ["cmake", "-S", ROOT, "-B", native, "-G", generator, "-DCMAKE_BUILD_TYPE=Release",
                                   "-DCMAKE_CXX_COMPILER="+compiler, "-DCMAKE_PREFIX_PATH="+str(install),
                                   "-DSystemCLanguage_DIR="+str(install/"lib"/"cmake"/"SystemCLanguage")]),
                ("build-wdt", ["cmake", "--build", native, "--config", "Release", "--parallel", str(jobs)])]
    try:
        for stem, command in commands:
            print(f"{stem}... logs: {logs}", flush=True)
            result = process(command, logs, stem, 600, records)
            require(result["exit_code"] == 0 and not result["timed_out"] and not result.get("error"),
                    f"{stem} failed; open {logs / (stem+'.stderr.log')}")
    finally:
        dump(logs/"setup.json", {"dependency": dependency, "toolchain": identity, "processes": records})
    return f"WDT is ready. Run: python tlm-lab.py run configs/wdt_scenario.example.json\nValidate: ctest --test-dir build-pilot -C Release --output-on-failure"
