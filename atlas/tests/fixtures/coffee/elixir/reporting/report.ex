defmodule Coffee.Reporting.Report do
  alias Coffee.Brewing.Recipe

  def total(names), do: Enum.reduce(names, 0, fn name, sum -> sum + Recipe.portions(name) end)

  def render(names) do
    entries = Enum.map_join(names, ",", fn name -> "#{name}=#{Recipe.portions(name)}" end)
    "coffee:#{entries};total=#{total(names)}"
  end
end
