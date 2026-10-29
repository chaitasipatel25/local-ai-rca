def calculate_total(price, quantity, discount=0):
    """Return the total after applying a discount."""
    subtotal = price * quantity
    discount_amount = subtotal * discount / 100
    return subtotal - discount_amount