"""
benchmark_layers.py
====================
Sistema de Validación por Capas de Complejidad Incremental.

Ejecuta 4 capas de benchmarks sobre el mismo periodo OOS y genera
una tabla comparativa exhaustiva para el capítulo de Resultados de la tesis.

Capas:
  0: Buy & Hold S&P 500 (benchmark pasivo)
  1: Rotación Táctica por Signo del ISRI (PCA solamente)
  2: HMM Markov-Switching GMV Estático (PCA + HMM, sin EWMA)
  3: Sistema Híbrido Completo (PCA + CLR + HMM + XGBoost + EWMA + Vol Targeting)

Referencias:
  - Bailey & López de Prado (2014): Deflated Sharpe Ratio
  - Moreira & Muir (2017): Volatility-Managed Portfolios
  - J.P. Morgan RiskMetrics (1996): EWMA Covariance

Autor: Pipeline de Tesis (Estadístico Estocástico)
"""

import pandas as pd
import numpy as np
import os
from scipy import stats
from data_engine import DataEngine
from pca_isri import PCAEngine
from hmm_regimes import HMMRegimes
from xgb_predictor import XGBPredictor

#=============================================================================
#CONFIGURACIÓN GLOBAL
#=============================================================================
TRAIN_SPLIT = '2021-12-31'
START_DATE = '2015-01-01'
N_REGIMES = 3
EWMA_SPAN = 63
EWMA_MIN_PERIODS = 21
KAPPA_POR_ACTIVO = np.array([2.0, -0.5, 1.5, -0.3, 0.5])  # SP500, GOLD, OIL, BOND10Y, USD
SIGMA_BASE_ANUAL = 0.10
KAPPA_VOL = 1.5
COSTO_BPS = 0.0002
ASSETS = ['SP500', 'GOLD', 'OIL', 'BOND10Y', 'USD']
N_OPTUNA_TRIALS = 20


#=============================================================================
#UTILIDADES
#=============================================================================
def transform_to_clr(hmm_probs_df):
    """Aplica la transformación CLR para romper la restricción del simplex."""
    eps = 1e-6
    smoothed = hmm_probs_df + eps
    geom_mean = np.exp(np.log(smoothed).mean(axis=1))
    clr_df = pd.DataFrame(index=hmm_probs_df.index)
    for col in hmm_probs_df.columns:
        clr_df[f'CLR_{col}'] = np.log(smoothed[col] / geom_mean)
    return clr_df


def solve_gmv(cov_matrix, n_assets):
    """Resuelve analíticamente el portafolio GMV long-only regularizado."""
    try:
        inv_s = np.linalg.inv(cov_matrix + np.eye(n_assets) * 1e-6)
        ones = np.ones(n_assets)
        w = np.dot(inv_s, ones) / np.dot(ones, np.dot(inv_s, ones))
        w = np.clip(w, 0.0, 1.0)
        w /= np.sum(w)
        return w
    except np.linalg.LinAlgError:
        return None


