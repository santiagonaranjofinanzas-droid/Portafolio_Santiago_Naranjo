import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from data_engine import DataEngine
from pca_isri import PCAEngine
from hmm_regimes import HMMRegimes
from xgb_predictor import XGBPredictor
from sklearn.metrics import classification_report, roc_auc_score, brier_score_loss
from visualization_engine import ThesisVisualizer
from evaluation_metrics import ModelEvaluator
from statistical_tests import StatisticalAuditor

def transform_to_clr(hmm_probs_df):
    """Aplica la transformación CLR para romper la restricción del simplex."""
    # Evitar log(0) añadiendo una pequeña constante de regularización (épsilon)
    eps = 1e-6
    smoothed_probs = hmm_probs_df + eps
    geom_mean = np.exp(np.log(smoothed_probs).mean(axis=1))
    
    clr_df = pd.DataFrame(index=hmm_probs_df.index)
    for col in hmm_probs_df.columns:
        clr_df[f'CLR_{col}'] = np.log(smoothed_probs[col] / geom_mean)
    return clr_df

def run_thesis_pipeline(start_date='2015-01-01', n_regimes=3):
    print("=== Iniciando Pipeline del Sistema Híbrido ISRI-HMM-XGB ===\n")
    
    # Punto crucial de la auditoría: Definir el split de entrenamiento
    train_split = '2021-12-31'
    
    # 1. Obtención y Preprocesamiento de Datos (Con prevención de fuga)
    engine = DataEngine()
    df_raw = engine.download_data(start_date=start_date)
    df_clean, scaler = engine.preprocess(df_raw, training_split=train_split)
    print(f"Módulo 1: Datos preprocesados (Escalador ajustado hasta {train_split}).")
    
    # 2. Extracción del Índice ISRI (PCA con prevención de fuga)
    pca_tool = PCAEngine()
    isri = pca_tool.fit_isri(df_clean, training_split=train_split)
    expl_var = pca_tool.get_explained_variance()
    print(f"Módulo 2: ISRI calculado (PCA ajustado hasta {train_split}).")
    
    # === Auditoría Estadística: Estacionariedad ===
    print("\n--- Auditoría Estadística: Estacionariedad ISRI ---")
    auditor = StatisticalAuditor()
    estacionariedad = auditor.test_stationarity(isri, "ISRI (PC1)")
    print(estacionariedad)
    
    # 3. Identificación de Regímenes (HMM con prevención de fuga y Caché)
    hmm_tool = HMMRegimes(n_regimes=n_regimes)
    hmm_results = hmm_tool.fit_predict(isri, training_split=train_split, use_cache=True)
    print(f"\nMódulo 3: HMM ajustado hasta {train_split} (Caché habilitado).")
    
    # 4. Predicción de Transiciones (XGBoost con Embargo y CLR)
    # Mapear las probabilidades del HMM al espacio real para romper el simplex
    hmm_probs = hmm_results.iloc[:, :n_regimes]
    clr_probs = transform_to_clr(hmm_probs)
    
    features = pd.concat([isri, clr_probs], axis=1)
    xgb_tool = XGBPredictor()
    
    # Usar target financiero basado en drawdowns del S&P500
    target = xgb_tool.prepare_academic_target(df_raw, hmm_results['State'], horizon=5)
    
    # Alinear los índices de características y target usando su intersección (evita KeyError por fechas con NaNs)
    common_idx = features.index.intersection(target.index)
    X_raw = features.loc[common_idx]
    y = target.loc[common_idx]
    
    # Aislar estrictamente el set de entrenamiento
    X_train_raw = X_raw.loc[:train_split]
    y_train = y.loc[:train_split]
    
    # Purga de Frontera (Boundary Purge)
    horizon = 5
    X_train_raw = X_train_raw.iloc[:-horizon]
    y_train = y_train.iloc[:-horizon]
    
    print("Mapeando características en su espacio real (preservando interpretabilidad)...")
    # Conservamos X_raw directamente, eliminando el segundo PCA que destruye la interpretabilidad
    X = X_raw.copy()
    X_train = X.loc[X_train_raw.index]
    
    print(f"Módulo 4: Ejecutando entrenamiento XGBoost (Entrenamiento Purgado hasta {train_split} - {horizon}d)...")
    xgb_tool.train_with_optuna(X_train, y_train, n_trials=20)
    
    # === Tarea 3: Evaluación de Entrenamiento y Out-of-Sample (OOS) ===
    print("\n--- Evaluación de Desempeño Train vs Test ---")
    
    y_prob_train = xgb_tool.predict(X_train)
    auc_train = roc_auc_score(y_train, y_prob_train)
    brier_train = brier_score_loss(y_train, y_prob_train)
    
    print("MÉTRICAS DE ENTRENAMIENTO (IS):")
    print(f"{'ROC AUC:':<25} {auc_train:.4f}")
    print(f"{'Brier Score:':<25} {brier_train:.4f}")
    
    X_test = X.loc[train_split:]
    y_test = y.loc[train_split:]
    
    resultados_auditoria = []
    resultados_auditoria.append(estacionariedad)
    
    if len(X_test) > 0:
        y_prob_test = xgb_tool.predict(X_test)
        y_pred_test = (y_prob_test > 0.5).astype(int)
        
        auc_test = roc_auc_score(y_test, y_prob_test)
        brier_test = brier_score_loss(y_test, y_prob_test)
        
        print("\nMÉTRICAS DE PRUEBA (OOS):")
        print(f"{'ROC AUC:':<25} {auc_test:.4f}")
        print(f"{'Brier Score:':<25} {brier_test:.4f}")
        print("\nClassification Report (Test):")
        print(classification_report(y_test, y_pred_test))
        
        # === Auditoría Estadística: Pruebas Avanzadas ===
        print("\n--- Auditoría Estadística Rigurosa (OOS) ---")
        
        # 1. Test de Ljung-Box en Residuos
        residuos = y_test - y_prob_test
        residuos_series = pd.Series(residuos, index=y_test.index)
        lb_test = auditor.test_ljung_box(residuos_series, lags=10)
        print("Ljung-Box Test (Residuos):", lb_test)
        lb_test["Serie"] = "Residuos_XGB"
        resultados_auditoria.append(lb_test)
        
        # 2. Test Diebold-Mariano (Comparación contra baseline Naive: siempre predice clase mayoritaria 0)
        y_pred_naive = np.zeros(len(y_test))
        dm_test = auditor.diebold_mariano_test(y_test, y_prob_test, y_pred_naive)
        print("Diebold-Mariano Test (XGB vs Naive):", dm_test)
        dm_test["Serie"] = "XGB vs Naive"
        resultados_auditoria.append(dm_test)
        
        # 3. Test de Causalidad de Granger (¿ISRI causa Target?)
        granger_data = pd.concat([y, isri], axis=1)
        granger_data.columns = ['Target', 'Predictor']
        granger_test = auditor.test_granger_causality(granger_data, maxlag=5)
        print("Granger Causality (ISRI -> Target):", granger_test)
        granger_test["Serie"] = "ISRI -> Target"
        resultados_auditoria.append(granger_test)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.abspath(os.path.join(script_dir, '../resultados'))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # 4. Explicabilidad con SHAP
        shap_output_path = os.path.join(output_dir, 'shap_summary_plot.png')
        xgb_tool.explain_model_shap(X_test, output_path=shap_output_path)
        
        # === Módulo 5: Generación de Gráficos para la Tesis ===
        print("\nGenerando suite de visualizaciones para la tesis...")
        viz = ThesisVisualizer()
        
        # 1. Gráficos de PCA
        viz.plot_pca_loadings(pca_tool.loadings)
        viz.plot_isri_timeseries(isri)
        
        # 2. Gráficos de HMM
        viz.plot_hmm_states(isri, hmm_results['State'])
        viz.plot_regime_distributions(isri, hmm_results['State'])
        viz.plot_state_probabilities(hmm_results.iloc[:, :n_regimes])
        
        # 3. Gráficos de XGBoost
        viz.plot_confusion_matrix(y_test, y_pred_test)
        viz.plot_roc_curves({
            'Train (In-Sample)': (y_train, y_prob_train),
            'Test (Out-of-Sample)': (y_test, y_prob_test)
        })
        viz.plot_calibration_curve(y_test, y_prob_test)
        viz.plot_feature_importance(xgb_tool.model, X.columns)
        
        # === Módulo 6: Evaluación Académica Completa (ModelEvaluator) ===
        # ==============================================================================
        # PIPELINE PREMIUM: MOTOR DE ALPHA BASADO EN PORTAFOLIO GMV CONDICIONAL (EWMA)
        # ==============================================================================
        print("\n[ALPHA OPTIMIZER] Iniciando optimizador GMV con covarianza dinámica EWMA...")

        # 1. Extraer los retornos normalizados y escalados inversamente de los 5 activos
        # Usamos el DataFrame original para calcular covarianzas financieras de test
        raw_returns = np.log(df_raw / df_raw.shift(1)).dropna()
        if 'BOND10Y' in raw_returns.columns:
            raw_returns['BOND10Y'] = -raw_returns['BOND10Y']

        # Sincronizar con el indice del set de prueba
        test_idx = y_test.index.intersection(raw_returns.index)
        returns_test_assets = raw_returns.loc[test_idx]

        # 2. Obtener las probabilidades predictivas continuas alineadas temporalmente
        p_t = pd.Series(y_prob_test, index=y_test.index).loc[test_idx]

        # 3. Estimar matrices de covarianza EWMA dinámicas (RiskMetrics)
        # En lugar de matrices estáticas IS, usamos un estimador de ventana exponencial
        # que adapta la estructura de correlaciones en tiempo real sin suponer estacionariedad.
        # Referencia: J.P. Morgan RiskMetrics (1996), Engle (2002)
        EWMA_SPAN = 63         # ~3 meses, estándar RiskMetrics (λ ≈ 0.969)
        EWMA_MIN_PERIODS = 21  # ~1 mes, mínimo para invertibilidad 5×5

        # === CAPA 3: Kappas Asimétricos por Clase de Activo ===
        # Justificación económica: en estrés, la volatilidad de renta variable
        # y commodities cíclicas SUBE, mientras que la de refugios BAJA.
        # V(t) = diag(1 + κᵢ·p(t))  →  Σ_pred = V·Σ_ewma·V
        # Al romper la simetría escalar, la inversa NO cancela el factor.
        KAPPA_POR_ACTIVO = np.array([
            2.0,   # SP500:  máxima penalización (equity risk premium sube)
            -0.5,  # GOLD:   refugio principal (vol relativa BAJA en estrés)
            1.5,   # OIL:    commodity cíclica (alta beta al ciclo)
            -0.3,  # BOND10Y: flight-to-quality (demanda de bonos sube)
            0.5,   # USD:    refugio parcial (DXY mixto en crisis)
        ])  # Orden: SP500, GOLD, OIL, BOND10Y, USD

        # === CAPA 2: Volatility Targeting Overlay ===
        # Referencia: Moreira & Muir (2017) "Volatility-Managed Portfolios"
        SIGMA_BASE_ANUAL = 0.10  # Target de volatilidad anualizada: 10%
        SIGMA_BASE_DIARIA = SIGMA_BASE_ANUAL / np.sqrt(252)
        KAPPA_VOL = 1.5  # Factor de contracción de vol target en estrés

        assets_list = ['SP500', 'GOLD', 'OIL', 'BOND10Y', 'USD']
        all_returns_assets = raw_returns[assets_list]

        # Pre-cómputo vectorizado de la serie completa de covarianzas EWMA
        print(f"[EWMA COV] Pre-computando matrices de covarianza dinámicas (span={EWMA_SPAN})...")
        ewma_cov_multi = all_returns_assets.ewm(
            span=EWMA_SPAN, min_periods=EWMA_MIN_PERIODS
        ).cov()

        # Diccionario de lookup causal: fecha → matriz 5×5 numpy
        cov_dates = ewma_cov_multi.index.get_level_values(0).unique()
        cov_lookup = {d: ewma_cov_multi.loc[d].values for d in cov_dates}
        all_dates_sorted = all_returns_assets.index
        print(f"[EWMA COV] {len(cov_lookup)} matrices dinámicas estimadas.")

        # 4. Bucle de Inferencia Causal OOS (GMV Dinámico: Asimétrico + Vol Targeting)
        strat_returns_list = []
        costo_transaccion_bps = 0.0002
        pesos_anteriores = np.array([1.0, 0.0, 0.0, 0.0, 0.0])  # Empezar 100% S&P500
        n_assets = len(assets_list)

        # Forzar causalidad estricta: probabilidad de hoy genera pesos de mañana
        p_t_causal = p_t.shift(1).fillna(0.1)  # Prior conservador para t=0

        for date, prob in p_t_causal.items():
            # --- Paso 1: Extraer Σ_ewma causal (datos hasta t-1) ---
            date_loc = all_dates_sorted.get_loc(date)
            if date_loc > 0:
                prev_date = all_dates_sorted[date_loc - 1]
                cov_ewma = cov_lookup.get(prev_date, np.eye(n_assets) * 1e-3)
            else:
                cov_ewma = np.eye(n_assets) * 1e-3

            # --- Paso 2 (Capa 3): Amplificación Asimétrica por Activo ---
            # V(t) = diag(1 + κᵢ · p(t))
            # Σ_pred = V · Σ_ewma · V  ←  NO se cancela en el GMV
            v_diag = 1.0 + KAPPA_POR_ACTIVO * prob
            V = np.diag(v_diag)
            cov_predictiva = V @ cov_ewma @ V

            # --- Paso 3: Resolver GMV analítico sin posiciones cortas ---
            try:
                inv_sigma = np.linalg.inv(cov_predictiva + np.eye(n_assets) * 1e-6)
                unos = np.ones(n_assets)
                w_risky = np.dot(inv_sigma, unos) / np.dot(unos, np.dot(inv_sigma, unos))
                w_risky = np.clip(w_risky, 0.0, 1.0)
                w_risky /= np.sum(w_risky)
            except np.linalg.LinAlgError:
                w_risky = pesos_anteriores

            # --- Paso 4 (Capa 2): Volatility Targeting Overlay ---
            # σ_p = √(w' · Σ_ewma · w)  (vol del portafolio base, sin amplificar)
            sigma_portfolio = np.sqrt(np.dot(w_risky, np.dot(cov_ewma, w_risky)))

            # Target dinámico: se contrae proporcionalmente al riesgo detectado
            sigma_target = SIGMA_BASE_DIARIA / (1.0 + KAPPA_VOL * prob)

            # φ(t) = min(1, σ_target / σ_portfolio) → escala la exposición total
            if sigma_portfolio > 1e-8:
                phi = min(1.0, sigma_target / sigma_portfolio)
            else:
                phi = 1.0

            # Pesos finales: φ en activos de riesgo, (1-φ) en cash implícito
            w_final = w_risky * phi

            # --- Paso 5: Calcular retorno del portafolio ---
            retornos_dia = returns_test_assets.loc[date, assets_list].values
            ret_estrategia_bruto = np.dot(w_final, retornos_dia)
            # Nota: la porción (1-φ) en cash genera retorno ≈ 0 (conservador)

            # Penalización friccional de rebalanceo (Turnover de portafolio)
            turnover = np.sum(np.abs(w_final - pesos_anteriores))
            friccion = turnover * costo_transaccion_bps

            strat_returns_list.append(ret_estrategia_bruto - friccion)
            pesos_anteriores = w_final

        # 5. Inyectar la serie final optimizada al evaluador de métricas de la tesis
        strat_returns = pd.Series(strat_returns_list, index=test_idx)
        print("[ALPHA OPTIMIZER] Frontera GMV-EWMA resuelta en tiempo real OOS de forma causal.")

        y_prob_test_series = pd.Series(y_prob_test, index=y_test.index)

        evaluator = ModelEvaluator(
            y_true=y_test.loc[strat_returns.index],
            y_proba=y_prob_test_series.loc[strat_returns.index],
            returns_strategy=strat_returns,
            threshold=0.5,
            risk_free_rate=0.0
        )
        df_resultados = evaluator.to_summary_dataframe()
        
    else:
        print("ADVERTENCIA: No hay suficientes datos para la evaluación OOS.")
        df_resultados = None

    print("\n=== Pipeline Completado con Éxito ===")
    
    # Calcular retornos del training set sin escalar para exportar scaler_params (con prevención de fuga y corrección de signo)
    df_train_raw = df_raw.loc[:train_split].ffill().dropna()
    train_returns = np.log(df_train_raw / df_train_raw.shift(1))
    if 'BOND10Y' in train_returns.columns:
        train_returns['BOND10Y'] = -train_returns['BOND10Y']
    train_returns = train_returns.dropna()

    return {
        'isri': isri,
        'hmm_results': hmm_results,
        'loadings': pca_tool.loadings,
        'xgb_model': xgb_tool.model,
        'hmm_model': hmm_tool.model,
        'train_returns': train_returns,
        'metricas_oos': df_resultados,
        'auditoria': pd.DataFrame(resultados_auditoria)
    }

if __name__ == "__main__":
    results = run_thesis_pipeline()
    
    # Guardar resultados supervisados para el Capítulo 5
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(script_dir, '../resultados'))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    results['isri'].to_csv(os.path.join(output_dir, 'isri_supervisado.csv'))
    results['hmm_results'].to_csv(os.path.join(output_dir, 'hmm_supervisado.csv'))
    
    if results['metricas_oos'] is not None:
        results['metricas_oos'].to_csv(os.path.join(output_dir, 'metricas_oos.csv'), index=False)
        print(f"\nMétricas OOS exportadas a {output_dir}/metricas_oos.csv")
        
    if results['auditoria'] is not None:
        results['auditoria'].to_csv(os.path.join(output_dir, 'auditoria_estadistica.csv'), index=False)
        print(f"Reporte de Auditoría Estadística exportado a {output_dir}/auditoria_estadistica.csv")
    
    print(f"Resultados supervisados exportados a {output_dir}/")
