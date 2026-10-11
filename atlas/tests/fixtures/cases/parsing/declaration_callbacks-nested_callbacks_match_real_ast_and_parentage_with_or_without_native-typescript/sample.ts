function outer(ready: boolean) {
      if (ready) ping();
      use((x: number) => { if (x > 0) ping(); use((y: number) => y > 0 && ready ? 1 : 0); return x; });
    }