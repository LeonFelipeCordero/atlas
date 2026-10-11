defmodule Owner do
  def outer do
    use(fn x when x > 0 -> if x > 1, do: 1, else: 0; _ -> 0 end)
    use(fn x -> x end)
    use(fn x -> x end)
  end
end