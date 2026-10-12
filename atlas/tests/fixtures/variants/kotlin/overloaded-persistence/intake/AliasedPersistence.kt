package intake

import exchange.OpenOrder as PendingOrder
import exchange.OpenOrderService

fun persistPending(service: OpenOrderService, order: PendingOrder, orders: kotlin.collections.List<PendingOrder>) {
    service.persist(order)
    service.persist(orders)
}
