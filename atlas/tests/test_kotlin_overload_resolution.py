"""Injected Kotlin services select only syntactically provable overloads."""

from functools import cache

import pytest

from tests.import_project_support import assert_external, edges_at, project_repository, symbols

CALLER = "exchange/OrderMatchingService.kt"
SERVICES = "exchange/OrderServices.kt"


@cache
def persistence_repository():
    return project_repository("kotlin", "overloaded-persistence")


@pytest.mark.parametrize("evidence,method,parameter", [
    ("openOrderService.persist(ordersToPersist)", "OpenOrderService.persist", "openOrders: List<OpenOrder>"),
    ("matchedOrderService.persist(matchedOrders)", "MatchedOrderService.persist", "matchedOrders: List<MatchedOrder>"),
    ("openOrderService.persist(order)", "OpenOrderService.persist", "openOrder: OpenOrder"),
    ("openOrderService.record()", "OpenOrderService.record", "()"),
    ("openOrderService.record(order)", "OpenOrderService.record", "order: OpenOrder)"),
    ("openOrderService.record(order, true)", "OpenOrderService.record", "filled: Boolean"),
    ("orderService.markOrdersAsFilled(filledOrders)", "OrderService.markOrdersAsFilled", "orders: List<OpenOrder>"),
    ("openOrderSemaphoreService.release(ordersToDelete)", "OpenOrderSemaphoreService.release", "orders: List<OpenOrder>"),
])
def test_injected_services_choose_exact_overload(evidence, method, parameter):
    repo = persistence_repository()
    target, = [symbol for symbol in symbols(repo, SERVICES, method) if parameter in (symbol.signature or "")]
    edge, = edges_at(repo, CALLER, evidence)
    assert edge.target_key == target.key


@pytest.mark.parametrize("evidence", [
    "openOrderService.persist(unknown)",
    "openOrderService.persist(inferredOrders)",
    "openOrderService.persist(orders)",
    "openOrderService.persist(changed)",
    "openOrderService.persist(openOrders = orders)",
    "openOrderService.persist(*orders)",
    "openOrderService.persist { orders }",
    "openOrderService.persist()",
])
def test_unsupported_or_shadowed_calls_stay_external(evidence):
    assert_external(persistence_repository(), CALLER, evidence)


@pytest.mark.parametrize("evidence", [
    "service.broad(order)", "service.inherited(derived)", "service.nullable(orders)",
    "service.nullable(maybe)", "service.defaults(order)", "service.spread(order)",
    "service.generic(orders)", "service.collection(projected)", "service.mutable(changed)",
])
def test_unsupported_candidates_are_not_eliminated(evidence):
    assert_external(persistence_repository(), "exchange/OverloadSafety.kt", evidence)


@pytest.mark.parametrize("evidence,method,parameter", [
    ("service.collection(orders)", "collection", "List<OpenOrder>"),
    ("service.collection(matched)", "collection", "List<MatchedOrder>"),
    ("service.returned(orders)", "returned", "List<OpenOrder>"),
])
def test_final_collection_elements_and_return_annotations(evidence, method, parameter):
    repo = persistence_repository()
    path = "exchange/OverloadSafety.kt"
    target, = [s for s in symbols(repo, path, "OverloadSafety." + method) if parameter in (s.signature or "")]
    edge, = edges_at(repo, path, evidence)
    assert edge.target_key == target.key


@pytest.mark.parametrize("argument,parameter", [("order", "openOrder: OpenOrder"), ("orders", "List<OpenOrder>")])
def test_import_aliases_and_qualified_list_types(argument, parameter):
    repo = persistence_repository()
    target, = [s for s in symbols(repo, SERVICES, "OpenOrderService.persist") if parameter in (s.signature or "")]
    edge, = edges_at(repo, "intake/AliasedPersistence.kt", f"service.persist({argument})")
    assert edge.target_key == target.key


def test_type_alias_and_generic_parameter_shadowing():
    assert_external(persistence_repository(), "shadowing/ListShadowing.kt", "service.persist(orders)")
    assert_external(persistence_repository(), "intake/GenericPersistence.kt", "service.persist(value)")


@pytest.mark.parametrize("evidence", ["globalPersist(value)", "globalRecord(1)"])
def test_overloads_never_disambiguate_global_fallback(evidence):
    assert_external(persistence_repository(), "intake/GlobalPersistence.kt", evidence)


@pytest.mark.parametrize("argument", ["orders", "order", "nestedOrder", "localOrder", "qualifiedOrder"])
def test_unsupported_value_and_lexical_type_shadowing(argument):
    assert_external(persistence_repository(), "intake/ShadowedPersistence.kt", f"service.persist({argument})")


@pytest.mark.parametrize("argument", ["genericOrder", "nestedReceiverOrder"])
def test_shadowed_receiver_annotation_is_not_a_concrete_service(argument):
    assert_external(persistence_repository(), "intake/ReceiverTypeShadowing.kt", f"service.persist({argument})")


@pytest.mark.parametrize("path,argument", [
    ("intake/PackageRootShadowing.kt", "packageRootOrder"),
    ("namespace/AliasedPackageRoot.kt", "importedRootOrder"),
])
def test_classifier_or_import_alias_shadows_qualified_receiver_package_root(path, argument):
    assert_external(persistence_repository(), path, f"service.persist({argument})")


@pytest.mark.parametrize("path,argument", [
    ("escaped/EscapedShadowing.kt", "escapedRootOrder"),
    ("escaped/EscapedShadowing.kt", "escapedGenericOrder"),
    ("escaped/EscapedShadowing.kt", "orders"),
    ("escapednamespace/EscapedImportAlias.kt", "escapedAliasOrder"),
    ("intake/EscapedPackageCaller.kt", "escapedPackageOrder"),
])
def test_escaped_names_do_not_bypass_shadowing_guards(path, argument):
    assert_external(persistence_repository(), path, f"service.persist({argument})")
