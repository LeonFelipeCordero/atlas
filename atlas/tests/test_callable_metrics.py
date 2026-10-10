"""Physical source spans and grammar-backed declared input counts."""

from pathlib import Path

import pytest
from tree_sitter_language_pack import get_parser

from atlas.metrics.adapters import get_metric_adapter
from atlas.bootstrap import repository_service
from atlas.domain.models import ParsedFile, SourceFile, Symbol
from atlas.metrics.callables import callable_metrics
from atlas.parsing.parser import parse_file
from atlas.indexer import analyze_repository
from atlas.persistence.database import migrate_database


def parsed(language: str, code: str):
    file = parse_file(SourceFile("sample", Path("sample"), language, code.encode()))
    callable_metrics(file)
    return file


@pytest.mark.parametrize(
    ("language", "code", "expected"),
    [
        ("python", "def f(a=call(1, 2), /, *args, b=0, **kwargs): pass", [4]),
        ("python", "x = lambda a, b=call(1, 2), *args: a", [3]),
        ("python", "class C:\n    def f(*args: int, a=1,b=2,c=3,d=4,e=5,f=6,g=7): pass\n    def g(**kwargs: int): pass", [8, 1]),
        ("javascript", "function f({a,b}, [x,y], z=call(1,2), ...args) {}", [4]),
        (
            "javascript",
            "const f = x => x; const g = () => 0; class C { m(a,b) {} }",
            [1, 0, 2],
        ),
        (
            "typescript",
            "function f<T>(this: C, {a,b}: X, c?: T, ...args: T[]): void;",
            [3],
        ),
        (
            "typescript",
            "interface C { m<T>(this: C, x: T): void; cb: (a: X, b: Y) => Z; }",
            [1, 2],
        ),
        ("tsx", "const f = ({a,b}: Props) => <div>{a}</div>;", [1]),
        (
            "go",
            "package p\nfunc (r R) f(a,b int, c ...string) {}\nvar g = func(int, string) {}",
            [3, 2],
        ),
        ("rust", "trait C { fn f<T>(&self, (a,b): (i32,i32), c: T); }", [2]),
        ("rust", "impl C { fn f(self: Box<Self>, x: i32) {} }", [1]),
        ("rust", "fn f(#[allow(unused_variables)] a:i32,b:i32,c:i32,d:i32,e:i32,f:i32,g:i32) {}", [7]),
        ("rust", 'extern "C" { fn f(x: i32, ...); }', [2]),
        ("rust", "fn f() { let g = |(a,b), c| a; }", [0, 2]),
        ("java", "interface C { <T> void f(int a, String... b); }", [2]),
        ("java", "class C { void f() { F g = (a,b) -> a; F h = x -> x; } }", [0, 2, 1]),
        ("kotlin", "fun <T> X.f(a: Int, vararg b: T): Int", [2]),
        ("kotlin", "val f = { (a,b): X, c: Int -> c }; val g = { -> 0 }", [2, 0]),
        ("kotlin", "val f = fun(a: Int, b: Int): Int { return a }", [2]),
        ("elixir", r"def f({a,b}, c \\ call(1,2)) when a > 0, do: c", [2]),
        (
            "elixir",
            "def zero, do: 0\nx = fn a,b when a > 0 -> a end\ny = fn -> 0 end",
            [0, 2, 0],
        ),
    ],
)
def test_parameter_counts(language, code, expected):
    file = parsed(language, code)
    assert file.parse_error is None
    callables = [
        symbol for symbol in file.symbols if symbol.kind in {"function", "method"}
    ]
    assert [symbol.parameter_count for symbol in callables] == expected
    assert all(symbol.line_count == 1 for symbol in callables)


def test_python_receivers_only_in_methods():
    code = """def f(self, cls): pass
class C:
    def m(self: C, x):
        def inner(self, cls): pass
    @classmethod
    def c(cls, x): pass
    @staticmethod
    def s(self, cls): pass
    def v(*self): pass
    def renamed(me, a,b,c,d,e,f,g): pass
    @classmethod
    def renamed_class(klass, a,b,c,d,e,f,g): pass
    @staticmethod # explanation
    def commented_static(self, a,b,c,d,e,f,g): pass
"""
    symbols = parsed("python", code).symbols
    counts = {
        symbol.name: symbol.parameter_count
        for symbol in symbols
        if symbol.kind == "function"
    }
    assert counts == {
        "f": 2, "m": 1, "inner": 2, "c": 1, "s": 2, "v": 1,
        "renamed": 7, "renamed_class": 7, "commented_static": 8,
    }
    assert next(symbol for symbol in symbols if symbol.name == "m").line_count == 2


