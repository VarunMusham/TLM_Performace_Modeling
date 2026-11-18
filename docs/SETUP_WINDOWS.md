# Windows setup

For a customer pilot, start with `python tlm-lab.py demo --open`: only Python 3.9+
is needed. For native WDT, `python tlm-lab.py setup-wdt` verifies and builds the
SystemC 2.3.4 source bundled under `vendor/systemc/`, then builds `build-pilot/`.
This offline setup needs CMake, Ninja and a C++ compiler; it does not download
packages or install system-wide files. The CLI automatically prefers the resulting
binary. MinGW WDT builds link their compiler runtime statically, reducing PATH/DLL
requirements for the retained binary. Icarus remains optional for `--rtl`.
See [customer setup](CUSTOMER_GUIDE.md) for troubleshooting. Manual and historical
setup instructions below remain available for other installations.

Target: SystemC 2.3.4, a compatible C++14 compiler/runtime, CMake, and Python 3.9+
for the CLI and trace checks. Icarus `iverilog`/`vvp` enables RTL comparison and
the full integration test suite. Use the same compiler family, architecture, runtime,
and C++ standard for SystemC and the pilot. Do not link an MSVC SystemC library
into a MinGW executable, or mix incompatible Debug/Release runtime libraries.

## Existing SystemC 2.3.4 installation

The current workspace has a qualified installation at
`.deps/systemc-2.3.4-install`, with the CLI build at `build-234`. See
[CLI](CLI.md). For a fresh MSYS2 UCRT64 build, the following local setup was
exercised successfully (the assembly preprocessor flag handles the source's
conditional ELF-only GNU-stack directive on native Windows):

```powershell
git clone --depth 1 --branch 2.3.4 https://github.com/accellera-official/systemc.git .deps/systemc-2.3.4
cmake -S .deps/systemc-2.3.4 -B .deps/systemc-2.3.4-build -G Ninja '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_CXX_STANDARD=14' '-DBUILD_SHARED_LIBS=OFF' '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON' '-DCMAKE_POLICY_VERSION_MINIMUM=3.5' '-DCMAKE_CXX_COMPILER=C:/msys64/ucrt64/bin/g++.exe' '-DCMAKE_ASM_FLAGS=-x assembler-with-cpp' '-DCMAKE_INSTALL_PREFIX=D:/TLM_Performance_Modeling/.deps/systemc-2.3.4-install'
cmake --build .deps/systemc-2.3.4-build --parallel 4
cmake --install .deps/systemc-2.3.4-build
python -m tlm_lab build --systemc-prefix .deps/systemc-2.3.4-install --compiler C:/msys64/ucrt64/bin/g++.exe
ctest --test-dir build-234 --output-on-failure
```

The checkout was commit `5fc1469339775b54b1fcc2020ac744a58be5b50e`;
the source was not patched. Only use that assembly flag with GCC-compatible
toolchains. The source's Pthreads option is unsupported on native Windows;
leave it disabled. The older compatibility setup below is historical.

From this workspace, set the prefix to your own installation containing
`lib/cmake/SystemCLanguage`. The path below is illustrative:

```powershell
cmake -S . -B build-234 -G Ninja '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_PREFIX_PATH=C:/path/to/systemc-2.3.4-install'
cmake --build build-234 --parallel 4
ctest --test-dir build-234 --output-on-failure
python tools/check_pilot_traces.py build-234/traces
```

For MSVC, run from its developer shell and use your installed Visual Studio
generator; build with `--config Release` and run CTest with `-C Release`.
The target-version check accepts SystemC's appended release-date version suffix.

## Workspace-local SystemC build

Obtain the official [2.3.4 source release](https://github.com/accellera-official/systemc/tree/2.3.4)
and extract into `.deps/systemc-2.3.4`. Follow its included installation notes.
Example for a compiler and Ninja already on PATH:

```powershell
$localPrefix = Join-Path (Get-Location) '.deps/systemc-2.3.4-install'
cmake -S .deps/systemc-2.3.4 -B .deps/systemc-2.3.4-build -G Ninja '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_CXX_STANDARD=14' '-DBUILD_SHARED_LIBS=OFF' '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON' "-DCMAKE_INSTALL_PREFIX=$localPrefix"
cmake --build .deps/systemc-2.3.4-build --parallel 4
cmake --install .deps/systemc-2.3.4-build
cmake -S . -B build-234 -G Ninja '-DCMAKE_BUILD_TYPE=Release' "-DCMAKE_PREFIX_PATH=$localPrefix"
cmake --build build-234 --parallel 4
ctest --test-dir build-234 --output-on-failure
python tools/check_pilot_traces.py build-234/traces
```

If a new CMake rejects the release's older policy baseline, consult its diagnostic;
`'-DCMAKE_POLICY_VERSION_MINIMUM=3.5'` may be needed when configuring SystemC.
Quote decimal-valued `-D` arguments in Windows PowerShell. Do not suppress the
SystemC API-version check to work around a C++ ABI mismatch; rebuild compatibly.

## Local compatibility check performed during initialization

The attempted GitHub archive download failed with a network connection error.
Existing sources at `C:/systemc/systemc-2.3.3` were built into this workspace and
installed under `.deps/systemc-2.3.3-install`. No existing SystemC installation
was modified. The currently configured `build/` uses that library with an explicit
override, not the target release:

```powershell
cmake -S . -B build -G Ninja '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_PREFIX_PATH=D:/TLM_Performance_Modeling/.deps/systemc-2.3.3-install' '-DTLM_LAB_ALLOW_UNQUALIFIED_SYSTEMC=ON'
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
python tools/check_pilot_traces.py build/traces
```

This override is for compatibility checks only. Use a fresh build directory and
the default version guard for 2.3.4 validation. See [validation status](VALIDATION.md).

