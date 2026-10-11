from typing import Callable
top = lambda x: x
def outer(cb: Callable[[int], int]):
 return lambda x: x