def test_comments_separators_and_annotations_are_not_inputs():
    assert (
        parsed(
            "python",
            "def f(a, # comma, comment\n *, b: tuple[int, int] = (1,2)) -> tuple[int,int]: pass",
        )
        .symbols[0]
        .parameter_count
        == 2
    )
    assert (
        parsed(
            "typescript",
            "function f<T,U>(a: Map<T,U>, /* , */ b = [1,2]): [T,U] { return b; }",
        )
        .symbols[0]
        .parameter_count
        == 2
    )


def test_unknown_counts_are_not_zero():
    assert (
        parsed("kotlin", "val f = { println(it) }").symbols[0].parameter_count is None
    )
    adapter = get_metric_adapter("python")
    malformed = (
        get_parser("python").parse(b"def f(a,,b): pass").root_node.named_children[0]
    )
    assert adapter.parameter_count(malformed) is None
    assert (
        get_metric_adapter("ruby").parameter_count(
            get_parser("ruby").parse(b"def f(x); end").root_node.named_children[0]
        )
        is None
    )


def test_elixir_clauses_keep_identity_and_counts():
    file = parsed("elixir", "def f(0, x), do: x\ndef f(n, x) when n > 0, do: x\n")
    assert [(symbol.name, symbol.parameter_count) for symbol in file.symbols] == [
        ("f", 2),
        ("f", 2),
    ]
    assert len({symbol.key for symbol in file.symbols}) == 2
    assert (
        get_metric_adapter("elixir").parameter_count(
            get_parser("elixir")
            .parse(b"fn a -> a; a,b -> a end")
            .root_node.named_children[0]
        )
        is None
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"", 0),
        (b"x", 1),
        (b"x\n", 1),
        (b"\n", 1),
        (b"x\n\n", 2),
        (b"# a\r\n# b\r\n", 2),
    ],
)
def test_file_physical_lines(tmp_path, content, expected):
    (tmp_path / "file.py").write_bytes(content)
    graph = analyze_repository(tmp_path)
    node = next(node for node in graph.nodes if node["type"] == "file")
    assert node["properties"]["lineCount"] == expected


def test_unknown_parameter_property_is_omitted(tmp_path):
    (tmp_path / "sample.rb").write_text("def f(x); x; end\n")
    graph = analyze_repository(tmp_path)
    callable_node = next(
        node for node in graph.nodes if node["type"] in {"function", "method"}
    )
    assert callable_node["properties"]["lineCount"] == 1
    assert "parameterCount" not in callable_node["properties"]


def test_end_exclusive_column_zero_and_nested_physical_lines():
    code = "def outer(a):\n\n    def inner(b):\n        return b\n    return inner(a)\n"
    file = parsed("python", code)
    assert [(symbol.line_count, symbol.parameter_count) for symbol in file.symbols] == [
        (5, 1),
        (2, 1),
    ]
    symbol = Symbol(
        "key",
        "sample",
        "python",
        "f",
        "f",
        "function",
        "file:sample",
        0,
        6,
        1,
        1,
        3,
        1,
        None,
        None,
        [],
    )
    synthetic = ParsedFile(
        SourceFile("sample", Path("sample"), "python", b"a\nb\nc"),
        "hash",
        None,
        [symbol],
    )
    callable_metrics(synthetic)
    assert symbol.line_count == 2


def test_metrics_survive_snapshot_persistence(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "sample.py").write_text(
        "def f(a, b=0):\n    return a\n\ndef zero(): pass\n"
    )
    path = tmp_path / "db.sqlite"
    migrate_database(path)
    with repository_service(path) as service:
        repository = service.register(
            {"name": "Callable metrics", "location": str(root)}
        )
        graph = service.index(repository.name, root)
    fresh = analyze_repository(root)
    expected = {node["stableKey"]: node["properties"] for node in fresh.nodes}
    with repository_service(path) as service:
        saved = service.get_architecture(repository.id)
        assert saved == graph
        facts = service.repository.report_facts(repository.id)
        assert facts is not None
        for node in facts.nodes:
            assert node.lineCount == expected[node.stableKey].get("lineCount")
            assert node.parameterCount == expected[node.stableKey].get("parameterCount")
            assert node.cyclomaticComplexity == expected[node.stableKey].get("cyclomaticComplexity")
