"""Shared logging and error wrapper. In a script:

    from lib.common import run

    def main(log):
        log.info("working")

    if __name__ == "__main__":
        run(main)
"""
import logging
import os
import sys


def setup(name=None):
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    return logging.getLogger(name or os.path.basename(sys.argv[0]))


def run(main):
    log = setup()
    try:
        sys.exit(main(log) or 0)
    except KeyboardInterrupt:
        log.error("interrupted")
        sys.exit(130)
    except Exception as e:
        log.error("%s", e)
        log.debug("traceback", exc_info=True)
        sys.exit(1)
