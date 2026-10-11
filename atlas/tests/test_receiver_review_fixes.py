"""Receiver review regressions: mutation safety and inherent impl identity."""

import pytest

from tests.test_receiver_safety import assert_target
from tests.test_semantic_resolution import call_edges, repository


@pytest.mark.parametrize("language,path,source", [
    ("typescript", "app.ts", "class Service {persist(){}} class Other {persist(){}} function run(local:Service){local=new Other();local.persist();}"),
    ("tsx", "app.tsx", "class Service {persist(){}} class Other {persist(){}} function run(local:Service){local=new Other();local.persist();}"),
    ("java", "App.java", "class Service {void persist(){}} class Other extends Service {void persist(){}} class App {void run(Service local){local=new Other();local.persist();}}"),
    ("kotlin", "App.kt", "open class Service {open fun persist(){}} class Other: Service() {override fun persist(){}} fun run(local:Service){local=Other();local.persist()}"),
])
def test_reassigned_declared_receiver_is_not_trusted(language, path, source):
    assert_target(language, {path: source}, "local.persist()", False)


@pytest.mark.parametrize("language,path,source,evidence", [
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef run(holder:Holder):\n holder.service=other\n holder.service.persist()", "holder.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef run(holder:Holder):\n alias=holder\n alias.service=other\n holder.service.persist()", "holder.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef run(holder:Holder):\n alias=holder\n second=alias\n second.service=other\n holder.service.persist()", "holder.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef run(holder:Holder):\n alias:Holder=holder\n holder.service=other\n alias.service.persist()", "alias.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef run(holder:Holder):\n alias=holder.service\n alias.persist=other\n holder.service.persist()", "holder.service.persist()"),
    ("javascript", "app.js", "class Service {persist(){}} class Holder {service=new Service()} function run(){const holder=new Holder(); holder.service=other; holder.service.persist();}", "holder.service.persist()"),
    ("javascript", "app.js", "class Service {persist(){}} class Holder {service=new Service()} function run(){const holder=new Holder(); const alias=holder; alias.service=other; holder.service.persist();}", "holder.service.persist()"),
])
def test_caller_field_writes_invalidate_receiver(language, path, source, evidence):
    assert_target(language, {path: source}, evidence, False)


@pytest.mark.parametrize("language,sources", [
    ("python", {"tools.py": "class Service:\n def persist(self):pass", "app.py": "from tools import Service as Alias, Service\nAlias.persist=other\ndef run(local:Service):\n local.persist()"}),
    ("typescript", {"tools.ts": "export class Service {persist(){}}", "app.ts": "import {Service as Alias, Service} from './tools'; Alias.prototype.persist=other; function run(local:Service){local.persist();}"}),
    ("tsx", {"tools.tsx": "export class Service {persist(){}}", "app.tsx": "import {Service as Alias, Service} from './tools'; Alias.prototype.persist=other; function run(local:Service){local.persist();}"}),
    ("python", {"tools.py": "class Service:\n def persist(self):pass", "app.py": "import tools\nfrom tools import Service\ntools.Service.persist=other\ndef run(local:Service):\n local.persist()"}),
])
def test_member_mutation_follows_imported_class_identity(language, sources):
    assert_target(language, sources, "local.persist()", False)


@pytest.mark.parametrize("language,path,source,evidence", [
    ("typescript", "app.ts", "class Service {persist(){}} function run(local:Service){local.persist();}", "local.persist()"),
    ("tsx", "app.tsx", "class Service {persist(){}} function run(local:Service){local.persist();}", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\ndef unrelated(holder):\n holder.service=other\ndef run(holder:Holder):\n holder.service.persist()", "holder.service.persist()"),
    ("javascript", "app.js", "class Service {persist(){}} class Holder {service=new Service()} function run(){const holder=new Holder(); holder.service.persist();}", "holder.service.persist()"),
])
def test_unchanged_receivers_remain_internal(language, path, source, evidence):
    assert_target(language, {path: source}, evidence, True)


@pytest.mark.parametrize("implementation", [
    "use service::Service; impl Service {fn persist(&self){}}",
    "impl service::Service {fn persist(&self){}}",
    "mod implementation {use crate::service::Service; impl Service {pub fn persist(&self){}}}",
])
def test_rust_impl_in_another_module_resolves_identity(implementation):
    sources = {"service.rs": "pub struct Service{}", "main.rs":
               "mod service; " + implementation + " fn run(local:&service::Service){local.persist();}"}
    assert_target("rust", sources, "local.persist()", True)


def test_rust_same_short_name_impl_is_not_used():
    sources = {
        "service.rs": "pub struct Service{}",
        "other.rs": "pub struct Service{} impl Service {pub fn persist(&self){}}",
        "main.rs": "mod service; mod other; use service::Service; fn run(local:&Service){local.persist();}",
    }
    assert_target("rust", sources, "local.persist()", False)


def test_rust_duplicate_impl_members_are_ambiguous():
    sources = {
        "service.rs": "pub struct Service{} impl Service {pub fn persist(&self){}}",
        "main.rs": "mod service; use service::Service; impl Service {fn persist(&self){}} fn run(local:&Service){local.persist();}",
    }
    assert_target("rust", sources, "local.persist()", False)


def test_rust_trait_impl_is_not_an_inherent_member():
    sources = {
        "service.rs": "pub struct Service{}",
        "main.rs": "mod service; use service::Service; trait Saving {fn persist(&self);} impl Saving for Service {fn persist(&self){}} fn run(local:&Service){local.persist();}",
    }
    assert_target("rust", sources, "local.persist()", False)


def test_java_constructor_subtype_field_write_is_not_trusted():
    source = "class Service {void persist(){}} class Other extends Service {void persist(){}} class App {Service local; App(){this.local=new Other();} void run(){local.persist();}}"
    assert_target("java", {"App.java": source}, "local.persist()", False)


def test_rust_impl_target_is_the_actual_method():
    sources = {"service.rs": "pub struct Service{}", "main.rs":
               "mod service;use service::Service;impl Service{fn persist(&self){}} fn run(local:&Service){local.persist();}"}
    repo = repository("rust", sources)
    edges = call_edges(repo, "local.persist()")
    targets = {symbol.key: symbol for symbol in repo.symbols}
    assert len(edges) == 1
    target = targets[edges[0].target_key]
    assert (target.file_path, target.name) == ("main.rs", "persist")
