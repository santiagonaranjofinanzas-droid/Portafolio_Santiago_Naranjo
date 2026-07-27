import os
import sys

import numpy as np
import pandas as pd

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from Capa_1.sovereign_core import CStatistics, CStateSpace, CVolatilityEngine


def log_gamma_lanczos(x: float) -> float:
    if x <= 0.0:
        return 0.0
    p = [
        676.5203681218851, -1259.1392167224028, 771.32342877765313,
        -176.61502916214059, 12.507343278686905, -0.13857109526572012,
        9.9843695780195716e-6, 1.5056327351493116e-7,
    ]
    y = x
    if y < 0.5:
        return np.log(np.pi / np.sin(np.pi * y)) - log_gamma_lanczos(1.0 - y)
    y -= 1.0
    x_p = 0.99999999999980993
    for i in range(8):
        x_p += p[i] / (y + float(i) + 1.0)
    t = y + 7.5
    return 0.5 * np.log(2.0 * np.pi) + (y + 0.5) * np.log(t) - t + np.log(x_p)


def log_t_student_density(x: float, mu: float, sig: float, nu: float) -> float:
    if sig <= 0.0:
        sig = 1e-10
    if nu <= 2.0:
        nu = 2.01
    z = (x - mu) / sig
    log_const = (
        log_gamma_lanczos((nu + 1.0) / 2.0)
        - log_gamma_lanczos(nu / 2.0)
        - 0.5 * np.log(nu * np.pi)
    )
    return log_const - np.log(sig) - ((nu + 1.0) / 2.0) * np.log(1.0 + (z * z) / nu)


def log_normal_jump_density(x: float, sig_jump: float) -> float:
    if sig_jump <= 0.0:
        sig_jump = 1e-10
    return -np.log(sig_jump) - 0.5 * np.log(2.0 * np.pi) - 0.5 * ((x / sig_jump) ** 2.0)


def calculate_wma(src: np.ndarray, period: int, start: int = 0) -> np.ndarray:
    wma = np.zeros_like(src, dtype=float)
    if period < 1:
        return wma
    weight_sum = period * (period + 1) / 2.0
    for i in range(max(0, start), len(src)):
        if i < period - 1:
            wma[i] = np.sum(src[:i + 1]) / (i + 1)
        else:
            window = src[i - period + 1:i + 1]
            weights = np.arange(1, period + 1, dtype=float)
            wma[i] = np.sum(window * weights) / weight_sum
    return wma


def calculate_hma(src: np.ndarray, length: int, start: int = 0) -> np.ndarray:
    if length < 2:
        return np.zeros_like(src, dtype=float)
    half = length // 2
    sqn = int(np.round(np.sqrt(length)))
    t1 = calculate_wma(src, half, start)
    t2 = calculate_wma(src, length, start)
    return calculate_wma(2.0 * t1 - t2, sqn, start)


def calculate_ema(src: np.ndarray, period: int) -> np.ndarray:
    ema = np.zeros_like(src, dtype=float)
    if period < 1 or len(src) == 0:
        return ema
    alpha = 2.0 / (period + 1.0)
    ema[0] = src[0]
    for i in range(1, len(src)):
        ema[i] = src[i] * alpha + ema[i - 1] * (1.0 - alpha)
    return ema


def calculate_stdev(src: np.ndarray, period: int) -> np.ndarray:
    dev = np.zeros_like(src, dtype=float)
    if period < 2:
        return dev
    for i in range(period - 1, len(src)):
        dev[i] = np.std(src[i - period + 1:i + 1], ddof=1)
    return dev


def calculate_variance(src: np.ndarray, period: int) -> np.ndarray:
    var = np.zeros_like(src, dtype=float)
    if period < 2:
        return var
    for i in range(period - 1, len(src)):
        var[i] = np.var(src[i - period + 1:i + 1], ddof=1)
    return var


def calculate_kurtosis(src: np.ndarray, period: int) -> np.ndarray:
    kurt = np.zeros_like(src, dtype=float)
    if period < 4:
        return kurt
    for i in range(period - 1, len(src)):
        window = src[i - period + 1:i + 1]
        mean_w = np.mean(window)
        m2 = np.mean((window - mean_w) ** 2)
        m4 = np.mean((window - mean_w) ** 4)
        kurt[i] = (m4 / (m2 * m2)) - 3.0 if m2 > 1e-20 else 0.0
    return kurt


