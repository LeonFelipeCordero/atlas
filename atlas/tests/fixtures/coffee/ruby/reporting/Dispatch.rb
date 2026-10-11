module Coffee
  module Reporting
    class Dispatch
      def initialize(sender)
        @sender = sender
        @delivered = []
      end

      def deliver(orders)
        orders.each do |order|
          next unless order.status == :brewed
          receipt = "pickup:#{order.customer};total=#{order.total}"
          @sender.call(receipt)
          @delivered << receipt
        end
        @delivered.dup
      end

      def preview(orders)
        orders.map { |order| "pickup:#{order.customer}" }
      end
    end
  end
end
