package intake

import exchange.OpenOrder

class ShadowedService {
    fun persist(order: OpenOrder) {}
    fun persist(orders: List<OpenOrder>) {}
}

open class OtherService {
    fun persist(order: OpenOrder) {}
    fun persist(orders: List<OpenOrder>) {}
}

fun <ShadowedService : OtherService> genericReceiver(service: ShadowedService, genericOrder: OpenOrder) {
    service.persist(genericOrder)
}

class NestedReceiverCaller {
    class ShadowedService {
        fun persist(order: OpenOrder) {}
        fun persist(orders: List<OpenOrder>) {}
    }

    fun persist(service: ShadowedService, nestedReceiverOrder: OpenOrder) {
        service.persist(nestedReceiverOrder)
    }
}
