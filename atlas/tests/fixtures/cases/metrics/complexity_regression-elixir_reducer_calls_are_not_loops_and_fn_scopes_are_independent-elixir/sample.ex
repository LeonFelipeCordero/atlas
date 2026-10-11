def aggregate(items) do
 Enum.reduce(items, 0, fn item, sum ->
  unless stopped do
   Enum.reduce(item, sum, fn value, acc ->
    if value > 0 and ready, do: acc + value, else: acc
   end)
  end
 end)
end