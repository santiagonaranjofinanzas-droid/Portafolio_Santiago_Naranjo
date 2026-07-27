import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from data_engine import DataEngine
from pca_isri import PCAEngine
from hmm_regimes import HMMRegimes
from xgb_predictor import XGBPredictor
from sklearn.metrics import classification_report, roc_auc_score, brier_score_loss
from visualization_engine import ThesisVisualizer
from evaluation_metrics import ModelEvaluator

def run_thesis_pipeline(start_date='2015-01-01', n_regimes=3):
    print("=== Iniciando Pipeline del Sistema Híbrido ISRI-HMM-XGB ===\n")
    
    # Punto crucial de la auditoría: Definir el split de entrenamiento
    # Para la tesis, usaremos datos hasta finales de 2021 para entrenar y 2022+ para validar/test.
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
    
    # 3. Identificación de Regímenes (HMM con prevención de fuga y Caché)
    hmm_tool = HMMRegimes(n_regimes=n_regimes)
    hmm_results = hmm_tool.fit_predict(isri, training_split=train_split, use_cache=True)
    print(f"Módulo 3: HMM ajustado hasta {train_split} (Caché habilitado).")
    
    # 4. Predicción de Transiciones (XGBoost con Embargo)
    # Features en t
    features = pd.concat([isri, hmm_results.iloc[:, :n_regimes]], axis=1)
    xgb_tool = XGBPredictor()
    
    # Target en t+5 (Alineación causal)
    target = xgb_tool.prepare_target(isri, hmm_results['State'], horizon=5)
    
    # Alineamos features (t) con target (t+5)
    X = features.loc[target.index]
    y = target
    
    # CORRECCIÓN FUGA 3: Aislar estrictamente el set de entrenamiento para Optuna
    X_train = X.loc[:train_split]
    y_train = y.loc[:train_split]
    
    # NUEVO: CORRECCIÓN FARE 3 - Purga de Frontera (Boundary Purge)
    # Evita que el target t+5 del fin del entrenamiento vea el inicio del test
    horizon = 5
    X_train = X_train.iloc[:-horizon]
    y_train = y_train.iloc[:-horizon]
    
    print(f"Módulo 4: Ejecutando entrenamiento XGBoost (Entrenamiento Purgado hasta {train_split} - {horizon}d)...")
    xgb_tool.train_with_optuna(X_train, y_train, n_trials=20)
    
    # === Tarea 3: Evaluación de Entrenamiento y Out-of-Sample (OOS) ===
    print("\n--- Evaluación de Desempeño Train vs Test ---")
    
    # Evaluación In-Sample (Entrenamiento)
    y_prob_train = xgb_tool.predict(X_train)
    auc_train = roc_auc_score(y_train, y_prob_train)
    brier_train = brier_score_loss(y_train, y_prob_train)
    
    print("MÉTRICAS DE ENTRENAMIENTO (IS):")
    print(f"{'ROC AUC:':<25} {auc_train:.4f}")
    print(f"{'Brier Score:':<25} {brier_train:.4f}")
    
    # Evaluación Out-of-Sample (Prueba)
    X_test = X.loc[train_split:]
    y_test = y.loc[train_split:]
    
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
        evaluator = ModelEvaluator(
            y_true=y_test,
            y_proba=y_prob_test,
            threshold=0.5
        )
        df_resultados = evaluator.to_summary_dataframe()
        
    else:
        print("ADVERTENCIA: No hay suficientes datos para la evaluación OOS.")
        df_resultados = None

    print("\n=== Pipeline Completado con Éxito ===")
    
    # Calcular retornos del training set sin escalar para exportar scaler_params
    train_returns = np.log(df_raw / df_raw.shift(1)).dropna().loc[:train_split]

    # Retornamos los objetos clave para análisis posterior
    return {
        'isri': isri,
        'hmm_results': hmm_results,
        'loadings': pca_tool.loadings,
        'xgb_model': xgb_tool.model,
        'hmm_model': hmm_tool.model,
        'train_returns': train_returns,
        'metricas_oos': df_resultados
    }

if __name__ == "__main__":
    results = run_thesis_pipeline()
    
    # Guardar resultados supervisados para el Capítulo 5
    import os
    output_dir = '../resultados'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    results['isri'].to_csv(os.path.join(output_dir, 'isri_supervisado.csv'))
    results['hmm_results'].to_csv(os.path.join(output_dir, 'hmm_supervisado.csv'))
    
    if results['metricas_oos'] is not None:
        results['metricas_oos'].to_csv(os.path.join(output_dir, 'metricas_oos.csv'), index=False)
        print(f"\nMétricas OOS exportadas a {output_dir}/metricas_oos.csv")
    
    print(f"Resultados supervisados exportados a {output_dir}/")
