
import json
import sys
from pathlib import Path
from atlas.indexer import analyze_repository
artifact = analyze_repository(Path(sys.argv[1]))
print(json.dumps({"stats": artifact.stats,
                  "files": [n["path"] for n in artifact.nodes if n["kind"] == "file"],
                  "relationships": sorted({e["type"] for e in artifact.edges})}))
