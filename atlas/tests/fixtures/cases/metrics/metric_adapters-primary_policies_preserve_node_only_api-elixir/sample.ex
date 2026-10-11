defmodule Coffee do
 def run(x) when x > 0 do
  cond do
   x > 1 -> 2
   true -> 1
  end
 end
end