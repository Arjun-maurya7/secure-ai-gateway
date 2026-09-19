import ipaddress


def is_valid_ipv4(ip_str: str) -> bool:
    """Validate whether a candidate string is a valid canonical IPv4 address (0-255 per octet, no invalid leading zeros)."""
    try:
        parts = ip_str.split(".")
        if len(parts) != 4:
            return False

        for part in parts:
            if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
                return False

        ipaddress.IPv4Address(ip_str)
        return True
    except (ValueError, AttributeError):
        return False
