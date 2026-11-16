# References

Checked 2026-11-17. Normative API behavior should be checked against the version
used by the production models; the project conventions are separately documented.

- [Accellera TLM-2.0 language reference manual](https://www.accellera.org/images/downloads/standards/systemc/TLM_2_0_LRM.pdf):
  transport interfaces, timing annotations, protocol behavior, and PEQ utilities.
- [Accellera SystemC 2.3.4 source](https://github.com/accellera-official/systemc/tree/2.3.4):
  the selected implementation release; use its build/install instructions.
- [Accellera SystemC reference implementation](https://github.com/accellera-official/systemc):
  official implementation repository.
- [Synopsys Platform Architect](https://www.synopsys.com/verification/virtual-prototyping/platform-architect.html):
  product scope used to distinguish the focused platform's initial requirements.

No proprietary protocol specification or production IP source has been supplied.
The WDT register map, scenarios, and architecture in this folder are project
design proposals, not claims about any vendor's WDT or link implementation.

## Development roadmap source register

Checked 2026-11-17. Public vendor/consortium summaries establish product scope
and document availability; they do not replace licensed normative specifications
or the user's actual model/RTL contract. Implementation decisions and estimates
in this pack are engineering proposals, not claims made by these sources.

| Source | Use in this pack | Limit |
|---|---|---|
| [Synopsys Platform Architect overview](https://www.synopsys.com/verification/virtual-prototyping/platform-architect.html) | Capability categories: modeling, workloads, analysis, exploration, CLI/UI | No independent speed/accuracy/parity benchmark |
| [Synopsys multi-die datasheet](https://www.synopsys.com/content/dam/synopsys/verification/datasheets/platform-architect-multi-die-ds.pdf) | Multi-die and die-to-die model scope, including UCIe | Does not qualify our models |
| [UALink specification catalog](https://ualinkconsortium.org/specification/) | Family has versioned specifications/options; intake selects implemented set | No assumed production model revision or optional-function support |
| [UCIe specifications](https://www.uciexpress.org/specifications) | Die-to-die layer/mapping scope and versioned documents | Exact rate/width/flow-control policy comes from selected specification/model |
| [PCI-SIG PCI Express Base catalog](https://pcisig.com/specification-overview/pci-express-base) | Revision/errata provenance for PCIe profile | Protocol constants/options require owner-provided normative evidence |

Avoid a `latest` protocol default: standards and model implementations evolve
independently. Pin document title, revision and relevant errata in every profile.
Restricted documents and production code are not reproduced in this repository.

