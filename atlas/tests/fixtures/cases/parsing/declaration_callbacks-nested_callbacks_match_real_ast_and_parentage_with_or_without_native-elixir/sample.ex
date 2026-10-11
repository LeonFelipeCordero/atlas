defmodule Owner do
      def outer(ready) do
        if ready, do: ping()
        use(fn x ->
          if x > 0, do: ping()
          use(fn y -> if y > 0 and ready, do: 1, else: 0 end)
          x
        end)
      end
    end