import phonenumbers


def is_valid_phone(phone: str, region: str = "RU") -> bool:
    try:
        parsed = phonenumbers.parse(phone, region)
        return phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        return False
