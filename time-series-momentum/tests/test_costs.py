import pytest
import numpy as np
from src.optimization import calcular_costo_transaccion, calcular_swap_pnl

def test_transaction_cost_increases_with_turnover():
    c1 = calcular_costo_transaccion(0.1, 0.0, 100, 0.02)
    c2 = calcular_costo_transaccion(0.2, 0.0, 100, 0.02)

    assert c2 > c1

def test_negative_long_swap_reduces_return():
    pnl = calcular_swap_pnl(
        w_prev=1.0,
        swap_long=-0.036,
        swap_short=0.0,
        multiplier=1.0
    )

    assert pnl < 0

def test_negative_short_swap_reduces_return_for_short_position():
    pnl = calcular_swap_pnl(
        w_prev=-1.0,
        swap_long=0.0,
        swap_short=-0.036,
        multiplier=1.0
    )

    assert pnl < 0

def test_positive_swap_is_credit():
    pnl = calcular_swap_pnl(
        w_prev=1.0,
        swap_long=0.036,
        swap_short=-0.036,
        multiplier=1.0
    )

    assert pnl > 0
