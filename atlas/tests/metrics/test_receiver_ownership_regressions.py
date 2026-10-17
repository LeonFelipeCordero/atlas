"""Real-parser regressions for direct field ownership and lexical self writes."""

from pathlib import Path

import pytest

from atlas.domain.models import SourceFile
from atlas.metrics.resolution_contract import ResolutionRequest
from atlas.metrics.resolver import CallResolver
from atlas.parsing.parser import parse_files


def resolver_for(language, source):
    return CallResolver(parse_files([SourceFile("sample", Path("/sample"), language, source.encode())]))


@pytest.mark.parametrize(("language", "source"), [
    ("python", """
class Client:
    def run(self): pass
class Outer:
    client: Client
    class Inner:
        client: Client

def use(outer: Outer):
    outer.client.run()
"""),
    ("java", """
class Client { void run() {} }
class Outer {
    Client client;
    class Inner { Client client; }
}
class Use { void use(Outer outer) { outer.client.run(); } }
"""),
    ("kotlin", """
class Client { fun run() {} }
class Outer {
    val client: Client = Client()
    class Inner { val client: Client = Client() }
}
fun use(outer: Outer) { outer.client.run() }
"""),
])
def test_nested_class_field_does_not_make_outer_field_ambiguous(language, source):
    resolver = resolver_for(language, source)
    call = next(c for c in resolver.repository.calls if c.name == "run")

    assert [s.qualified_name for s in resolver.resolve(call, resolver.owner(call))] == ["sample::Client.run"]


@pytest.mark.parametrize("statement", ["self = object()", "self: object = object()"])
def test_nested_function_self_assignment_has_its_own_lexical_owner(statement):
    resolver = resolver_for("python", f"""
class Client:
    def run(self): pass
    def use(self):
        def nested():
            {statement}
        self.run()
""")
    call = next(c for c in resolver.repository.calls if c.name == "run")

    assert [s.qualified_name for s in resolver.resolve(call, resolver.owner(call))] == ["sample::Client.run"]


@pytest.mark.parametrize(("statement", "written"), [
    ("self = object()", False),
    ("nonlocal self; self = object()", True),
    ("global self; self = object()", True),
    ("self.run = replacement", True),
    ("alias = self; alias.run = replacement", True),
    ("other = object()", False),
])
def test_nested_local_write_filter_keeps_nonlocal_global_and_member_writes(statement, written):
    resolver = resolver_for("python", f"""
class Client:
    def use(self):
        def nested():
            {statement}
        self.run()
""")
    call = next(c for c in resolver.repository.calls if c.name == "run")
    request = ResolutionRequest(resolver.files["sample"], call, resolver.owner(call), "run", "self")

    assert resolver.receivers._path_written(request) is written


def test_javascript_nested_identifier_assignment_is_not_a_python_local_write():
    resolver = resolver_for("javascript", """
function use(service) {
    function nested() { service = replacement; }
    service.run();
}
""")
    call = next(c for c in resolver.repository.calls if c.name == "run")
    request = ResolutionRequest(resolver.files["sample"], call, resolver.owner(call), "run", "service")

    assert resolver.receivers._path_written(request) is True


def test_nested_java_method_write_can_still_invalidate_outer_field():
    resolver = resolver_for("java", """
class Client { void run() {} }
class Outer {
    Client client;
    class Inner { void reset(Client replacement) { client = replacement; } }
}
class Use { void use(Outer outer) { outer.client.run(); } }
""")
    call = next(c for c in resolver.repository.calls if c.name == "run")

    assert resolver.resolve(call, resolver.owner(call)) == []


def test_outer_class_cannot_borrow_nested_class_field():
    resolver = resolver_for("python", """
class Client:
    def run(self): pass
class Outer:
    class Inner:
        client: Client

def use(outer: Outer):
    outer.client.run()
""")
    call = next(c for c in resolver.repository.calls if c.name == "run")

    assert resolver.resolve(call, resolver.owner(call)) == []
