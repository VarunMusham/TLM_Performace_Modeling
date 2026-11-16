# Runtime configuration examples

`wdt_scenario.example.json` is a runnable version-1 scenario.
`adapter_contract.example.json` is the registered WDT contract and
`sweep.example.json` is a 16-experiment generated-workload matrix.
The strict validator is [config.py](../tlm_lab/config.py). It rejects unknown
fields, invalid timing and unsupported capabilities. Tick strings preserve
precision across JSON consumers. See [CLI](../docs/CLI.md).

The scenario covers setup, pre-decrement COUNT read, and first expiry. The legacy
fixed CTest `expiry` case also reads and clears status afterward.

