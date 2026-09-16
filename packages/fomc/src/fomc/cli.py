"""`fomc` — unified command-line entry point for the research lab.

Thin dispatcher: each subcommand delegates to its module's own main(argv), so the
per-command options are exactly what `python -m fomc.<module> --help` shows.

    fomc status                 # current regime + SPY/TLT playbook
    fomc regime --at 2024-06-01
    fomc truth                  # rebuild the source-truth table
    fomc dips                   # buy-the-dip cohort
    fomc backtest --horizon 5
    fomc study
    fomc fetch --since 2018-01-01
    fomc speeches --speakers powell
    fomc warsh
"""

from __future__ import annotations

import sys

from fomc import (
    backtest,
    dip_analysis,
    event_study,
    export_truth,
    fetch,
    regime,
    speeches,
    status,
    truth,
    warsh,
)

# command -> (one-line help, module.main). ORDER controls help/listing order.
COMMANDS = {
    "status": ("Current regime + SPY/TLT playbook for the next meeting", status.main),
    "regime": ("Show the hiking/easing regime timeline", regime.main),
    "truth": ("Build the per-event SPY/TLT source-truth table (CSV + MD)", truth.main),
    "export-truth": ("Export event-truth CSV+JSON for the dashboard", export_truth.main),
    "study": ("Event study: SPY/TLT 5d before & after each FOMC", event_study.main),
    "dips": ("Deep-dive the 'SPY fell on decision day' cohort", dip_analysis.main),
    "backtest": ("Backtest the decision-day reversal rules", backtest.main),
    "fetch": ("Fetch FOMC statements / minutes / SEP / press-conf", fetch.main),
    "speeches": ("Fetch Fed speeches & testimony by speaker", speeches.main),
    "warsh": ("Fetch curated free Warsh primary-text sources", warsh.main),
}
ORDER = list(COMMANDS)


def _print_help() -> None:
    print("fomc — FOMC / Warsh-vs-Powell SPY-TLT research lab\n")
    print("usage: fomc <command> [options]\n")
    print("commands:")
    for c in ORDER:
        print(f"  {c:12s} {COMMANDS[c][0]}")
    print("\nrun 'fomc <command> --help' for a command's options")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"fomc: unknown command {cmd!r}\n", file=sys.stderr)
        _print_help()
        return 2
    return COMMANDS[cmd][1](rest) or 0


if __name__ == "__main__":
    raise SystemExit(main())
