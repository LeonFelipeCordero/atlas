defmodule Coffee.Brewing.Brewer do
  alias Coffee.Brewing.Recipe
  alias Coffee.Reporting.Report

  def brew([]), do: Report.render([])

  def brew(names) do
    names |> Enum.filter(fn name -> Recipe.portions(name) > 0 end) |> Report.render()
  end

  def retry(attempts) when attempts <= 0, do: 0
  def retry(attempts), do: 1 + retry(attempts - 1)

  def score(batches) do
    Enum.reduce(batches, 0, fn batch, sum ->
      Enum.reduce(batch, sum, fn name, subtotal ->
        count = Recipe.portions(name)
        if count > 0 and count <= 3 do
          subtotal + count
        else
          subtotal
        end
      end)
    end)
  end

  def main do
    IO.puts(brew(["espresso", "filter", "invalid"]))
  end
end
