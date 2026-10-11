def choose(x) do
 case x do
 _ when ready -> accept()
 _ -> fallback()
 end
end