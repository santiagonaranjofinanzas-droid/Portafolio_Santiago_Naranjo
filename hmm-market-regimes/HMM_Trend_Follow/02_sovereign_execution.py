class CFinancialEngine:
    @staticmethod
    def calculate_volatility_stop(
        price: float,
        vol_projected_sigma: float,
        vol_multiplier: float = 2.5,
        spread_price: float = 0.0,
    ) -> float:
        """Replica ExecuteOrder: price * sigma * multiplier, con piso de 3x spread."""
        vol_distance_price = price * vol_projected_sigma * vol_multiplier
        min_sl_price = spread_price * 3.0
        return max(vol_distance_price, min_sl_price)

    @staticmethod
    def calculate_adaptive_lot(
        balance: float,
        risk_percent: float,
        stop_loss_points: int,
        tick_value: float,
        tick_size: float,
        point: float,
        max_lot: float = 10.0,
        min_lot: float = 0.01,
        lot_step: float = 0.01,
    ) -> float:
        """Replica CalculateLot del EA y aplica el clamp final de ExecuteOrder."""
        if stop_loss_points <= 0 or tick_value <= 0 or tick_size <= 0 or point <= 0:
            return min_lot
        risk_money = balance * (risk_percent / 100.0)
        raw_lot = risk_money / (stop_loss_points * (tick_value / tick_size * point))
        if lot_step <= 0.0:
            lot_step = 0.01
        steps = round((raw_lot - min_lot) / lot_step)
        lot = min_lot + steps * lot_step
        lot = round(lot, 4)
        return min(max_lot, max(min_lot, lot))
