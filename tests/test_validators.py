from detection.validators.card import is_valid_card
from detection.validators.pan import is_valid_pan

def test_valid_card_number():
    assert is_valid_card("4111111111111111") is True


def test_invalid_card_number():
    assert is_valid_card("4111111111111112") is False


def test_invalid_card_candidates_formatted():
    assert is_valid_card("4111-1111-1111-1112") is False
    assert is_valid_card("4111 1111 1111 1112") is False


######### PAN ###############
def test_valid_pan():
    assert is_valid_pan("IKRPM7731M") is True


def test_invalid_pan_malformed():
    assert is_valid_pan("12345ABCDE") is False


def test_invalid_pan_candidate_entity_type():
    # Matches [A-Z]{5}[0-9]{4}[A-Z] regex, but 4th character is not in [ABCFGHLJPT]
    assert is_valid_pan("ABCDE1234F") is False
    assert is_valid_pan("ZZZZZ9999Z") is False
    assert is_valid_pan("ABCDK1234E") is False


######### IPv4 ###############
def test_valid_ipv4():
    from detection.validators.ip import is_valid_ipv4
    assert is_valid_ipv4("192.168.1.1") is True
    assert is_valid_ipv4("10.0.0.1") is True
    assert is_valid_ipv4("127.0.0.1") is True
    assert is_valid_ipv4("255.255.255.255") is True
    assert is_valid_ipv4("0.0.0.0") is True


def test_invalid_ipv4_out_of_range():
    from detection.validators.ip import is_valid_ipv4
    assert is_valid_ipv4("999.999.999.999") is False
    assert is_valid_ipv4("192.168.1.256") is False
    assert is_valid_ipv4("256.0.0.1") is False


def test_invalid_ipv4_malformed():
    from detection.validators.ip import is_valid_ipv4
    assert is_valid_ipv4("192.168.1") is False
    assert is_valid_ipv4("192.168.1.1.1") is False
    assert is_valid_ipv4("192.168.01.1") is False
    assert is_valid_ipv4("abc.def.ghi.jkl") is False