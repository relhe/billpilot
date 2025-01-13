def compute_total_due(due_amount, discount_percent, tax_percent):
    """
    Dynamically calculates `total_due` based on `due_amount`,
    `discount_percent`, and `tax_percent`.
    """
    discount = due_amount * (discount_percent / 100)
    tax = due_amount * (tax_percent / 100)
    return round(due_amount - discount + tax, 2)
