package sample
type Callback func(int) int
var top Callback = func(x int) int { return x }
func outer(cb Callback) { use(func(x int) int { return x }) }