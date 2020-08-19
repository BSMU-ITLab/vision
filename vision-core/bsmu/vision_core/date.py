from typing import Tuple


DAYS_IN_YEAR = 365.2422
DAYS_IN_MONTH = DAYS_IN_YEAR / 12


def months_to_days(months: float) -> float:
    return months * DAYS_IN_MONTH


def years_months_to_days(years: float, months: float) -> float:
    return years * DAYS_IN_YEAR + months * DAYS_IN_MONTH


def days_to_months(days: float) -> float:
    return days / DAYS_IN_MONTH


def days_to_years_days(days: float) -> Tuple[int, float]:
    years, days_remainder = divmod(days, DAYS_IN_YEAR)
    return int(years), days_remainder


def days_to_years_months(days: float) -> Tuple[int, float]:
    years, days_remainder = days_to_years_days(days)
    months = days_remainder / DAYS_IN_MONTH
    return years, months


def days_to_months_days(days: float) -> Tuple[int, float]:
    months, days_remainder = divmod(days, DAYS_IN_MONTH)
    return int(months), days_remainder


def days_to_years_months_days(days: float) -> Tuple[int, int, float]:
    years, days_remainder = days_to_years_days(days)
    months, days_remainder = days_to_months_days(days_remainder)
    return years, months, days_remainder
