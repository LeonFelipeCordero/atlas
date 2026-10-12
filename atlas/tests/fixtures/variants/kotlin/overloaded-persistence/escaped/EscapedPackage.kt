package `intake`

import exchange.OpenOrder

class `backtickexchange` {
    class Service {
        fun persist(order: OpenOrder) {}
        fun persist(orders: List<OpenOrder>) {}
    }
}
