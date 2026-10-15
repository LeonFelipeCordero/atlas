def brew(beans, cups)
  # Deliberately unsupported semantics: parser availability is not capability.
  beans > 0 ? beans + cups : 0
end
