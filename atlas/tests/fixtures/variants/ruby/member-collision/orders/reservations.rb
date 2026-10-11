require_relative "../inventory/inventory"


def reserve(customer, drink, units)
  "Reserved for #{customer}: #{units} #{drink}"
end


def queue_order(inventory, customer, drink, units)
  return "Waiting for stock: #{customer}" unless inventory.reserve(drink, units)
  reserve(customer, drink, units)
end


def request_supplier(supplier, customer, drink, units)
  return "Supplier cannot fill: #{customer}" unless supplier.reserve(drink, units)
  supplier.delivery_label(customer, drink, units)
end
