# Qualification record template

Status: UNKNOWN / uncorrelated / inconclusive / fail / pass. Copy per profile and
qualification attempt; preserve previous records. A template is not approval.

| Field | Value |
|---|---|
| Record ID, date, requirement/release gate | UNKNOWN |
| Adapter/model revision and build manifest hash | UNKNOWN |
| Protocol document revision/options and modeled boundary | UNKNOWN |
| RTL revision, simulator/exporter and importer hashes | UNKNOWN |
| Clock/resolution/reset and synchronization markers | UNKNOWN |
| Workload/generator versions, seeds, offered/feedback semantics | UNKNOWN |
| Configuration envelope (ranges and excluded combinations) | UNKNOWN |
| Measurement/warm-up/drain and capture prerequisites | UNKNOWN |
| KPI endpoints/populations/units and policy ID/hash | UNKNOWN |
| Numeric bounds, ordering constraints, sample/precision requirements | UNKNOWN |
| Calibration set / held-out set / reason for selection | UNKNOWN |
| Exact/build/environment reproducibility evidence | UNKNOWN |
| Known omissions, inaccessible probes and consequences | UNKNOWN |
| Decision owners and review evidence | UNKNOWN |

| Case ID | Family/config/seed | Artifact hashes/locations | Execution/evidence | KPI/accuracy verdict | Mismatch/action |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Required negative controls: shifted timing, missing and duplicate observations,
allowed independent reordering, forbidden causal reorder, wrong units/clock epoch,
payload/tag reuse, lost credit return, censored tail and baseline mismatch.

Qualification applies only to recorded mechanisms/configurations and KPI bounds.
Requalification triggers: changed timing/resource/ordering/reset behavior,
changed compiler/runtime with observed semantic impact, new protocol options,
changed workloads outside the envelope, new importer or capture semantics, or
changed policy. State which prior evidence remains reusable and why.
