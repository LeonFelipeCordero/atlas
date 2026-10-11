package sample
    func outer(ready bool) {
      if ready { ping() }
      use(func(x int) int {
        if x > 0 { ping() }
        use(func(y int) int { if y > 0 && ready { return 1 }; return 0 })
        return x
      })
    }