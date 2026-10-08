"""Acyclic lexical-syntax contract shared by syntax caches and language policies."""

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
