from typing import List


def polynomial(x: float, coeffs: List[float]) -> float:
    x_degree = 1
    result = 0
    for coeff in coeffs:
        result += coeff * x_degree
        x_degree *= x
    return result


def polynomial_in_range(x: float, x_min: float, x_max: float, coeffs: List[float]) -> float:
    return polynomial(x, coeffs) if x_min <= x <= x_max else float('nan')


class PolynomialInterval:
    def __init__(self, coeffs: List[float], begin: float, end: float):
        self.coeffs = coeffs
        self.begin = begin
        self.end = end

    def calculate(self, x: float) -> float:
        return polynomial_in_range(x, self.begin, self.end, self.coeffs)
