typealias Callback = (Int) -> Int
val top: Callback = { x -> x }
fun outer(cb: Callback) { use { x -> x } }