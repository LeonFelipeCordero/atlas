defmodule Brewer do
  def brew(beans, cups) when beans > 0 and cups != 0 do
    label = "Café + >="
    total = beans + cups * 2
    if beans > 0 && !(cups == 0), do: total + 1, else: 0
    unless cups == 0 do
      total - 1
    end
  end
end
