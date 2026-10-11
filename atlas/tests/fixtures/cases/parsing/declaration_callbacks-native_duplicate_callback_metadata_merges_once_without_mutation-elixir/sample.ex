top = fn x -> x end
defmodule Owner do
 def outer(cb), do: use(fn x -> x end)
end