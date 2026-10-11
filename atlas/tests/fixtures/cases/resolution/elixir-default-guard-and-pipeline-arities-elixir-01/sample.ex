defp run(value, extra \\ 1) when value > 0 do
  value |> next(extra)
  value |> finish
end
