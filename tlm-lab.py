"""Run from any directory without installation or pip dependencies."""
import sys
if sys.version_info < (3, 9):
    print("TLM Performance Lab needs Python 3.9 or newer. Install Python, then run this launcher again.", file=sys.stderr)
    raise SystemExit(2)
from tlm_lab.cli import main
raise SystemExit(main())
