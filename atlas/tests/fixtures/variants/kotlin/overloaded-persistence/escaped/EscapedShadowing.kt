package escaped

import exchange.OpenOrder
import exchange.MatchedOrder
import exchange.OpenOrderService
import intake.OtherService

class `exchange` {
    class OpenOrderService {
        fun persist(order: OpenOrder) {}
        fun persist(orders: List<OpenOrder>) {}
    }
}

fun escapedRootReceiver(service: exchange.OpenOrderService, escapedRootOrder: OpenOrder) {
    service.persist(escapedRootOrder)
}

fun <`OpenOrderService` : OtherService> escapedGenericReceiver(service: OpenOrderService, escapedGenericOrder: OpenOrder) {
    service.persist(escapedGenericOrder)
}

fun escapedConstructorShadow(service: OpenOrderService, orders: List<OpenOrder>) {
    class Local(`orders`: List<MatchedOrder>) {
        init {
            service.persist(orders)
        }
    }
}
