package intake

import exchange.OpenOrder

class exchange {
    class OpenOrderService {
        fun persist(order: OpenOrder) {}
        fun persist(orders: List<OpenOrder>) {}
    }
}

fun packageRootReceiver(service: exchange.OpenOrderService, packageRootOrder: OpenOrder) {
    service.persist(packageRootOrder)
}
