package exchange

class OrderMatchingService(
    private val openOrderService: OpenOrderService,
    private val matchedOrderService: MatchedOrderService,
    private val orderService: OrderService,
    private val openOrderSemaphoreService: OpenOrderSemaphoreService
) {
    fun matchOrder(order: OpenOrder, orders: List<OpenOrder>, matchedOrders: List<MatchedOrder>) {
        val ordersToPersist: List<OpenOrder> = orders
        val filledOrders: List<OpenOrder> = orders
        val ordersToDelete: List<OpenOrder> = orders
        openOrderService.persist(ordersToPersist)
        matchedOrderService.persist(matchedOrders)
        orderService.markOrdersAsFilled(filledOrders)
        openOrderSemaphoreService.release(ordersToDelete)
        openOrderService.persist(order)
        openOrderService.record()
        openOrderService.record(order)
        openOrderService.record(order, true)
    }

    fun unknown(unknown: Any) {
        openOrderService.persist(unknown)
    }

    fun inferred(orders: List<OpenOrder>) {
        val inferredOrders = orders
        openOrderService.persist(inferredOrders)
    }

    fun shadowed(orders: List<OpenOrder>, values: List<Any>) {
        values.forEach { orders -> openOrderService.persist(orders) }
    }

    fun shadowedService(openOrderService: Any, orders: List<OpenOrder>) {
        openOrderService.persist(orders)
    }

    fun reassigned(orders: List<OpenOrder>) {
        var changed: List<OpenOrder> = orders
        changed = orders
        openOrderService.persist(changed)
    }

    fun unsupported(orders: List<OpenOrder>) {
        openOrderService.persist(openOrders = orders)
        openOrderService.persist(*orders)
        openOrderService.persist { orders }
        openOrderService.persist()
    }
}
