require_relative "scheduling"

module Coffee
  class Order < Scheduling
    attr_reader :items
    attr_accessor :status

    def initialize(customer, items, days = 1)
      super(customer, days)
      @items = items
      @status = :queued
    end
  end

  class PickupQueue
    def initialize
      @orders = []
    end

    def record(order, status)
      order.status = status
      @orders << order
      order.receipt
    end

    def collect
      ready, @orders = @orders.partition { |order| order.status == :ready }
      ready.map(&:receipt)
    end
  end
end
