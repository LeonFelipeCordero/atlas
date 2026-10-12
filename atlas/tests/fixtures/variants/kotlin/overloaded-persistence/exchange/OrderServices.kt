package exchange

class OpenOrder
class MatchedOrder

class OpenOrderService {
    fun persist(openOrder: OpenOrder) {}
    fun persist(openOrders: List<OpenOrder>) {}
    fun record() {}
    fun record(order: OpenOrder) {}
    fun record(order: OpenOrder, filled: Boolean) {}
}

class MatchedOrderService {
    fun persist(matchedOrder: MatchedOrder) {}
    fun persist(matchedOrders: List<MatchedOrder>) {}
}

class OrderService {
    fun markOrdersAsFilled(orders: List<OpenOrder>) {}
}

class OpenOrderSemaphoreService {
    fun release(orders: List<OpenOrder>) {}
}
