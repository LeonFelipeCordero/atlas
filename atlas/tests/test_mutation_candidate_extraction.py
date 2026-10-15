"""Raw-byte mutation extraction contracts, without indexing or persistence."""

import hashlib
from pathlib import Path

import pytest

from atlas.domain.models import SourceFile
from atlas.parsing.mutation_candidates import extract_candidates


def source(text: str | bytes, language: str = "python", path: str = "sample.py") -> SourceFile:
    return SourceFile(path=path, absolute_path=Path("/tmp") / path, language=language, source=text.encode() if isinstance(text, str) else text)


@pytest.mark.parametrize(("language", "text"), [
    ("python", "def f(x):\n if x > 0 and not x: return x + 1\n"),
    ("javascript", "function f(x){if(x > 0 && !x) return x + 1;}"),
    ("typescript", "function f(x: number){if(x > 0 && !x) return x + 1;}"),
    ("tsx", "function f(x: number){return x > 0 && !x ? <b>{x + 1}</b> : null;}"),
    ("java", "class A { int f(int x){if(x > 0 && !(x == 2)) return x + 1; return 0;} }"),
    ("kotlin", "fun f(x:Int) { if(x > 0 && !false) println(x + 1) }"),
    ("rust", "fn f(x:i32){if x > 0 && !false { let y = x + 1; }}"),
    ("go", "package p\nfunc f(x int){if x > 0 && !false { x = x + 1 }}"),
    ("elixir", "def f(x) do\n if x > 0 && !false, do: x + 1\nend"),
])
def test_supported_adapters(language: str, text: str) -> None:
    analysis = extract_candidates(source(text, language))
    assert {item.kind for item in analysis.candidates} >= {"condition", "comparison", "logical", "arithmetic"}
    assert all(item.callable is not None and item.callable.name == "f" for item in analysis.candidates)


def test_exact_bytes_and_determinism() -> None:
    file = source('def café(é):\n if é > 0:\n  return f"é{é + 1}"\n')
    first = extract_candidates(file)
    assert first.model_dump() == extract_candidates(file).model_dump()
    assert first.candidates
    for item in first.candidates:
        assert file.source[item.span.startByte:item.span.endByte].decode() == item.originalText
        assert file.source[item.expressionSpan.startByte:item.expressionSpan.endByte].decode() == item.expressionText
        assert item.sourceHash == hashlib.sha256(file.source).hexdigest()
        line = file.source.splitlines()[item.span.startLine - 1]
        assert line[item.span.startColumn - 1:].startswith(item.originalText.splitlines()[0].encode())
        assert item.expressionSpan.startByte <= item.span.startByte < item.span.endByte <= item.expressionSpan.endByte
    greater = next(item for item in first.candidates if item.operator == ">")
    assert greater.span.startColumn == 8
    assert len({item.id for item in first.candidates}) == len(first.candidates)
    assert {item.id for item in first.candidates}.isdisjoint(item.id for item in extract_candidates(source(file.source, path="other.py")).candidates)


def test_python_multiword_and_chained_operators() -> None:
    analysis = extract_candidates(source("if a is   not b and a not in c and 0 < a <= 2: pass\n"))
    operators = [item for item in analysis.candidates if item.kind != "condition"]
    assert [item.operator for item in operators] == ["is not", "and", "not in", "and", "<", "<="]
    assert operators[0].originalText == "is   not"
    assert operators[0].expressionText == "a is   not b"
    assert [item.expressionText for item in operators[-2:]] == ["0 < a <= 2"] * 2


@pytest.mark.parametrize(("language", "text", "condition"), [
    ("javascript", "for(let i=0; i<2; i++) {}", "i<2"),
    ("java", "class A { void f(){ for(int i=0; i<2; i++) {} } }", "i<2"),
    ("go", "package p\nfunc f(){for i:=0;i<2;i++ {}}", "i<2"),
    ("go", "package p\nfunc f(x int){for x>0 {}}", "x>0"),
    ("kotlin", "fun f(x:Int){while(x>0){}; do {} while(x<2)}", "x>0"),
    ("python", "x = a if b else c\n", "b"),
])
def test_condition_shapes(language: str, text: str, condition: str) -> None:
    analysis = extract_candidates(source(text, language))
    assert condition in [item.originalText for item in analysis.candidates if item.kind == "condition"]


@pytest.mark.parametrize(("language", "text"), [
    ("python", 'for x in xs:\n pass\ns = "a > b and a + b" # x + 2\n'),
    ("python", 'x: tuple[int, 1 + 2]\ndef f(x: tuple[int, 1 + 2]) -> tuple[int, 1 + 2]: pass\n'),
    ("javascript", 'for (const x of xs) {} const s="a > b"; const r=/a+b/; // a + b'),
    ("typescript", 'type X<T> = T extends number ? 1 : 2; const s="a + b";'),
    ("kotlin", 'fun f(){for(x in xs){}; val s="a + b"}'),
    ("rust", 'fn f(){for x in xs {} let s="a + b";}'),
    ("go", 'package p\nfunc f(){for range xs {} }'),
    ("elixir", 'x = "a + b"\ny = ~r/a+b/'),
])
def test_exclusions(language: str, text: str) -> None:
    analysis = extract_candidates(source(text, language))
    assert not analysis.candidates


