if enabled:
    run()


@deco(threshold > 0)
def brew(ready):
    if ready:
        return 1
    return 0


def other(ready):
    @deco(nested_limit > 0)
    def nested(value):
        if value:
            return 3
        return 0

    if ready:
        return 2
    return 0
