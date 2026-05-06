"""``python -m witness.schema.generate`` — regenerate trace_v1.json on disk."""
from __future__ import annotations

from witness.schema import write_schema_file


def main() -> int:
    p = write_schema_file()
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
