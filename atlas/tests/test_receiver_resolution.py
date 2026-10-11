"""Receiver fixtures use each grammar, not a shared source-text approximation."""

import pytest

from tests.test_semantic_resolution import repository, call_edges


CASES = {
    "java": ("App.java", "class Service { void persist() {} } class App { Service orderService; App(Service orderService) { this.orderService = orderService; } void run(Service parameter) { Service local = new Service(); orderService.persist(); this.orderService.persist(); parameter.persist(); local.persist(); } }"),
    "kotlin": ("App.kt", "class Service { fun persist() {} }\nclass App(private val orderService: Service) { fun run(parameter: Service) { val local: Service = Service(); orderService.persist(); this.orderService.persist(); parameter.persist(); local.persist() } }"),
    "typescript": ("app.ts", "class Service { persist() {} } class App { constructor(private orderService: Service) {} run(parameter: Service) { const local: Service = new Service(); this.orderService.persist(); parameter.persist(); local.persist(); } }"),
    "tsx": ("app.tsx", "class Service { persist() {} } function run(parameter: Service) { const local: Service = new Service(); parameter.persist(); local.persist(); }"),
    "python": ("app.py", "class Service:\n def persist(self): pass\ndef run(parameter: Service):\n local: Service = Service()\n parameter.persist()\n local.persist()\n"),
    "go": ("app.go", "package main\ntype Service struct{}\nfunc (s *Service) persist() {}\nfunc run(parameter *Service) { var local *Service; parameter.persist(); local.persist() }"),
    "rust": ("app.rs", "struct Service {} impl Service { fn persist(&self) {} } fn run(parameter: &Service) { let local: Service = Service {}; parameter.persist(); local.persist(); }"),
    "javascript": ("app.js", "class Service { persist() {} } function run() { const local = new Service(); local.persist(); }"),

}


@pytest.mark.parametrize("language", CASES)
def test_declared_receivers(language):
    path, source = CASES[language]
    repo = repository(language, {path: source})
    edges = [e for e in call_edges(repo) if e.evidence and ".persist()" in e.evidence]
    assert edges
    assert all(e.target_key.startswith("symbol:") and "persist" in e.target_key for e in edges), edges


@pytest.mark.parametrize("language", CASES)
def test_unknown_receiver_never_uses_member_name(language):
    path, source = CASES[language]
    source = source.replace("local.persist()", "unknown.persist()")
    repo = repository(language, {path: source})
    edges = call_edges(repo, "unknown.persist()")
    assert edges
    assert all(e.target_key.startswith("external:") for e in edges)


@pytest.mark.parametrize("language, path, source", [
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run():\n local = Service()\n local = other\n local.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } function run() { let local = new Service(); local = other; local.persist(); }"),
    ("typescript", "app.ts", "class Service { persist() {} } function run() { let local = new Service(); local = other; local.persist(); }"),
])
def test_reassigned_inferred_receiver_stays_external(language, path, source):
    edges = call_edges(repository(language, {path: source}), "local.persist()")
    assert edges and all(e.target_key.startswith("external:") for e in edges)


def test_elixir_has_module_calls_not_instance_members():
    repo = repository("elixir", {"app.ex": "defmodule Service do\n def persist(), do: :ok\nend\ndefmodule App do\n def run(service) do\n  Service.persist()\n  service.persist()\n end\nend"})
    modules = call_edges(repo, "Service.persist()")
    dynamic = call_edges(repo, "service.persist()")
    assert modules and all(e.target_key.startswith("symbol:") for e in modules)
    assert dynamic and all(e.target_key.startswith("external:") for e in dynamic)
