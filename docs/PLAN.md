# Platform development plan

The authoritative developer handoff starts at [docs index](README.md).
The product is a Windows-first CLI platform for performance analysis and RTL
correlation of existing hybrid SystemC IPs, then multi-IP architecture exploration.
Target families are UALink, UCIe and PCIe, with WDT as the base validation fixture.
The user confirmed this order and deferred UI; Linux remains a future port.

## Current state and next objective

The inspected `43ba848` baseline implements the WDT CLI workflow on SystemC 2.3.4,
including an independent reference and recorded tests. The code still encodes WDT
timing, serial workloads and metrics. See [gap analysis](GAP_ANALYSIS.md).

The next production objective is one supplied link-IP profile with reproducible
builds, preserved timing, concurrent workloads, resource-aware performance metrics
and independently qualified RTL comparison. Generic infrastructure and a synthetic
credit-link fixture can progress before real-IP access; they do not fulfill the
real-IP qualification gate.

## Development sequence

1. Inspect model/RTL code using the [IP intake](templates/IP_INTAKE.md).
2. Implement versioned contracts and a reusable adapter SDK while preserving WDT.
3. Generalize workload concurrency, observation, metrics and correlation.
4. Qualify one real link over latency, saturation, contention and holdout cases.
5. Qualify additional profiles, then explicit multi-IP paths and shared resources.
6. Add architecture exploration; scope UI and calibrated power separately later.

See [roadmap](ROADMAP.md) for gates/effort, [backlog](BACKLOG.md) for implementation
tickets, and [verification](VERIFICATION_PLAN.md) for acceptance evidence.
The [requirements](PRODUCT_REQUIREMENTS.md) define comparable capabilities to
Platform Architect without asserting broad product parity or invented percentages.
Exact protocol revisions, interfaces, probes and RTL availability remain intake
questions; no production model has been assumed from its family name.
