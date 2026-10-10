"""Acyclic requests shared by syntax caches and language-resolution policies."""

from dataclasses import dataclass

from tree_sitter import Node

from ..domain.models import Call, ParsedFile, Symbol


@dataclass(frozen=True)
class ImportRequest:
    """One import directive or member lookup at its lexical location."""

    file: ParsedFile
    path: str
    position: int | None = None
    source: str = ""


@dataclass(frozen=True)
class ResolutionRequest:
    """A name lookup in the lexical context of a parsed call."""

    file: ParsedFile
    call: Call
    owner: Symbol | None
    name: str
    qualifier: str | None = None


@dataclass(frozen=True)
class CallTarget:
    """Normalized syntax and spelling of a callable target."""

    callee: Node | None
    receiver: Node | None
    name: str
    qualifier: str | None


@dataclass(frozen=True)
class DeclarationLookup:
    name: str
    node: Node
    position: int


FUNCTIONS = {
    "function_definition",
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
    "method_declaration",
    "constructor_declaration",
    "function_item",
    "lambda",
    "lambda_expression",
    "lambda_literal",
    "closure_expression",
    "func_literal",
    "method",
    "singleton_method",
}
SCOPES = FUNCTIONS | {
    "class_definition",
    "class_declaration",
    "class_specifier",
    "struct_specifier",
    "block",
    "statement_block",
    "compound_statement",
    "do_block",
}
