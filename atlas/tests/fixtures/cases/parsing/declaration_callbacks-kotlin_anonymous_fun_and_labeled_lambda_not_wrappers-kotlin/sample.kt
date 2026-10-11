typealias Callback = (Int) -> Int
fun outer(cb: (Int) -> Int) {
  val assigned = fun(x: Int): Int { return if (x > 0) x else 0 }
  use(fun(x: Int) = if (x > 0) x else 0)
  use label@ { x -> if (x > 0) x else 0 }
}