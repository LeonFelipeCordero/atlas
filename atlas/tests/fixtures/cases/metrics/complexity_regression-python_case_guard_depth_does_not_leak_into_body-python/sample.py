def route(value):
 if active:
  match value:
   case 1 if ready:
    if enabled: accept()
   case _:
    if fallback: reject()
