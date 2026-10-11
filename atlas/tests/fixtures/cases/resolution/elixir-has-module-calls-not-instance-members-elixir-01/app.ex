defmodule Service do
 def persist(), do: :ok
end
defmodule App do
 def run(service) do
  Service.persist()
  service.persist()
 end
end