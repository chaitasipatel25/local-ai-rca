from calculator import calculate_total


def test_total_without_discount():
    assert calculate_total(10, 3) == 30


def test_total_with_discount():
    # A 5% discount on $30 should produce $28.50.
    assert calculate_total(10, 3, discount=5) == 28.5


def test_percentage_discount():
    # A 10% discount on $200 should produce $180.
    assert calculate_total(100, 2, discount=10) == 180