@pytest.mark.parametrize(("language", "text"), [
    ("python", 's = f"x={a + 1}"'),
    ("javascript", 'const s=`x=${a + 1}`;'),
    ("tsx", 'const s=<div>{a + 1}</div>;'),
    ("javascript", 'const s=<div>{a + 1}</div>;'),
    ("kotlin", 'val s="x=${a + 1}"'),
    ("elixir", 's = "x=#{a + 1}"'),
])
def test_runtime_interpolation(language: str, text: str) -> None:
    analysis = extract_candidates(source(text, language))
    assert [(item.kind, item.originalText) for item in analysis.candidates] == [("arithmetic", "+")]


def test_elixir_truthy_conditions_and_strict_guards() -> None:
    analysis = extract_candidates(source("def f(x) when x > 0 do\n unless x, do: x || 1\nend", "elixir"))
    assert [item.originalText for item in analysis.candidates if item.kind == "condition"] == ["x > 0", "x"]
    assert [(item.operator, item.kind) for item in analysis.candidates if item.operator == "||"] == [("||", "logical")]


def test_rust_let_chains_are_not_boolean_conditions() -> None:
    analysis = extract_candidates(source("fn f(x:Option<i32>){if let Some(y) = x && y > 0 {} }", "rust"))
    assert not analysis.candidates


@pytest.mark.parametrize(("text", "language"), [
    (b"if a > \xff: pass", "python"),
    ("if (", "python"),
    ("a + b", "unsupported"),
])
def test_unanalyzable_sources_have_no_candidates(text: str | bytes, language: str) -> None:
    assert not extract_candidates(source(text, language)).candidates


def test_operator_sites_are_distinct_from_conditions() -> None:
    analysis = extract_candidates(source("if a > b: pass"))
    assert [(item.kind, item.originalText) for item in analysis.candidates] == [("condition", "a > b"), ("comparison", ">")]


@pytest.mark.parametrize(("language", "text"), [
    ("python", "x += 2"),
    ("javascript", "x += 2;"),
    ("typescript", "x += 2;"),
    ("tsx", "x += 2;"),
    ("java", "class A { void f(){x += 2;} }"),
    ("kotlin", "fun f(){x += 2}"),
    ("rust", "fn f(){x += 2;}"),
    ("go", "package p\nfunc f(){x += 2}"),
])
def test_compound_assignment(language: str, text: str) -> None:
    analysis = extract_candidates(source(text, language))
    assert [(item.kind, item.operator) for item in analysis.candidates] == [("assignment", "+=")]


def test_elixir_quoted_and_attribute_syntax_is_not_runtime() -> None:
    analysis = extract_candidates(source("quote do\n if x > 0, do: x + 1\nend\n@type t :: 1 + 2", "elixir"))
    assert not analysis.candidates


@pytest.mark.parametrize(("language", "text"), [
    ("elixir", 'x = "a" <> "b"'),
    ("elixir", "x = a <<< 2"),
    ("javascript", "x = a & b;"),
    ("python", "x = a << 1"),
])
def test_unsupported_operators_are_excluded(language: str, text: str) -> None:
    assert not extract_candidates(source(text, language)).candidates


@pytest.mark.parametrize(("language", "text"), [
    ("rust", "fn f(p: &i32) { let x = *p; }"),
    ("go", "package p\nfunc f(p *int){x := *p}"),
])
def test_pointer_dereference_is_not_multiplication(language: str, text: str) -> None:
    assert not extract_candidates(source(text, language)).candidates


def test_elixir_zero_arity_callable_name() -> None:
    analysis = extract_candidates(source("def f, do: x + 1", "elixir"))
    assert analysis.candidates[0].callable is not None
    assert analysis.candidates[0].callable.name == "f"


@pytest.mark.parametrize("definition", ["defmacro", "defmacrop"])
def test_elixir_macro_definitions_are_not_runtime(definition: str) -> None:
    analysis = extract_candidates(source(f"{definition} f(x), do: x + 1", "elixir"))
    assert not analysis.candidates


def test_elixir_patterns_are_not_arithmetic_expressions() -> None:
    analysis = extract_candidates(source("def f(-1), do: 2 + 1\ncase x do\n -1 -> x + 1\nend", "elixir"))
    assert [item.operator for item in analysis.candidates] == ["+", "+"]


def test_rust_const_generic_and_array_types_are_not_runtime() -> None:
    analysis = extract_candidates(source("fn f<const N: usize>() { let a: [i32; 1 + 2]; let b = f::<{1+2}>(); }", "rust"))
    assert not analysis.candidates


def test_python_match_guard_is_condition_not_pattern() -> None:
    analysis = extract_candidates(source("match x:\n case -1: pass\n case y if y > 0: pass\n"))
    assert [(item.kind, item.originalText) for item in analysis.candidates] == [("condition", "y > 0"), ("comparison", ">")]


def test_kotlin_when_patterns_are_not_arithmetic() -> None:
    analysis = extract_candidates(source("fun f(x:Int){when(x){-1 -> x+1; else -> 0}}", "kotlin"))
    assert [item.operator for item in analysis.candidates] == ["+"]


def test_jsx_text_is_not_expression_syntax() -> None:
    analysis = extract_candidates(source("const x=<p>a + b &gt; c {a+b}</p>;", "tsx"))
    assert [item.operator for item in analysis.candidates] == ["+"]


def test_nearest_callable_context() -> None:
    analysis = extract_candidates(source("def outer(x):\n def inner(y):\n  return y + 1\n return x - 1\n"))
    assert [(item.operator, item.callable.name if item.callable else None) for item in analysis.candidates] == [("+", "inner"), ("-", "outer")]
    assert analysis.candidates[0].callable is not None
    assert analysis.candidates[0].callable.originalText == "def inner(y):\n  return y + 1"
