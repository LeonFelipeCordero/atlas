using System.Collections.Generic;

namespace Coffee.Inventory {
    public sealed class Inventory {
        private readonly Dictionary<string, int> available;

        public Inventory(Dictionary<string, int> openingStock) {
            available = new Dictionary<string, int>(openingStock);
        }

        public bool Reserve(string drink, int units) {
            if (!available.TryGetValue(drink, out int remaining) || remaining < units) return false;
            available[drink] = remaining - units;
            return true;
        }
    }
}
