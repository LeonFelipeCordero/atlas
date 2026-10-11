def choose(x) do
 cond do
 x > 0 and ready -> if enabled, do: accept()
 x < 0 -> reject()
 true -> fallback()
 end
end