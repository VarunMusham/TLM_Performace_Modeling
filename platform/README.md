# Planned platform components

Implementation reserved for the experiment runner, configuration validation,
canonical events, metric calculations, RTL comparison, and reports. See
[architecture](../docs/ARCHITECTURE.md). These components are not implemented yet.

Proposed command flow: validate scenario -> build/resolve simulator -> run ->
analyze -> correlate -> report. Each stage records its version and input hashes.
Do not expose these as working commands until implemented and tested.

