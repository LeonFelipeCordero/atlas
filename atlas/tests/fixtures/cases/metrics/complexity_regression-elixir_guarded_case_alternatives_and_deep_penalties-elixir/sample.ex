def choose(x) do
 if enabled do
 unless stopped do
 case x do
 1 when ready and valid -> if active, do: accept()
 _ -> fallback()
 end
 end
 end
end