def compute_metrics(returns, name, n_trials=1):
    """
    Calcula la batería completa de métricas institucionales OOS.
    
    Incluye el Deflated Sharpe Ratio de Bailey & López de Prado (2014)
    para certificar significancia estadística neta de data snooping.
    """
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n == 0:
        return {'Capa': name}

    cumulative = np.cumprod(1 + r)
    n_years = n / 252

    # CAGR
    cagr = float(cumulative[-1] ** (1 / n_years) - 1) if n_years > 0 else 0.0

    # Volatilidad anualizada
    vol = float(np.std(r, ddof=1) * np.sqrt(252))

    # Sharpe Ratio (anualizado, rf=0)
    mean_d = np.mean(r)
    std_d = np.std(r, ddof=1)
    sharpe = float(mean_d / std_d * np.sqrt(252)) if std_d > 0 else 0.0

    # Sortino Ratio (anualizado, target=0)
    downside = np.minimum(r, 0.0)
    dd_dev = np.sqrt(np.mean(downside ** 2))
    sortino = float(mean_d / dd_dev * np.sqrt(252)) if dd_dev > 0 else 0.0

    # Max Drawdown
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    mdd = float(np.min(drawdowns))

    # Calmar Ratio = CAGR / MDD
    calmar = float(cagr / abs(mdd)) if abs(mdd) > 1e-8 else 0.0

    # --- Deflated Sharpe Ratio (Bailey & López de Prado, 2014) ---
    # Usa SR diario para el cálculo estadístico
    sr_daily = float(mean_d / std_d) if std_d > 0 else 0.0
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))  # Raw kurtosis (no excess)

    # Umbral SR₀: máximo esperado bajo la nula (iid normal) para N trials
    gamma_em = 0.5772156649  # Constante de Euler-Mascheroni
    if n_trials > 1:
        z1 = stats.norm.ppf(1 - 1 / n_trials)
        z2 = stats.norm.ppf(1 - 1 / (n_trials * np.e))
        sr0 = (1 - gamma_em) * z1 + gamma_em * z2
        sr0 *= np.sqrt(1 / (n - 1))  # Escalar a la varianza del estimador
    else:
        sr0 = 0.0

    # PSR: probabilidad de que el SR verdadero supere sr0
    var_sr = (1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2) / (n - 1)
    if var_sr > 0:
        dsr = float(stats.norm.cdf((sr_daily - sr0) / np.sqrt(var_sr)))
    else:
        dsr = 0.5

    return {
        'Capa': name,
        'CAGR': round(cagr, 4),
        'Volatilidad': round(vol, 4),
        'Sharpe': round(sharpe, 4),
        'Sortino': round(sortino, 4),
        'Calmar': round(calmar, 4),
        'MDD': round(mdd, 4),
        'DSR': round(dsr, 4),
    }


def compute_turnover(weights_history):
    """Calcula el turnover diario promedio."""
    if len(weights_history) < 2:
        return 0.0
    turnovers = [np.sum(np.abs(weights_history[i] - weights_history[i - 1]))
                 for i in range(1, len(weights_history))]
    return float(np.mean(turnovers))


