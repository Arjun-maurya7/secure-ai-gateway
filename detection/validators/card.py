def is_valid_card(number: str) -> bool:
    digits = [int(digit) for digit in number if digit.isdigit()]

    total = 0
    parity = len(digits) % 2

    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0