"""Independent original-order contracts for retained import and setup cases."""

from pathlib import Path

import pytest

from tests.import_snapshot_support import IMPORT_PATHS, import_case_sources, write_import_case
from tests.source_snapshot_fixture import CASE_ROOT

# Original dictionary/project order, traced from HEAD tests, not the loader/catalog.
ORDERS = {
    "extraction-integration-rust-relative-module-paths-keep-their-declared-identity": ["main.rs", "recipe.rs", "recipe/report.rs"],
    "jsx-intrinsics-jsx": ["Card.jsx", "App.jsx"],
    "jsx-intrinsics-tsx": ["Card.tsx", "App.tsx"],
    "python-project-imports-comma-separated-module-imports": ["src/app/__init__.py", "main.py", "src/app/worker.py", "src/app/other.py"],
    "python-project-imports-ordinary-module-cannot-have-child-modules-1": ["main.py", "app.py", "app/worker.py"],
    "python-project-imports-ordinary-module-cannot-have-child-modules-2": ["main.py", "app.py", "app/worker.py"],
    "python-project-imports-runtime-modules-take-precedence-over-type-stubs-1": ["src/app/__init__.py", "main.py", "src/app/worker.py", "src/app/worker.pyi"],
    "python-project-imports-runtime-modules-take-precedence-over-type-stubs-2": ["src/app/__init__.py", "main.py", "src/app/worker/__init__.py", "src/app/worker/__init__.pyi"],
    "python-project-imports-unrelated-suffix-is-not-an-import-root": ["main.py", "examples/requests.py"],
    "rust-root-streaming-fallback-root-references-are-merged-incrementally": ["root.rs", "child.rs", "child/leaf.rs"],
    "selective-import-python": ["tools.py", "main.py"],
    "selective-import-typescript": ["tools.ts", "main.ts"],
    "tsx-coffee-lowercase-namespaces-and-nonletter-component-names": ["Card.tsx", "App.tsx"],
    "jooq-response-factory": ["QueueApi.kt", "ChannelRepository.kt"],
    "namespace-1": ["tools/worker.go", "app.go"],
    "namespace-2": ["tools/worker.go", "app.go"],
    "namespace-5": ["tools.ts", "app.ts"],
    "namespace-6": ["tools.js", "app.js"],
    "namespace-shadow-1": ["tools.ts", "app.ts"],
    "namespace-shadow-2": ["tools.ts", "app.ts"],
    "namespace-shadow-3": ["tools.ts", "app.ts"],
    "namespace-ambiguous-1": ["a.ts", "b.ts", "app.ts"],
    "namespace-ambiguous-2": ["a.ts", "b.ts", "app.ts"],
    "call-resolution-ambiguous-bare-call-stays-external": ["a.ts", "b.ts", "app.ts"],
    "import-resolution-package-import-with-multiple-files": ["tools/a.go", "tools/b.go", "app.go"],
    "indexer-indexes-polyglot-symbols-and-connections": ["helper.ts", "service.ts", "main.go", "App.java", "App.kt", "app.ex"],
    "indexer-builds-module-file-type-and-callable-views": ["core/helper.ts", "api/service.ts"],
    "indexer-discovers-large-and-non-programming-language-files": ["payload.json", "notes.md", "node_modules/ignored.ts"],
}


@pytest.mark.parametrize("case_id", ORDERS)
def test_original_import_source_order(case_id: str) -> None:
    assert list(import_case_sources("imports", case_id)) == ORDERS[case_id]


@pytest.mark.parametrize("case_id", ORDERS)
def test_import_materialization_order(tmp_path: Path, monkeypatch, case_id: str) -> None:
    paths = []
    original = Path.write_bytes

    def record(path: Path, data: bytes) -> int:
        paths.append(path.relative_to(tmp_path).as_posix())
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", record)
    write_import_case(tmp_path, case_id)
    assert paths == ORDERS[case_id]


def test_import_order_catalog_covers_setup_cases_and_exact_paths() -> None:
    root = CASE_ROOT / "imports"
    assert set(IMPORT_PATHS) == {path.name for path in root.iterdir() if path.is_dir()}
    for case_id, paths in IMPORT_PATHS.items():
        actual = import_tree_paths(root / case_id)
        assert len(paths) == len(set(paths))
        assert set(paths) == actual


def import_tree_paths(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
