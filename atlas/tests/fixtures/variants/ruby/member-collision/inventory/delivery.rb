def delivery_label(customer, drink, units)
  "Deliver #{units} #{drink} to #{customer}"
end


def manifest(customer, drinks)
  drinks.map { |drink, units| delivery_label(customer, drink, units) }
end
