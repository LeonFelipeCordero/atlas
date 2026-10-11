def outer(x) do
 if ready do
 defmacro inner(x), do: if(x and enabled, do: accept())
 end
 defmodule Inner do
 def run(), do: unless(stopped, do: reject())
 end
end