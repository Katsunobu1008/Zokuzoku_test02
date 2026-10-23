"""Research-only PICSY virtual-central-bank model (not an asset or payment ledger).

Reference: user's supplied PICSY chapter 4, especially equations 4.60–4.65.
"""
from __future__ import annotations

from typing import Sequence
import math

EPS = 1e-9


def validate_e(matrix: Sequence[Sequence[float]]) -> None:
    n = len(matrix)
    if n < 2 or any(len(row) != n for row in matrix):
        raise ValueError('E must be an NxN matrix with N >= 2')
    for row in matrix:
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in row):
            raise ValueError('entries must be between zero and one')
        if abs(sum(row) - 1.0) > 1e-7:
            raise ValueError('each row of E must sum to one')


def virtual_bank(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """E' = E - diag(E) + diag(E)D/(N-1), D = J - I."""
    validate_e(matrix)
    n = len(matrix)
    return [[0.0 if i == j else matrix[i][j] + matrix[i][i] / (n - 1)
             for j in range(n)] for i in range(n)]


def contribution(matrix: Sequence[Sequence[float]], tol: float = 1e-11,
                 iterations: int = 100_000) -> list[float]:
    """c E' = c and sum(c) = N; lazy walk avoids periodicity (N=2)."""
    e = virtual_bank(matrix)
    n = len(e)
    c = [1.0] * n
    for _ in range(iterations):
        next_c = [(c[j] + sum(c[i] * e[i][j] for i in range(n))) / 2.0
                  for j in range(n)]
        if max(abs(a - b) for a, b in zip(c, next_c)) < tol:
            return [v * n / sum(next_c) for v in next_c]
        c = next_c
    raise ArithmeticError('stationary contribution vector did not converge')


def transaction(matrix: Sequence[Sequence[float]], buyer: int, seller: int,
                amount: float) -> list[list[float]]:
    """E_bb -= alpha; E_bs += alpha (research simulation, not money)."""
    validate_e(matrix)
    n = len(matrix)
    if not 0 <= buyer < n or not 0 <= seller < n or buyer == seller:
        raise ValueError('buyer and seller must be different valid actors')
    if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0 or amount > matrix[buyer][buyer] + EPS:
        raise ValueError('amount exceeds available budget')
    result = [list(row) for row in matrix]
    result[buyer][buyer] -= amount
    result[buyer][seller] += amount
    validate_e(result)
    return result


def natural_recovery(matrix: Sequence[Sequence[float]], gamma: float) -> list[list[float]]:
    """E(t+1)=(1-gamma) E(t)+gamma I (equations 4.9–4.10)."""
    validate_e(matrix)
    if not math.isfinite(gamma) or not 0 <= gamma <= 1:
        raise ValueError('gamma must be in [0,1]')
    return [[(1-gamma)*v + (gamma if i == j else 0) for j, v in enumerate(row)]
            for i, row in enumerate(matrix)]


def demo_three_person() -> dict:
    names = ['A：原作者', 'B：二次創作者', 'C：応援するファン']
    initial = [[0.8, 0.2, 0.0], [0.0, 0.7, 0.3], [0.2, 0.0, 0.8]]
    # C consumes B's derivative work; B invests in A's original source.
    after = transaction(initial, 2, 1, 0.15)
    return {'actors': names, 'before': {'E': initial, 'E_prime': virtual_bank(initial),
                                        'c': contribution(initial)},
            'after': {'E': after, 'E_prime': virtual_bank(after),
                      'c': contribution(after)},
            'transaction': {'buyer': 2, 'seller': 1, 'alpha': 0.15},
            'disclaimer': '研究用計算例。法定通貨・ポイント・配当・請求権・投資商品ではありません。'}
