package escapednamespace

import intake.exchange as `exchange`
import exchange.OpenOrder

fun escapedImportReceiver(service: exchange.OpenOrderService, escapedAliasOrder: OpenOrder) {
    service.persist(escapedAliasOrder)
}
