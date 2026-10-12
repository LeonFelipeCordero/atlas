module Coffee
  class Inventory
    def initialize(opening_stock)
      @available = opening_stock.dup
    end

    def reserve(drink, units)
      remaining = @available.fetch(drink, 0)
      return false if remaining < units
      @available[drink] = remaining - units
      true
    end
  end
end
