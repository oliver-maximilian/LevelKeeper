"""CLI entrypoint.

Works both as a long-running container (internal scheduler loop, when
run_interval is configured) and as a one-shot invocation for host-cron style
scheduling (`docker compose run levelkeeper` or `--once`).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from levelkeeper.archiver import Archiver
from levelkeeper.config import ConfigError, load_config
from levelkeeper.logging_setup import setup_logging
from levelkeeper.notifier import Notifier
from levelkeeper.scheduler import parse_interval, run_forever
from levelkeeper.state import StateStore

DEFAULT_CONFIG_PATH = "/config/config.toml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="levelkeeper")
    parser.add_argument("--config", default=None, help="path to config TOML file")
    parser.add_argument(
        "--once", action="store_true", help="run a single pass and exit, ignoring run_interval"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="force dry-run mode regardless of configuration"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config or os.environ.get("LEVELKEEPER_CONFIG_FILE", DEFAULT_CONFIG_PATH)

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"levelkeeper: configuration error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        config.dry_run = True

    setup_logging(config.log_level, config.log_format)
    logger = logging.getLogger("levelkeeper")
    logger.info(
        "starting levelkeeper (dry_run=%s, archive_root=%s)", config.dry_run, config.archive_root
    )

    notifier = Notifier(config)
    state = StateStore(config.state_path)
    archiver = Archiver(config, notifier, state)

    if args.once:
        interval = None
    else:
        try:
            interval = parse_interval(config.run_interval)
        except ValueError as exc:
            logger.error("invalid run_interval: %s", exc)
            return 2

    if interval is None:
        archiver.run()
        return 0

    stop = {"flag": False}

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("received signal %s, shutting down after current run", signum)
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("internal scheduler active, run_interval=%ss", interval)
    run_forever(archiver.run, interval, lambda: stop["flag"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
