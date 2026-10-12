package intake

import exchange.OpenOrder
import exchange.MatchedOrder
import exchange.OpenOrderService

fun constructorShadow(service: OpenOrderService, orders: List<OpenOrder>) {
    class Local(orders: List<MatchedOrder>) {
        init {
            service.persist(orders)
        }
    }
}

fun propertyShadow(service: OpenOrderService, orders: List<OpenOrder>) {
    class Local(val orders: List<MatchedOrder>) {
        init {
            service.persist(orders)
        }
    }
}

fun receiverConstructorShadow(service: OpenOrderService, order: OpenOrder) {
    class Local(service: Any) {
        init {
            service.persist(order)
        }
    }
}

fun catchShadow(service: OpenOrderService, order: OpenOrder) {
    try {
        throw Exception()
    } catch (order: Exception) {
        service.persist(order)
    }
}

class NestedTypeCaller {
    class OpenOrder

    fun persist(service: OpenOrderService, nestedOrder: OpenOrder) {
        service.persist(nestedOrder)
    }
}

fun localTypeCaller(service: OpenOrderService) {
    class OpenOrder
    val localOrder: OpenOrder = OpenOrder()
    service.persist(localOrder)
}

class QualifiedTypeCaller {
    class exchange {
        class OpenOrder
    }

    fun persist(service: OpenOrderService, qualifiedOrder: exchange.OpenOrder) {
        service.persist(qualifiedOrder)
    }
}
