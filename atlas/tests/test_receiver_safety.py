"""Negative receiver inference and existing identity-safety contracts."""

import pytest

from tests.test_semantic_resolution import repository, call_edges


def assert_target(language, sources, evidence, internal):
    edges = call_edges(repository(language, sources), evidence)
    assert edges, evidence
    assert all(e.target_key.startswith("symbol:" if internal else "external:") for e in edges), edges


@pytest.mark.parametrize("language, path, source, evidence", [
    ("python", "app.py", "class Service:\n def persist(self): pass\nclass App:\n def __init__(self, injected: Service):\n  self.service = injected\n def run(self):\n  self.service.persist()", "self.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\nclass App:\n def __init__(self):\n  self.service = Service()\n def run(self):\n  self.service.persist()", "self.service.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } class App { constructor() { this.service = new Service(); } run() { this.service.persist(); } }", "this.service.persist()"),
    ("javascript", "app.jsx", "class Service { persist() {} } class App { service = new Service(); run() { this.service.persist(); } }", "this.service.persist()"),
    ("java", "App.java", "class Service { void persist() {} } class App { void run() { var local = new Service(); local.persist(); } }", "local.persist()"),
    ("java", "App.java", "class Service { void persist() {} } class App { static Service local; static void run(){ local.persist(); } }", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\nclass App:\n service: Service\n def run(self):\n  self.service.persist()", "self.service.persist()"),
    ("kotlin", "App.kt", "class Service { fun persist() {} }\nfun run() { val local = Service(); local.persist() }", "local.persist()"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist() {}\ntype App struct{ service *Service }\nfunc(a *App) run(){ a.service.persist() }", "a.service.persist()"),
    ("rust", "app.rs", "struct Service {} impl Service { fn persist(&self) {} } struct App { service: Service } impl App { fn run(&self) { self.service.persist(); } }", "self.service.persist()"),
])
def test_constructor_and_field_receivers(language, path, source, evidence):
    assert_target(language, {path: source}, evidence, True)


@pytest.mark.parametrize("language, path, source, evidence", [
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run(local: Service):\n local = other\n local.persist()", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef Service(): return other\ndef run():\n local = Service()\n local.persist()", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run():\n local.persist()\n local: Service = Service()", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run():\n if condition:\n  local = Service()\n local.persist()", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run():\n if condition:\n  local: Service = Service()\n local.persist()", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\nclass App:\n def __init__(self):\n  self.service = Service()\n def run(self):\n  self.service = other\n  self.service.persist()", "self.service.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\nclass App:\n def __init__(self):\n  self.service = Service()\n def run(self):\n  self = other\n  self.service.persist()", "self.service.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } class App { constructor(){ this.service = new Service(); } run(){ this.service = other; this.service.persist(); } }", "this.service.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } function run(){ const local = new Service(); local.persist = other; local.persist(); }", "local.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } function run(){ let local = new Service(); local++; local.persist(); }", "local.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } function run(){ let local = new Service(); [local] = others; local.persist(); }", "local.persist()"),
    ("python", "app.py", "class Service:\n def persist(self): pass\ndef run():\n local = Service()\n local, other = others\n local.persist()", "local.persist()"),
    ("javascript", "app.js", "class Service { persist() {} } function run(){ const local = new Service(); function nested(local){ local.persist(); } }", "local.persist()"),
    ("typescript", "app.ts", "class Service { persist() {} } class Other { persist() {} } function run(local: Service | Other){ local.persist(); }", "local.persist()"),
    ("java", "App.java", "class Service { void persist() {} } class App { Service local; static void run(){ local.persist(); } }", "local.persist()"),
    ("java", "App.java", "class Service { void persist() {} void persist(int x) {} } class App { void run(Service local){ local.persist(); } }", "local.persist()"),
    ("java", "App.java", "class Service { void persist() {} } class App { Service local; void run(Unknown local){ local.persist(); } }", "local.persist()"),
    ("kotlin", "App.kt", "class Service { fun persist() {} } class App(local: Service) { fun run(){ local.persist() } }", "local.persist()"),
    ("rust", "app.rs", "struct Service {} impl Service { fn persist(&self) {} } fn run(local: Unknown){ local.persist(); }", "local.persist()"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist() {}\nfunc run(local interface{}) { local.persist() }", "local.persist()"),
    ("go", "app.go", "package main\ntype Service struct{}\nfunc(s *Service) persist() {}\nfunc run(local *Service) { if condition { local := other; local.persist() } }", "local.persist()"),
])
def test_unsafe_receivers_stay_external(language, path, source, evidence):
    assert_target(language, {path: source}, evidence, False)


@pytest.mark.parametrize("language, sources, evidence", [
    ("java", {"service/OrderService.java": "package service; public class OrderService { public void saveOrder(int order) {} }", "app/App.java": "package app; import service.OrderService; class App { private final OrderService orderService; App(OrderService orderService){ this.orderService = orderService; } void run(){ orderService.saveOrder(1); } }"}, "orderService.saveOrder(1)"),
    ("kotlin", {"service/OrderService.kt": "package service\nclass OrderService { fun persist(order: Int) {} }", "app/App.kt": "package app\nimport service.OrderService\nclass App { @Inject private lateinit var orderService: OrderService; fun run(){ orderService.persist(1) } }"}, "orderService.persist(1)"),
    ("python", {"tools.py": "class Service:\n def persist(self): pass", "app.py": "import tools\ndef run(local: tools.Service):\n local.persist()"}, "local.persist()"),
    ("typescript", {"tools.ts": "export class Service { persist() {} }", "app.ts": "import * as tools from './tools'; function run(local: tools.Service){ local.persist(); }"}, "local.persist()"),
    ("go", {"tools/tools.go": "package tools\ntype Service struct{}\nfunc(s *Service) persist() {}", "app.go": "package main\nimport \"tools\"\nfunc run(local *tools.Service){ local.persist() }"}, "local.persist()"),
    ("rust", {"tools.rs": "pub struct Service {} impl Service { pub fn persist(&self) {} }", "main.rs": "mod tools; fn run(local: &tools::Service){ local.persist(); }"}, "local.persist()"),
])
def test_type_visibility_follows_import_and_namespace_context(language, sources, evidence):
    assert_target(language, sources, evidence, True)


@pytest.mark.parametrize("language, sources", [
    ("python", {"tools.py": "class Service:\n def persist(self): pass", "app.py": "from tools import Service as Alias\nAlias.persist = other\ndef run():\n local = Alias()\n local.persist()"}),
    ("javascript", {"tools.js": "export class Service { persist() {} }", "app.js": "import {Service as Alias} from './tools'; Alias.prototype.persist = other; function run(){ const local = new Alias(); local.persist(); }"}),
])
def test_imported_receiver_member_rebinding_is_not_ignored(language, sources):
    assert_target(language, sources, "local.persist()", False)


def test_exchange_broker_constructor_injected_websocket_client():
    sources = {
        "service/OrderService.java": "package service; public class OrderService { public Order saveOrder(Order order){ return order; } }",
        "client/OrderCreatedWebSocketClient.java": "package client; public class OrderCreatedWebSocketClient { public void sendAndWait(Event event) {} }",
        "handler/OrderCreatedHandler.java": """package handler;
import service.OrderService;
import client.OrderCreatedWebSocketClient;
class OrderCreatedHandler {
 private final OrderService orderService;
 private final OrderCreatedWebSocketClient orderCreatedWebSocketClient;
 @Inject OrderCreatedHandler(OrderService orderService, OrderCreatedWebSocketClient orderCreatedWebSocketClient) {
  this.orderService = orderService;
  this.orderCreatedWebSocketClient = orderCreatedWebSocketClient;
 }
 void onMessage(Order order, Event event) {
  Order savedOrder = orderService.saveOrder(order);
  orderCreatedWebSocketClient.sendAndWait(event);
 }
}""",
    }
    assert_target("java", sources, "orderService.saveOrder(order)", True)
    assert_target("java", sources, "orderCreatedWebSocketClient.sendAndWait(event)", True)


def test_unrelated_constructor_assignments_are_separate_scopes():
    source = "class Service:\n def persist(self): pass\nclass App:\n def __init__(self):\n  self.service = Service()\n def run(self):\n  self.service.persist()\nclass Other:\n def __init__(self):\n  self.service = unknown"
    assert_target("python", {"app.py": source}, "self.service.persist()", True)


def test_unimported_type_is_not_guessed_globally():
    sources = {"tools.py": "class Service:\n def persist(self): pass", "app.py": "def run(local: Service):\n local.persist()"}
    assert_target("python", sources, "local.persist()", False)
