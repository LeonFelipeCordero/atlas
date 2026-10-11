def outer(ready):
    if ready:
        ping()
    use(lambda x: (use(lambda y: 1 if y > 0 and ready else 0), 1 if x else 0))
