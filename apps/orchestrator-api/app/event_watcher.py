from __future__ import annotations

import logging

from app.db import init_db
from app.services.event_watcher_service import EventWatcherService


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [event-watcher] %(message)s",
    )
    init_db()
    EventWatcherService().run_forever()


if __name__ == "__main__":
    main()