#=============================================================================
#PIPELINE PRINCIPAL
#=============================================================================
def main():
    print("=" * 70)
    print("  SISTEMA DE VALIDACION POR CAPAS DE COMPLEJIDAD INCREMENTAL")
    print("  Periodo IS: 2015-01-01 -> 2021-12-31")
    print("  Periodo OOS: 2022-01-01 -> Presente")
    print("=" * 70)

    n_assets = len(ASSETS)

    # === Módulos compartidos ===
    print("\n[DATOS] Cargando y preprocesando universo multi-activo...")
    engine = DataEngine()
    df_raw = engine.download_data(start_date=START_DATE)
    df_clean, scaler = engine.preprocess(df_raw, training_split=TRAIN_SPLIT)

    # Retornos logarítmicos crudos (con corrección de signo para bonos)
    raw_returns = np.log(df_raw / df_raw.shift(1)).dropna()
    if 'BOND10Y' in raw_returns.columns:
        raw_returns['BOND10Y'] = -raw_returns['BOND10Y']

    print("[PCA] Extrayendo ISRI...")
    pca_tool = PCAEngine()
    isri = pca_tool.fit_isri(df_clean, training_split=TRAIN_SPLIT)

    print("[HMM] Identificando regímenes latentes...")
    hmm_tool = HMMRegimes(n_regimes=N_REGIMES)
    hmm_results = hmm_tool.fit_predict(isri, training_split=TRAIN_SPLIT, use_cache=True)

    print("[XGB] Entrenando clasificador con purga y embargo...")
    hmm_probs = hmm_results.iloc[:, :N_REGIMES]
    clr_probs = transform_to_clr(hmm_probs)
    features = pd.concat([isri, clr_probs], axis=1)
    xgb_tool = XGBPredictor()
    target = xgb_tool.prepare_academic_target(df_raw, hmm_results['State'], horizon=5)

    common_idx = features.index.intersection(target.index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    X_train = X.loc[:TRAIN_SPLIT].iloc[:-5]
    y_train = y.loc[:TRAIN_SPLIT].iloc[:-5]
    xgb_tool.train_with_optuna(X_train, y_train, n_trials=N_OPTUNA_TRIALS)

    X_test = X.loc[TRAIN_SPLIT:]
    y_test = y.loc[TRAIN_SPLIT:]
    y_prob_test = xgb_tool.predict(X_test)

    # --- Periodo OOS común a todas las capas ---
    oos_returns = raw_returns.loc[TRAIN_SPLIT:].iloc[1:]
    common_oos = oos_returns.index.intersection(y_test.index)
    oos_aligned = oos_returns.loc[common_oos, ASSETS]

    print(f"\n{'-' * 50}")
    print(f"  Periodo OOS: {common_oos[0].date()} -> {common_oos[-1].date()}")
    print(f"  Observaciones: {len(common_oos)} dias de negociacion")
    print(f"{'-' * 50}")

    # ==================================================================
    #  CAPA 0: Buy & Hold S&P 500
    # ==================================================================
    print("\n[CAPA 0] Buy & Hold S&P 500 (Benchmark Pasivo)...")
    ret_c0 = oos_aligned['SP500'].values
    m_c0 = compute_metrics(ret_c0, 'C0: Buy & Hold SP500', n_trials=1)
    m_c0['Turnover'] = 0.0

    # ==================================================================
    #  CAPA 1: Rotación Táctica por Signo del ISRI
    # ==================================================================
    print("[CAPA 1] Rotacion Tactica ISRI (SP500 <-> GOLD)...")
    isri_causal = isri.shift(1).loc[common_oos]

    ret_c1_list, wts_c1 = [], []
    w_prev = np.array([1.0, 0.0, 0.0, 0.0, 0.0])

    for date in common_oos:
        sig = isri_causal.get(date, 0.0)
        if pd.isna(sig):
            sig = 0.0

        # ISRI > 0 → 100% SP500 (Risk-On), ISRI ≤ 0 → 100% GOLD (Refugio)
        w = np.array([1.0, 0.0, 0.0, 0.0, 0.0]) if sig > 0 else \
            np.array([0.0, 1.0, 0.0, 0.0, 0.0])

        ret_dia = oos_aligned.loc[date, ASSETS].values
        to = np.sum(np.abs(w - w_prev))
        ret_c1_list.append(np.dot(w, ret_dia) - to * COSTO_BPS)
        wts_c1.append(w.copy())
        w_prev = w

    m_c1 = compute_metrics(np.array(ret_c1_list), 'C1: ISRI Rotation', n_trials=1)
    m_c1['Turnover'] = round(compute_turnover(wts_c1), 4)

    # ==================================================================
    #  CAPA 2: HMM Markov-Switching GMV Estático
    # ==================================================================
    print("[CAPA 2] HMM Markov-Switching GMV Estático...")

    # Matrices de covarianza ESTÁTICAS (IS)
    train_ret = raw_returns.loc[:TRAIN_SPLIT]
    hmm_st_train = hmm_results.loc[:TRAIN_SPLIT, 'State']
    ci = train_ret.index.intersection(hmm_st_train.index)
    tr_aligned = train_ret.loc[ci, ASSETS]
    st_aligned = hmm_st_train.loc[ci]

    is_stress = (st_aligned == 2)
    cov_normal = tr_aligned[~is_stress].cov().values if (~is_stress).sum() >= 21 \
        else tr_aligned.cov().values
    cov_stress = tr_aligned[is_stress].cov().values if is_stress.sum() >= 21 \
        else tr_aligned.cov().values

    # Estado HMM causal (shift(1)) para OOS
    hmm_st_oos = hmm_results.loc[common_oos, 'State'].shift(1).fillna(0).astype(int)

    ret_c2_list, wts_c2 = [], []
    w_prev = np.array([1.0, 0.0, 0.0, 0.0, 0.0])

    for date in common_oos:
        state = hmm_st_oos.loc[date]
        cov_sel = cov_stress if state == 2 else cov_normal

        w = solve_gmv(cov_sel, n_assets)
        if w is None:
            w = w_prev

        ret_dia = oos_aligned.loc[date, ASSETS].values
        to = np.sum(np.abs(w - w_prev))
        ret_c2_list.append(np.dot(w, ret_dia) - to * COSTO_BPS)
        wts_c2.append(w.copy())
        w_prev = w

    m_c2 = compute_metrics(np.array(ret_c2_list), 'C2: HMM Static GMV', n_trials=1)
    m_c2['Turnover'] = round(compute_turnover(wts_c2), 4)

    # ==================================================================
    #  CAPA 3: Sistema Híbrido Completo
    # ==================================================================
    print("[CAPA 3] Sistema Híbrido (EWMA + Asimétrico + Vol Targeting)...")

    # Pre-cómputo EWMA
    all_ret = raw_returns[ASSETS]
    ewma_multi = all_ret.ewm(span=EWMA_SPAN, min_periods=EWMA_MIN_PERIODS).cov()
    cov_dates = ewma_multi.index.get_level_values(0).unique()
    cov_lookup = {d: ewma_multi.loc[d].values for d in cov_dates}
    all_dates = all_ret.index

    p_t = pd.Series(y_prob_test, index=y_test.index).loc[common_oos]
    p_causal = p_t.shift(1).fillna(0.1)
    sigma_base_d = SIGMA_BASE_ANUAL / np.sqrt(252)

    ret_c3_list, wts_c3 = [], []
    w_prev = np.array([1.0, 0.0, 0.0, 0.0, 0.0])

    for date in common_oos:
        prob = p_causal.get(date, 0.1)
        if pd.isna(prob):
            prob = 0.1

        # EWMA causal
        dloc = all_dates.get_loc(date)
        if dloc > 0:
            cov_ewma = cov_lookup.get(all_dates[dloc - 1], np.eye(n_assets) * 1e-3)
        else:
            cov_ewma = np.eye(n_assets) * 1e-3

        # Capa 3: Amplificación Asimétrica
        v = 1.0 + KAPPA_POR_ACTIVO * prob
        V = np.diag(v)
        cov_pred = V @ cov_ewma @ V

        # GMV
        w_risky = solve_gmv(cov_pred, n_assets)
        if w_risky is None:
            w_risky = w_prev

        # Vol Targeting Overlay
        sig_p = np.sqrt(np.dot(w_risky, np.dot(cov_ewma, w_risky)))
        sig_tgt = sigma_base_d / (1.0 + KAPPA_VOL * prob)
        phi = min(1.0, sig_tgt / sig_p) if sig_p > 1e-8 else 1.0
        w_final = w_risky * phi

        ret_dia = oos_aligned.loc[date, ASSETS].values
        to = np.sum(np.abs(w_final - w_prev))
        ret_c3_list.append(np.dot(w_final, ret_dia) - to * COSTO_BPS)
        wts_c3.append(w_final.copy())
        w_prev = w_final

    m_c3 = compute_metrics(np.array(ret_c3_list), 'C3: Hybrid EWMA+VT', n_trials=N_OPTUNA_TRIALS)
    m_c3['Turnover'] = round(compute_turnover(wts_c3), 4)

    # ==================================================================
    #  TABLA COMPARATIVA
    # ==================================================================
    df_out = pd.DataFrame([m_c0, m_c1, m_c2, m_c3])
    col_order = ['Capa', 'CAGR', 'Volatilidad', 'Sharpe', 'Sortino',
                 'Calmar', 'MDD', 'Turnover', 'DSR']
    df_out = df_out[col_order]

    print("\n" + "=" * 70)
    print("  TABLA COMPARATIVA OOS - CAPAS DE COMPLEJIDAD INCREMENTAL")
    print("=" * 70)
    print(df_out.to_string(index=False))

    # Exportar
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(script_dir, '../resultados'))
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, 'benchmark_capas_oos.csv')
    df_out.to_csv(out_path, index=False)
    print(f"\nResultados exportados a: {out_path}")

    return df_out


if __name__ == "__main__":
    results = main()
