"""Fresh-review receiver mutation, initializer and Rust owner regressions."""

import pytest

from tests.test_receiver_safety import assert_target


@pytest.mark.parametrize("case", [
    ("javascript", "app.js", "class Service {persist(){}} class Holder {service=new Service();run(){const alias=this;alias.service=other;this.service.persist();}}", "this.service.persist()"),
    ("typescript", "app.ts", "class Service {persist(){}} class Holder {service:Service;run(){const alias=this;alias.service=other;this.service.persist();}}", "this.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Holder:\n service:Service\n def run(self):\n  alias=self\n  alias.service=other\n  self.service.persist()", "self.service.persist()"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist(){}\ntype Holder struct{service *Service}\nfunc run(holder *Holder){alias:=holder;alias.service=other;holder.service.persist()}", "holder.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self):pass\nclass Inner:\n service:Service\nclass Holder:\n inner:Inner\n def run(self):\n  alias=self.inner\n  alias.service=other\n  self.inner.service.persist()", "self.inner.service.persist()"),
])
def test_alias_field_mutation(case):
    language, path, source, evidence = case
    assert_target(language, {path: source}, (evidence, False))


@pytest.mark.parametrize("language_case", [("javascript", "js"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("target", ["Alias.prototype.persist", "local.persist"])
@pytest.mark.parametrize("operation", ["&&=replacement", "||=replacement", "??=replacement", "+=replacement", "++"])
def test_script_member_write_forms(language_case, target, operation):
    language, extension = language_case
    sources = {
        f"service.{extension}": "export class Service {persist(){}}",
        f"app.{extension}": f"import {{Service as Alias, Service}} from './service'; function run(){{const local=new Service();{target}{operation};local.persist();}}",
    }
    assert_target(language, sources, ("local.persist()", False))


@pytest.mark.parametrize("language,extension", [("python", "py"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("same", [False, True])
def test_annotated_constructor_initializer_identity(language, extension, same):
    initializer = "Service" if same else "Other"
    source = (f"class Service:\n def persist(self):pass\nclass Other:\n def persist(self):pass\ndef run():\n local:Service={initializer}()\n local.persist()" if language == "python" else
              f"class Service {{persist(){{}}}} class Other extends Service {{persist(){{}}}} function run(){{const local:Service=new {initializer}();local.persist();}}")
    assert_target(language, {f"app.{extension}": source}, ("local.persist()", same))


@pytest.mark.parametrize("language,extension", [("python", "py"), ("typescript", "ts"), ("tsx", "tsx")])
@pytest.mark.parametrize("same", [False, True])
def test_annotated_identifier_initializer_identity(language, extension, same):
    initializer = "Service" if same else "Other"
    source = (f"class Service:\n def persist(self):pass\nclass Other:\n def persist(self):pass\ndef run():\n other={initializer}()\n local:Service=other\n local.persist()" if language == "python" else
              f"class Service {{persist(){{}}}} class Other {{persist(){{}}}} function run(){{const other=new {initializer}();const local:Service=other;local.persist();}}")
    assert_target(language, {f"app.{extension}": source}, ("local.persist()", same))


@pytest.mark.parametrize("language,sources", [
    ("python", {"service.py": "class Service:\n def persist(self):pass", "app.py": "from service import Service, Service as Alias\ndef run():\n local:Service=Alias()\n local.persist()"}),
    ("typescript", {"service.ts": "export class Service {persist(){}}", "app.ts": "import {Service, Service as Alias} from './service';function run(){const local:Service=new Alias();local.persist();}"}),
    ("java", {"App.java": "class Service {void persist(){}} class Other extends Service {void persist(){}} class App {void run(Service local){local.persist();}}"}),
    ("kotlin", {"app.kt": "open class Service {open fun persist(){}}\nclass Other:Service(){override fun persist(){}}\nfun run(local:Service){local.persist()}"}),
])
def test_import_alias_identity_and_static_parameter_types(language, sources):
    assert_target(language, sources, ("local.persist()", True))


@pytest.mark.parametrize("kind,declaration", [("struct", "{}"), ("enum", "{One}")])
@pytest.mark.parametrize("qualified", [False, True])
def test_rust_self_impl_identity(kind, declaration, qualified):
    implementation = "impl service::Service" if qualified else "use service::Service; impl Service"
    sources = {"service.rs": f"pub {kind} Service{declaration}", "main.rs":
               f"mod service; {implementation} {{fn persist(&self){{}} fn run(&self){{self.persist();}}}}"}
    assert_target("rust", sources, ("self.persist()", True))


@pytest.mark.parametrize("language,path,source", [
    ("rust", "app.rs", "struct Service{} impl Service{fn persist(&self){}} fn run(local:Service){local+=other;local.persist();}"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist(){}\nfunc run(local *Service){local+=other;local.persist()}"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist(){}\nfunc run(local *Service){local++;local.persist()}"),
    ("java", "App.java", "class Service {void persist(){}} class App {void run(Service local){local++;local.persist();}}"),
    ("kotlin", "app.kt", "class Service {fun persist(){}} fun run(local:Service){local++;local.persist()}"),
    ("kotlin", "app.kt", "class Service {fun persist(){}} fun run(local:Service){++local;local.persist()}"),
])
def test_compound_receiver_assignment(language, path, source):
    assert_target(language, {path: source}, ("local.persist()", False))
