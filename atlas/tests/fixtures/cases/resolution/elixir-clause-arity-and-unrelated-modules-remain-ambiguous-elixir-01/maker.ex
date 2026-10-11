defmodule Maker do
 def retry(0), do: 0
 def retry(n), do: retry(n-1)
 def retry(n, x), do: x
end