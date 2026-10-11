def choose(x) do
 case x do
 true -> accept()
 false -> reject()
 _ -> fallback()
 end
end