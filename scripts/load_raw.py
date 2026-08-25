"""Load the source CSVs into the `raw` schema.

Run from the repository root:

    uv run python scripts/load_raw.py
"""

from delivery_risk.database import get_session
from delivery_risk.ingestion import ingest


def main() -> None:
    with get_session() as session:
        ingest(session)
        session.commit()
    print("\ndone")


if __name__ == "__main__":
    main()