def calculate_atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.zeros_like(close, dtype=float)
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    atr = np.zeros_like(close, dtype=float)
    atr[0] = tr[0]
    alpha = 1.0 / period
    for i in range(1, len(close)):
        atr[i] = tr[i] * alpha + atr[i - 1] * (1.0 - alpha)
    return atr


def load_hmm_params(csv_path: str) -> dict:
    params = {
        "ExtPBull": 0.980,
        "ExtPBear": 0.980,
        "ExtSlopeT": 0.0273,
        "ExtJumpLambda": 0.05,
        "ExtHMMNu": 4.88,
        "ExtWConf": 0.5,
        "ExtWVol": 0.5,
        "ExtWSlope": 0.5,
        "ExtWAccel": 0.0,
        "ExtWInter": 0.0,
        "ExtMuConf": 0.5,
        "ExtMuVol": 1.0,
        "ExtMuSlope": 1.0,
        "ExtMuAccel": 0.0,
        "ExtStdConf": 0.25,
        "ExtStdVol": 0.5,
        "ExtStdSlope": 2.0,
        "ExtStdAccel": 1.0,
    }
    if not os.path.exists(csv_path):
        return params
    raw = pd.read_csv(csv_path)
    if raw.empty:
        return params
    cols = list(raw.columns)
    vals = raw.iloc[0].tolist()
    if len(vals) < 9:
        return params
    params.update({
        "ExtPBull": float(vals[0]),
        "ExtPBear": float(vals[1]),
        "ExtSlopeT": float(vals[2]),
        "ExtJumpLambda": float(vals[3]),
        "ExtHMMNu": float(vals[4]),
        "ExtWConf": float(vals[5]),
        "ExtWVol": float(vals[6]),
        "ExtWSlope": float(vals[7]),
    })
    has_accel = len(vals) >= 18 and cols[8] == "WAccel" and cols[13] == "MuAccel" and cols[17] == "StdAccel"
    if has_accel:
        params.update({
            "ExtWAccel": float(vals[8]),
            "ExtWInter": float(vals[9]),
            "ExtMuConf": float(vals[10]),
            "ExtMuVol": float(vals[11]),
            "ExtMuSlope": float(vals[12]),
            "ExtMuAccel": float(vals[13]),
            "ExtStdConf": float(vals[14]),
            "ExtStdVol": float(vals[15]),
            "ExtStdSlope": float(vals[16]),
            "ExtStdAccel": float(vals[17]),
        })
    else:
        params["ExtWInter"] = float(vals[8])
    if (not has_accel) and len(vals) >= 15 and cols[9] == "MuConf" and cols[14] == "StdSlope":
        params.update({
            "ExtMuConf": float(vals[9]),
            "ExtMuVol": float(vals[10]),
            "ExtMuSlope": float(vals[11]),
            "ExtStdConf": float(vals[12]),
            "ExtStdVol": float(vals[13]),
            "ExtStdSlope": float(vals[14]),
        })
    return params


