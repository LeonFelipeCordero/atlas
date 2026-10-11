def route(value):
 match value:
  case 0 | 1: pass
  case State.READY: pass
  case [first, *rest]: pass
  case _: pass
