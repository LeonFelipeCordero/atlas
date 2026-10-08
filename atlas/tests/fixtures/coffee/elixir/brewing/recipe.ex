defmodule Coffee.Brewing.Recipe do
  alias Coffee.Reporting.Report

  def portions(name) do
    case name do
      "espresso" -> 2
      "filter" -> 3
      _ -> 0
    end
  end

  def preview(name), do: Report.render([name])
end
