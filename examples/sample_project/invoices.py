"""Invoice totals. Toy code for the refactor-baseline demo — not real software."""


def sum_line_items(lines):
    total = 0
    for line in lines:
        amount = line.unit_price * line.quantity
        if line.taxable:
            amount += amount * 0.08
        total += amount
    return round(total, 2)
