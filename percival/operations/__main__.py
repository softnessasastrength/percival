"""Run: python -m percival.operations [--poll 60 --count 3]"""
import argparse
from .health import render_json, report
from .poller import poll


def main(argv=None):
    parser = argparse.ArgumentParser(description="Percival local read-only health checks")
    parser.add_argument("--poll", type=float, default=60, help="Seconds between checks (minimum 5)")
    parser.add_argument("--count", type=int, default=1, help="Number of checks; no indefinite polling")
    args = parser.parse_args(argv)
    poll(args.poll, iterations=args.count, emit=lambda checks: print(render_json(checks), flush=True))


if __name__ == "__main__":
    main()
