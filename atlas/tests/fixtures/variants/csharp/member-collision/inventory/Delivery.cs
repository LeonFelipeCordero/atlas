using System.Collections.Generic;

namespace Coffee.Inventory {
    public static class Delivery {
        public static string DeliveryLabel(string customer, string drink, int units) {
            return $"Deliver {units} {drink} to {customer}";
        }

        public static IReadOnlyList<string> Manifest(string customer, Dictionary<string, int> drinks) {
            var labels = new List<string>();
            foreach (var drink in drinks) {
                labels.Add(DeliveryLabel(customer, drink.Key, drink.Value));
            }
            return labels.AsReadOnly();
        }
    }
}
