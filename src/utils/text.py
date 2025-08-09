def normalize(text: str) -> str:
    """
    Приводит строку к единому виду:
    - lower()
    - убирает лишние пробелы
    - заменяет дефисы и подчёркивания на пробелы
    """
    x = text.lower().strip()
    x = x.replace("-", " ").replace("_", " ")
    x = " ".join(x.split())
    return x