package brewing

import (
	"fmt"
	"strings"
)

func Reserve(order Order) string {
	return fmt.Sprintf("Reserved for %s: %s", order.Customer, strings.Join(order.Names, ", "))
}

func QueueOrder(inventory *Inventory, order Order) string {
	for _, name := range order.Names {
		if !inventory.Reserve(name) {
			return fmt.Sprintf("Waiting for stock: %s", order.Customer)
		}
	}
	return Reserve(order)
}

func RequestSupplier(supplier interface{}, order Order) string {
	if !supplier.Reserve(order) {
		return fmt.Sprintf("Supplier cannot fill: %s", order.Customer)
	}
	return supplier.DeliveryLabel(order)
}
