# Draft configuration examples

These JSON files make the proposed runner/adapter contract reviewable. They are
not runtime configuration for the fixed C++ pilot and have no production schema
validator yet. Integer ticks are strings to preserve precision across future
web/JSON consumers. Unresolved RTL references remain explicitly null.

The minimal scenario covers setup and first expiry. The CTest `expiry` case
additionally reads and clears status after that observation. A future runner
must reject missing required parameters, unsupported adapter features, and
unresolved correlation references when a correlation run is requested.

