package shadowing

import exchange.OpenOrder
import exchange.OpenOrderService

typealias List<T> = Set<T>

fun aliasList(service: OpenOrderService, orders: List<OpenOrder>) {
    service.persist(orders)
}

class GenericIntake<List>(private val service: OpenOrderService) {
    fun persistShadowed(orders: List) {
        service.persist(orders)
    }
}
