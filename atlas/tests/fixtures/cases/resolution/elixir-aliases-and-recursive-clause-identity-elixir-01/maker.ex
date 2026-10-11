defmodule Drinks.Maker do
 alias Drinks.Report, as: R
 def retry(0), do: 0
 def retry(n) when n > 0, do: retry(n-1)
 def brew(x), do: R.render(x)
end