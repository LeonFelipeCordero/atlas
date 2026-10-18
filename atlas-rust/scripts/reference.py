"""Developer-only Python oracle. Never linked to or called by the native runtime."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID


def main() -> None:
    mode, *args = sys.argv[1:]
    if mode == "seed":
        from atlas.persistence.database import migrate_database
        from atlas.persistence.repositories import repository_store
        database, root = map(Path, args)
        migrate_database(database)
        from atlas.persistence import repositories
        repositories.uuid4 = lambda: UUID("00000000-0000-4000-8000-000000000001")
        with repository_store(database) as store:
            store.register(root.name, str(root))
    elif mode == "historical":
        from lifecycle import historical
        historical(Path(os.environ["DATABASE_PATH"]), args[0], Path(args[1]))
    elif mode == "migrate":
        from atlas.persistence.database import main as migrate
        sys.argv = ["atlas-migrate", "migrate", *args]
        migrate()
    elif mode == "cli":
        from atlas.cli import main as cli
        fixture = os.environ.get("ATLAS_PARITY_UUID")
        if fixture:
            from atlas.persistence import repositories
            repository = os.environ.get("ATLAS_PARITY_REPOSITORY_UUID")
            identities = iter([repository, fixture] if repository else [fixture])
            repositories.uuid4 = lambda: UUID(next(identities))
        cli(args=args, prog_name="atlas")
    else:
        raise SystemExit(f"Unknown reference operation: {mode}")


if __name__ == "__main__":
    main()
