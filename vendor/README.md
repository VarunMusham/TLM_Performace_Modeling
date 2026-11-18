# Offline dependency source

`systemc/systemc-2.3.4.tar.gz` is an unmodified source archive of the official
Accellera SystemC repository at the revision in `systemc/dependency.json`.
Its SHA-256 is checked before extraction. The archive preserves upstream source,
license and notices; readable copies of LICENSE and NOTICE are alongside it.

`python tlm-lab.py setup-wdt` builds this source locally. It does not download or
install system-wide packages. CMake, a matching C++ compiler and the selected build
tool must already be available. The Python-only demo does not use this dependency.

Python, compilers, commercial simulators and their licenses are not bundled.
Customer adapters reuse the tools required by the customer's own source/testbench.
