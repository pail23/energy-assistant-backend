from pathlib import Path
import sys

import alembic.config

here = Path(__file__).parent


def main():
    argv = [
        # Use our custom config path
        "--config",
        str(here / "alembic.ini"),
        "--raiseerr",
        "upgrade",
        "head",
        # Forward all other arguments to alembic as is
        *sys.argv[1:],
    ]
    alembic.config.main(argv=argv)
