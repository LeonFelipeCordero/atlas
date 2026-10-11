require "date"

module Coffee
  class Scheduling
    def initialize(customer, days = 1)
      @customer = customer
      @pickup = Date.today + days
    end

    def receipt
      "#{@customer}: #{@pickup.iso8601}"
    end
  end
end
