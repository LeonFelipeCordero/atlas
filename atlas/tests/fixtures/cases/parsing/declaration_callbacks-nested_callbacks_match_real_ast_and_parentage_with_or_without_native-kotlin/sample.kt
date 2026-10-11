fun outer(ready: Boolean) {
      if (ready) ping()
      use { x -> if (x > 0) ping(); use { y -> if (y > 0 && ready) 1 else 0 }; x }
    }