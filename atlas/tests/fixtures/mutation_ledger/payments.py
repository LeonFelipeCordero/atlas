"""Small experiment target; no tests are executed by Atlas."""


def accept_payment(amount, minimum):
    if amount >= minimum:
        return True
    return False
