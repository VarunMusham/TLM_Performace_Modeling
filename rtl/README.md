# RTL reference boundary

No RTL implementation is included yet. The next step is an independent clocked
WDT reference and monitor based on the reviewed [WDT specification](../docs/WDT_SPEC.md).
Export transaction commits, expiry, IRQ, and reset request with named clock-domain
cycles. A comparison must use equivalent bus timing and offered register traffic.

Store source-controlled monitor/reference code here when implemented. Keep
generated waveforms and traces under ignored run directories. Passing the C++
pilot tests alone is not evidence of RTL agreement.