def run_sovereign_signal_engine(
    df: pd.DataFrame,
    params_csv: str  None = None,
    point: float = 0.01,
    ret_window: int = 20,
    vol_window: int = 60,
    threshold: float = 0.65,
    garch_alpha: float = 0.05,
    garch_gamma: float = 0.05,
    garch_beta: float = 0.88,
    long_run_window: int = 120,
    recalib_window: int = 500,
    jump_sigma_k: float = 3.0,
    kalman_q: float = 0.0001,
    kalman_r: float = 0.01,
    kalman_gate: bool = True,
    ou_window: int = 60,
    drift_window: int = 2000,
    min_strength: float = 0.3,
    ablation_mode: str = "none",
    dynamic_threshold: bool = False,
    dynamic_threshold_k: float = 0.10,
    dynamic_threshold_min: float = 0.51,
    dynamic_threshold_max: float = 0.95,
) -> pd.DataFrame:
    params = load_hmm_params(params_csv or os.path.join(ruta_raiz, "HMM_Params_15M.csv"))
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    open_ = df["open"].to_numpy(dtype=float)
    rates_total = len(close)

    hma_warmup = 150 + int(np.round(np.sqrt(150))) + 1
    min_start = max(hma_warmup, long_run_window) + 1

    b_shifted_close = np.zeros(rates_total)
    b_shifted_close[1:] = close[:-1]
    b_shifted_close[0] = close[0]
    b_returns = np.zeros(rates_total)
    for i in range(2, rates_total):
        b_returns[i] = np.log(close[i - 1] / close[i - 2])

    b_hma_val = calculate_hma(b_shifted_close, 150)
    b_mu_rets = calculate_ema(b_returns, ret_window)
    b_sig_rets = calculate_stdev(b_returns, vol_window)
    b_lr_sigs = calculate_stdev(b_returns, long_run_window)
    b_init_vars = calculate_variance(b_returns, long_run_window)
    b_kurtosis = calculate_kurtosis(b_returns, long_run_window)
    b_atr = calculate_atr_wilder(high, low, close, 14)

    b_p1 = np.zeros(rates_total)
    b_sigma2_gjr = np.zeros(rates_total)
    b_strength = np.zeros(rates_total)
    b_regime = np.zeros(rates_total)
    b_hma_raw_slope = np.zeros(rates_total)
    b_kalman_x = np.zeros(rates_total)
    b_kalman_p = np.zeros(rates_total)
    b_sig_proj = np.zeros(rates_total)
    b_raw_conf = np.zeros(rates_total)
    b_raw_vol = np.zeros(rates_total)
    b_raw_slope = np.zeros(rates_total)
    b_raw_accel = np.zeros(rates_total)
    b_kalman_slope = np.zeros(rates_total)
    b_kalman_regime = np.zeros(rates_total)
    b_to_bull = np.full(rates_total, np.nan)
    b_to_bear = np.full(rates_total, np.nan)

    b_p1[:max(min_start, 1)] = 0.5
    b_sigma2_gjr[0] = 0.000001 / (1.0 - garch_alpha - garch_gamma * 0.5 - garch_beta)
    if b_sigma2_gjr[0] <= 0 or b_sigma2_gjr[0] > 1.0:
        b_sigma2_gjr[0] = 0.0001
    if min_start - 1 < rates_total:
        b_kalman_x[min_start - 1] = close[min_start - 1]
        b_kalman_p[min_start - 1] = 1.0
    for i in range(1, min(min_start, rates_total)):
        b_sigma2_gjr[i] = max(b_init_vars[i], 1e-10) if i < long_run_window else b_sigma2_gjr[0]
        b_kalman_x[i] = b_shifted_close[i]
        b_kalman_p[i] = 1.0

    g_nu_dynamic = params["ExtHMMNu"]
    g_lambda_dynamic = params["ExtJumpLambda"]

    for i in range(min_start, rates_total):
        ret = b_returns[i]
        sig_t = max(b_sig_rets[i], 1e-10)
        lr_sigma = max(b_lr_sigs[i], 1e-10)

        ou_start = max(2, i - ou_window + 1)
        mu_bull_ou, mu_bear_ou = CStateSpace.estimate_ou_drift(
            b_returns, ou_start, min(ou_window, i - ou_start + 1), lr_sigma
        )

        prev_innov = b_returns[i - 1] - b_mu_rets[i - 1]
        prev_sigma2 = max(b_sigma2_gjr[i - 1], 1e-10)
        b_sigma2_gjr[i] = CVolatilityEngine.step_gjr_garch(
            prev_innov, prev_sigma2, max(b_init_vars[i], 1e-10),
            garch_alpha, garch_gamma, garch_beta,
        )
        gjr_sigma = np.sqrt(b_sigma2_gjr[i])

        if i >= long_run_window and (i % recalib_window == 0):
            w = min(i, recalib_window)
            kappa = b_kurtosis[i]
            if kappa > 0.01:
                g_nu_dynamic = max(2.5, min(30.0, 6.0 / kappa + 4.0))
            jump_threshold = jump_sigma_k * lr_sigma
            jump_count = sum(1 for k in range(w) if abs(b_returns[i - k]) > jump_threshold)
            g_lambda_dynamic = max(0.01, min(0.30, float(jump_count) / w))

        prev_kx = b_kalman_x[i - 1] if i > 0 else b_shifted_close[i]
        prev_kp = b_kalman_p[i - 1] if i > 0 else 1.0
        b_kalman_x[i], b_kalman_p[i] = CStateSpace.step_kalman(
            b_shifted_close[i], prev_kx, prev_kp, kalman_q, kalman_r
        )
        b_kalman_slope[i] = (b_kalman_x[i] - prev_kx) / max(point, 1e-10)
        atr_i = max(b_atr[max(i - 1, 0)], 1e-10)
        kalman_thresh = atr_i * params["ExtSlopeT"] / max(point, 1e-10)
        b_kalman_regime[i] = 1 if b_kalman_slope[i] > kalman_thresh else (-1 if b_kalman_slope[i] < -kalman_thresh else 0)

        prev_p1 = b_p1[i - 1] if i > 0 else 0.5
        p1_pred = params["ExtPBull"] * prev_p1 + (1.0 - params["ExtPBear"]) * (1.0 - prev_p1)
        p0_pred = 1.0 - p1_pred
        ll1 = log_t_student_density(ret, mu_bull_ou, sig_t, g_nu_dynamic)
        ll0 = log_t_student_density(ret, -mu_bear_ou, sig_t, g_nu_dynamic)
        kurt_mult = max(2.0, min(10.0, np.sqrt(max(b_kurtosis[i] + 3.0, 3.0))))
        sig_jump = max(lr_sigma * kurt_mult, 1e-10)
        ll_jump = log_normal_jump_density(ret, sig_jump)
        ll_max = max(max(ll1, ll0), ll_jump)
        lam = g_lambda_dynamic
        lik1_mix = (1.0 - lam) * np.exp(ll1 - ll_max) + lam * np.exp(ll_jump - ll_max)
        lik0_mix = (1.0 - lam) * np.exp(ll0 - ll_max) + lam * np.exp(ll_jump - ll_max)
        lik1 = p1_pred * lik1_mix
        lik0 = p0_pred * lik0_mix
        norm_f = lik1 + lik0
        prob = lik1 / norm_f if norm_f > 1e-14 else p1_pred
        b_p1[i] = max(1e-4, min(0.9999, prob))
        hmm_prob = b_p1[i]

        t_scale = g_nu_dynamic / (g_nu_dynamic - 2.0) if g_nu_dynamic > 2.0 else 1.5
        var_t = (sig_t * sig_t) * t_scale
        var_j = sig_jump * sig_jump
        mu_s_val = mu_bull_ou if hmm_prob > 0.5 else -mu_bear_ou
        e_var_cond = (1.0 - lam) * var_t + lam * var_j + lam * (1.0 - lam) * (mu_s_val * mu_s_val)
        var_e_cond = hmm_prob * (1.0 - hmm_prob) * ((1.0 - lam) ** 2.0) * ((mu_bull_ou + mu_bear_ou) ** 2.0)
        b_sig_proj[i] = np.sqrt(max(e_var_cond + var_e_cond, 1e-12))

        confidence = abs(hmm_prob - 0.5) * 2.0
        hma_val_prev = b_hma_val[max(i - 5, 0)]
        b_hma_raw_slope[i] = (b_hma_val[i] - hma_val_prev) / 5.0
        vol_ratio = gjr_sigma / lr_sigma
        hma_thresh_abs = atr_i * params["ExtSlopeT"]
        hma_slope_mag = abs(b_hma_raw_slope[i]) / max(hma_thresh_abs / max(params["ExtSlopeT"], 0.0273), 1e-10)
        b_raw_conf[i] = confidence
        b_raw_vol[i] = vol_ratio
        b_raw_slope[i] = hma_slope_mag
        hma_accel_mag = abs(hma_slope_mag - b_raw_slope[max(i - 1, 0)])
        b_raw_accel[i] = hma_accel_mag

        lookback = min(i - min_start + 1, drift_window)
        if lookback < 2:
            lookback = 2
        conf_w = b_raw_conf[i - lookback + 1:i + 1]
        vol_w = b_raw_vol[i - lookback + 1:i + 1]
        slope_w = b_raw_slope[i - lookback + 1:i + 1]
        accel_w = b_raw_accel[i - lookback + 1:i + 1]
        s_conf = CStatistics.calculate_z_score(confidence, np.mean(conf_w), max(np.std(conf_w, ddof=1), 1e-6))
        s_vol = CStatistics.calculate_z_score(vol_ratio, np.mean(vol_w), max(np.std(vol_w, ddof=1), 1e-6))
        s_slope = CStatistics.calculate_z_score(hma_slope_mag, np.mean(slope_w), max(np.std(slope_w, ddof=1), 1e-6))
        s_accel = CStatistics.calculate_z_score(hma_accel_mag, np.mean(accel_w), max(np.std(accel_w, ddof=1), 1e-6))
        
        # Ablación: sin HMA
        if ablation_mode == "no_hma":
            s_slope = 0.0
            s_accel = 0.0

        z = (
            params["ExtWConf"] * s_conf
            + params["ExtWVol"] * s_vol
            + params["ExtWSlope"] * s_slope
            + params["ExtWAccel"] * s_accel
            + params["ExtWInter"]
        )
        b_strength[i] = CStatistics.logistic_clamped(z)
        
        # Ablación: sin ML strength o solo régimen
        if ablation_mode in {"no_strength", "regime_only"}:
            b_strength[i] = 1.0

        # Threshold dinámico por volatilidad
        if dynamic_threshold:
            current_threshold = threshold + dynamic_threshold_k * (vol_ratio - 1.0)
            current_threshold = max(dynamic_threshold_min, min(dynamic_threshold_max, current_threshold))
        else:
            current_threshold = threshold

        hmm_bull = hmm_prob > current_threshold
        hmm_bear = hmm_prob < (1.0 - current_threshold)
        
        # Ablación: sin HMM (el régimen direccional depende del Kalman)
        if ablation_mode == "no_hmm":
            hmm_bull = b_kalman_regime[i] > 0
            hmm_bear = b_kalman_regime[i] < 0

        gate_bull_ok = (not kalman_gate) or b_kalman_regime[i] > 0
        gate_bear_ok = (not kalman_gate) or b_kalman_regime[i] < 0
        
        # Ablación: sin Kalman o solo régimen o sin HMM
        if ablation_mode in {"no_kalman", "regime_only", "no_hmm"}:
            gate_bull_ok = True
            gate_bear_ok = True

        regime = 1 if (hmm_bull and gate_bull_ok) else (-1 if (hmm_bear and gate_bear_ok) else 0)
        b_regime[i] = regime
        if regime == 1 and b_regime[max(i - 1, 0)] != 1 and b_strength[i] > min_strength:
            b_to_bull[i] = low[i] - 10.0 * point
        if regime == -1 and b_regime[max(i - 1, 0)] != -1 and b_strength[i] > min_strength:
            b_to_bear[i] = high[i] + 10.0 * point

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "shifted_close_F_t1": b_shifted_close,
        "returns_t": b_returns,
        "ATR_14": b_atr,
        "HMM_Prob_Bull": b_p1,
        "Regime_Buffer_18": b_regime,
        "ML_Master_Strength": b_strength,
        "Vol_Projected_Sigma": b_sig_proj,
        "GJR_GARCH_Varianza": b_sigma2_gjr,
        "Kalman_Precio_Medio": b_kalman_x,
        "Kalman_Covarianza_P": b_kalman_p,
        "Kalman_Slope": b_kalman_slope,
        "Kalman_Regime": b_kalman_regime,
        "HMA_Value": b_hma_val,
        "HMA_Raw_Slope": b_hma_raw_slope,
        "Raw_Confidence": b_raw_conf,
        "Raw_Vol_Ratio": b_raw_vol,
        "Raw_Slope_Mag": b_raw_slope,
        "Raw_Accel_Mag": b_raw_accel,
        "Entry_Bull_Buffer_6": b_to_bull,
        "Entry_Bear_Buffer_7": b_to_bear,
    }, index=df.index)
