from pathlib import Path
import sys

import alembic.config

here = Path(__file__).parent


def main() -> None:
    argv = [
        # Use our custom config path
        "--config",
        str(here / "alembic.ini"),
        "--raiseerr",
        "upgrade",
        "head",
    ]
    alembic.config.main(argv=argv)  # type: ignore
