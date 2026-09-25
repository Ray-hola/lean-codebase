"""Order pricing. Toy code for the refactor-baseline demo — not real software."""


def calc_order_total(items):
    total = 0
    for item in items:
        price = item.unit_price * item.quantity
        if item.taxable:
            price += price * 0.08
        total += price
    return round(total, 2)
