from typing import Any
def rows(artifact: dict[str, Any]):
    return [dict(item) for item in artifact['nodes']]