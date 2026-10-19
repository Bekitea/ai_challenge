def average(values):
    # намеренно: нет проверки пустого входа -> ZeroDivisionError
    return sum(values) / len(values)
