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

  # Deliberately exceed the cyclomatic-complexity limit without deep nesting.
  def classify(amount) do
    category = 0
    category = if amount > 0, do: category + 1, else: category
    category = if amount > 1, do: category + 1, else: category
    category = if amount > 2, do: category + 1, else: category
    category = if amount > 3, do: category + 1, else: category
    category = if amount > 4, do: category + 1, else: category
    category = if amount > 5, do: category + 1, else: category
    category = if amount > 6, do: category + 1, else: category
    category = if amount > 7, do: category + 1, else: category
    category
  end

  # Deliberately exceed the decision-nesting limit without loops.
  def ready(water, beans, cups, temperature) do
    if water > 0 do
      if beans > 0 do
        if cups > 0 do
          if temperature > 0 do
            true
          else
            false
          end
        else
          false
        end
      else
        false
      end
    else
      false
    end
  end

  def main do
    IO.puts(brew(["espresso", "filter", "invalid"]))
  end
end
