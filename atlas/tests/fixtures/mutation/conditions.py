"""if fake and fake > 4: strings are not syntax."""
# if ignored or ignored < 0:
label = "café 🫘"

def brew(amount, ready):
    assert amount >= 0, "amount > 0"
    if ready and 0 < amount <= 10:
        while amount != 0:
            amount -= 1
    elif amount is None or amount not in [1, 2]:
        return False
    return "hot" if ready else "cold"

class Machine:
    def serve(self, ready):
        def nested(value):
            return value > 2 and ready
        accepts = lambda value: value == 3 or ready
        return [value for value in range(5) if value > 0]

match label:
    case "tea" if len(label) > 1:
        pass
