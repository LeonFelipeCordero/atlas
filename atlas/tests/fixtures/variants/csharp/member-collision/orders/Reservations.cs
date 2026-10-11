namespace Coffee.Orders {
    public static class Reservations {
        public static string Reserve(string customer, string drink, int units) {
            return $"Reserved for {customer}: {units} {drink}";
        }

        public static string QueueOrder(Coffee.Inventory.Inventory inventory, string customer, string drink, int units) {
            if (!inventory.Reserve(drink, units)) return $"Waiting for stock: {customer}";
            return Reserve(customer, drink, units);
        }

        public static string RequestSupplier(dynamic supplier, string customer, string drink, int units) {
            if (!supplier.Reserve(drink, units)) return $"Supplier cannot fill: {customer}";
            return supplier.DeliveryLabel(customer, drink, units);
        }
    }
}
