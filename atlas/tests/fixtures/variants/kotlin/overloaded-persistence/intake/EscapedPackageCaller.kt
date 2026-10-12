package intake

import exchange.OpenOrder

fun escapedPackageReceiver(service: backtickexchange.Service, escapedPackageOrder: OpenOrder) {
    service.persist(escapedPackageOrder)
}
