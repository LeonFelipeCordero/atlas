fn outer(ready: bool) {
      if ready { ping(); }
      consume(|x: i32| {
        if x > 0 { ping(); }
        consume(|y: i32| if y > 0 && ready { 1 } else { 0 }); x
      });
    }