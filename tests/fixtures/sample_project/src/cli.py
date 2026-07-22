"""CLI (fixture baseline) using argparse."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sample")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("seed", help="Seed the database with demo users")
    sub.add_parser("purge", help="Remove all users")
    return parser
