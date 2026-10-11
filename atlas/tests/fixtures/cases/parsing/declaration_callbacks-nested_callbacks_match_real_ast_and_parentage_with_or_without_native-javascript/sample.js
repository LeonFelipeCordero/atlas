function outer(ready) {
      if (ready) ping();
      use(x => { if (x > 0) ping(); use(y => y > 0 && ready ? 1 : 0); return x; });
    }