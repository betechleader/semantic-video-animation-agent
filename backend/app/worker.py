"""Entrypoint for the optional persistent local worker."""

import signal

from .execution import PersistentWorker
from .logging_config import configure_logging


def main() -> None:
    configure_logging()
    worker = PersistentWorker()
    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), lambda *_args: worker.stop())
    worker.run_forever()


if __name__ == "__main__":
    main()
