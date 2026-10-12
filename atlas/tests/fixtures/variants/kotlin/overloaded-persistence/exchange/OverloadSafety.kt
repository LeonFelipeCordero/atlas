package exchange

open class BaseOrder
class DerivedOrder : BaseOrder()

class OverloadSafety {
    fun broad(order: OpenOrder) {}
    fun broad(order: Any) {}
    fun inherited(order: BaseOrder) {}
    fun inherited(order: DerivedOrder) {}
    fun nullable(order: OpenOrder) {}
    fun nullable(order: List<OpenOrder>?) {}
    fun defaults(order: OpenOrder) {}
    fun defaults(order: OpenOrder, filled: Boolean = false) {}
    fun spread(order: OpenOrder) {}
    fun spread(vararg orders: OpenOrder) {}
    fun generic(order: OpenOrder) {}
    fun <T> generic(orders: List<T>) {}
    fun collection(orders: List<OpenOrder>) {}
    @JvmName("collectMatched")
    fun collection(orders: List<MatchedOrder>) {}
    fun mutable(orders: List<OpenOrder>) {}
    @JvmName("mutableOrders")
    fun mutable(orders: MutableList<OpenOrder>) {}
    fun returned(order: OpenOrder): OpenOrder = order
    fun returned(orders: List<OpenOrder>): List<OpenOrder> = orders

    fun exercise(service: OverloadSafety, order: OpenOrder, orders: List<OpenOrder>, matched: List<MatchedOrder>,
                 derived: DerivedOrder, maybe: List<OpenOrder>?, projected: List<*>, changed: MutableList<OpenOrder>) {
        service.broad(order)
        service.inherited(derived)
        service.nullable(orders)
        service.nullable(maybe)
        service.defaults(order)
        service.spread(order)
        service.generic(orders)
        service.collection(orders)
        service.collection(matched)
        service.collection(projected)
        service.mutable(changed)
        service.returned(orders)
    }
}
