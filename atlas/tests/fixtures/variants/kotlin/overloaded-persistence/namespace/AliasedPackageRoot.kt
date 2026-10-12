package namespace

import intake.exchange as exchange
import exchange.OpenOrder

fun importedRootReceiver(service: exchange.OpenOrderService, importedRootOrder: OpenOrder) {
    service.persist(importedRootOrder)
}
