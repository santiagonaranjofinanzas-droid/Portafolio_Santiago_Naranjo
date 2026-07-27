"""
evaluation_metrics.py
=====================
Módulo de Evaluación Post-Entrenamiento para Tesis de Economía.

Propósito:
    Calcular métricas de discriminación estadística, calibración probabilística,
    análisis Precision-Recall y desempeño financiero/económico del sistema
    híbrido HMM-XGBoost, asegurando el rigor cuantitativo necesario para
    la defensa de un trabajo de grado en Economía.

Restricciones de Diseño:
    - Completamente DESACOPLADO del pipeline de entrenamiento.
    - No modifica objetos ni modelos existentes.
    - No ejecuta prints ni efectos secundarios.
    - Usa exclusivamente sklearn, numpy y pandas.
    - Salidas diseñadas para conversión directa a pd.DataFrame y exportación
      a tablas LaTeX/Word para el documento de tesis (APA 7ma edición).

Autor: Sistema de Tesis (Estadístico Estocástico + Redactor Académico)
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    matthews_corrcoef,
    log_loss,
    brier_score_loss,
    precision_recall_curve,
    auc
)
from sklearn.calibration import calibration_curve


class ModelEvaluator:
    """
    Módulo de evaluación post-entrenamiento para tesis de Economía.

    Calcula métricas de discriminación, calibración y desempeño financiero,
    asegurando rigor estadístico fuera de muestra (Out-of-Sample).

    Este módulo es estrictamente una herramienta de diagnóstico y reporte
    académico. No ejecuta ninguna acción automáticamente ni modifica los
    modelos subyacentes.

    Parámetros
    ----------
    y_true : array-like
        Etiquetas verdaderas (0/1) del conjunto de evaluación.
    y_proba : array-like
        Probabilidades predichas por el modelo (salida de predict_proba).
    returns_strategy : array-like o pd.Series, opcional
        Serie de retornos diarios de la estrategia basada en las señales
        del modelo. Si se proporciona, se calculan métricas financieras.
    threshold : float, default=0.5
        Umbral de decisión para convertir probabilidades en clases binarias.
    periods_per_year : int, default=252
        Número de periodos de negociación por año (252 para datos diarios).
    risk_free_rate : float, default=0.0
        Tasa libre de riesgo anualizada para el cálculo del Sharpe Ratio.
    """

    def __init__(
        self,
        y_true,
        y_proba,
        returns_strategy=None,
        threshold=0.5,
        periods_per_year=252,
        risk_free_rate=0.0
    ):
        self.y_true = np.asarray(y_true, dtype=int)
        self.y_proba = np.asarray(y_proba, dtype=float)
        self.returns_strategy = (
            np.asarray(returns_strategy, dtype=float)
            if returns_strategy is not None
            else None
        )
        self.threshold = threshold
        self.periods_per_year = periods_per_year
        self.risk_free_rate = risk_free_rate

        # Calcular y_pred internamente para garantizar consistencia
        # matemática en el umbral de decisión.
        self.y_pred = (self.y_proba >= self.threshold).astype(int)

    # =================================================================
    # 1. MÉTRICAS DE DISCRIMINACIÓN ESTADÍSTICA
    # =================================================================

    def classification_metrics(self):
        """
        Evalúa la capacidad discriminativa del clasificador mediante
        métricas estándar de la teoría de decisión estadística.

        Perspectiva Económica:
            En el contexto de detección de regímenes financieros, la
            discriminación mide la habilidad del modelo para separar
            correctamente los estados de mercado normales de los estados
            de estrés sistémico. Una alta AUC indica que las señales
            del modelo son fiables para la toma de decisiones de
            desapalancamiento (*de-risking*).

        Retorna
        -------
        dict
            Diccionario plano con las siguientes claves:
            - roc_auc: Área bajo la curva ROC (0.5 = aleatorio, 1.0 = perfecto).
            - precision: Proporción de alertas correctas sobre total de alertas.
            - recall: Proporción de eventos de estrés detectados correctamente.
            - f1_score: Media armónica de precision y recall.
            - mcc: Coeficiente de Correlación de Matthews [-1, 1].
                   Métrica robusta ante desbalance de clases, crucial para
                   justificar la validez del modelo en la defensa de tesis.
            - log_loss: Pérdida logarítmica. Mide la penalización por
                        predicciones probabilísticas incorrectas.
        """
        return {
            "roc_auc": float(roc_auc_score(self.y_true, self.y_proba)),
            "precision": float(precision_score(
                self.y_true, self.y_pred, zero_division=0
            )),
            "recall": float(recall_score(
                self.y_true, self.y_pred, zero_division=0
            )),
            "f1_score": float(f1_score(
                self.y_true, self.y_pred, zero_division=0
            )),
            "mcc": float(matthews_corrcoef(self.y_true, self.y_pred)),
            "log_loss": float(log_loss(self.y_true, self.y_proba)),
        }

    # =================================================================
    # 2. MÉTRICAS DE CALIBRACIÓN (INCERTIDUMBRE DEL MODELO)
    # =================================================================

    def calibration_metrics(self, n_bins=10):
        """
        Evalúa la calibración probabilística de las señales de riesgo
        generadas por el modelo.

        Perspectiva Económica:
            Un modelo bien calibrado significa que cuando predice una
            probabilidad del 70% de transición a régimen de estrés,
            efectivamente el 70% de las veces se materializa dicho evento.
            La calibración es esencial para la gestión cuantitativa de
            riesgos, ya que los gestores de portafolio necesitan confiar
            en la magnitud de las probabilidades, no solo en su ordenamiento.

        Parámetros
        ----------
        n_bins : int, default=10
            Número de intervalos para la curva de calibración.

        Retorna
        -------
        dict
            Diccionario con:
            - brier_score: Puntuación de Brier [0, 1]. Menor es mejor.
                           Mide el error cuadrático medio de las probabilidades.
            - prob_true: array con las probabilidades empíricas observadas.
            - prob_pred: array con las probabilidades medias predichas.
                         (prob_true y prob_pred se usan para graficar la
                         curva de calibración externamente).
        """
        brier = float(brier_score_loss(self.y_true, self.y_proba))

        prob_true, prob_pred = calibration_curve(
            self.y_true, self.y_proba, n_bins=n_bins, strategy="uniform"
        )

        return {
            "brier_score": brier,
            "prob_true": prob_true.tolist(),
            "prob_pred": prob_pred.tolist(),
        }

    # =================================================================
    # 3. MÉTRICAS PRECISION-RECALL
    # =================================================================

    def precision_recall_metrics(self):
        """
        Evalúa el desempeño del modelo en el espacio Precision-Recall,
        especialmente relevante cuando las clases están desbalanceadas.

        Perspectiva Económica:
            En mercados financieros, los eventos de crisis (clase positiva)
            son inherentemente raros respecto a los periodos de estabilidad.
            El PR-AUC proporciona una evaluación más informativa que el
            ROC-AUC en escenarios de desbalance extremo, ya que se enfoca
            exclusivamente en la clase minoritaria (eventos de estrés).
            Una alta PR-AUC indica que el modelo detecta crisis reales
            sin generar un exceso de falsas alarmas.

        Retorna
        -------
        dict
            Diccionario con:
            - pr_auc: Área bajo la curva Precision-Recall.
            - precision_curve: array de valores de precisión por umbral.
            - recall_curve: array de valores de recall por umbral.
            - thresholds: array de umbrales evaluados.
        """
        precision_arr, recall_arr, thresholds_arr = precision_recall_curve(
            self.y_true, self.y_proba
        )
        pr_auc_score = float(auc(recall_arr, precision_arr))

        return {
            "pr_auc": pr_auc_score,
            "precision_curve": precision_arr.tolist(),
            "recall_curve": recall_arr.tolist(),
            "thresholds": thresholds_arr.tolist(),
        }

    # =================================================================
    # 4. MÉTRICAS FINANCIERAS / ECONÓMICAS
    # =================================================================

    def economic_metrics(self):
        """
        Evalúa el desempeño financiero de una estrategia de inversión
        condicionada por las señales del modelo.

        Perspectiva Económica:
            Estas métricas traducen la capacidad predictiva estadística
            del modelo a indicadores de gestión de portafolios reconocidos
            por la industria financiera y la literatura académica:
            - Sharpe Ratio: rentabilidad ajustada por riesgo total.
            - Sortino Ratio: rentabilidad ajustada por riesgo a la baja
              (más relevante para gestión de drawdowns).
            - Maximum Drawdown (MDD): peor caída acumulada desde un pico,
              indicador de riesgo de cola izquierda.
            - CAGR: tasa de crecimiento anual compuesta, medida estándar
              de rentabilidad a largo plazo.

        Retorna
        -------
        dict o None
            Diccionario con métricas financieras si se proporcionaron
            retornos de la estrategia. None en caso contrario.
        """
        if self.returns_strategy is None:
            return None

        returns = self.returns_strategy
        n_periods = len(returns)

        if n_periods == 0:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "cagr": 0.0,
            }

        # --- Sharpe Ratio (Anualizado) ---
        # Exceso de retorno medio diario sobre la tasa libre de riesgo
        # diaria, escalado por la raíz de los periodos anuales.
        rf_daily = self.risk_free_rate / self.periods_per_year
        excess_returns = returns - rf_daily
        mean_excess = np.mean(excess_returns)
        std_returns = np.std(returns, ddof=1)

        sharpe = (
            (mean_excess / std_returns) * np.sqrt(self.periods_per_year)
            if std_returns > 0
            else 0.0
        )

        # --- Sortino Ratio (Anualizado) ---
        # Definición académica: Sortino & van der Meer (1991).
        # La Downside Deviation se calcula como la raíz cuadrada de la
        # media de los cuadrados de los retornos negativos respecto a 0
        # (o la tasa libre de riesgo), dividiendo por N total (no solo
        # los días perdedores). Esto evita sobreestimar el riesgo.
        downside_diff = np.minimum(excess_returns, 0.0)
        downside_deviation = np.sqrt(np.mean(downside_diff ** 2))

        sortino = (
            (mean_excess / downside_deviation) * np.sqrt(self.periods_per_year)
            if downside_deviation > 0
            else 0.0
        )

        # --- Maximum Drawdown (MDD) ---
        # Peor caída porcentual desde un pico de la curva de equidad.
        # Métrica fundamental para evaluar el riesgo de cola izquierda.
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdowns))

        # --- CAGR (Tasa de Crecimiento Anual Compuesta) ---
        # Crecimiento anualizado de la inversión, ajustado por la
        # duración real del periodo de evaluación.
        # El capital inicial implícito es 1. cumulative[-1] ya representa
        # el factor de crecimiento total, incluyendo el primer día.
        total_return = cumulative[-1]
        n_years = n_periods / self.periods_per_year

        cagr = (
            float(total_return ** (1 / n_years) - 1)
            if n_years > 0
            else 0.0
        )

        return {
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "cagr": float(cagr),
        }

    # =================================================================
    # EVALUACIÓN INTEGRAL
    # =================================================================

    def full_evaluation(self, n_bins=10):
        """
        Ejecuta la batería completa de métricas de evaluación.

        Perspectiva Académica:
            Este método consolida todos los diagnósticos en un único
            diccionario estructurado, diseñado para ser convertido
            directamente a pd.DataFrame y exportado a tablas de
            LaTeX/Word para la presentación formal de resultados
            en el documento de tesis (Capítulo 4: Resultados y Discusión).

        Parámetros
        ----------
        n_bins : int, default=10
            Número de intervalos para la curva de calibración.

        Retorna
        -------
        dict
            Diccionario con cuatro categorías:
            - "classification": métricas de discriminación estadística.
            - "calibration": métricas de calibración probabilística.
            - "precision_recall": métricas del espacio PR.
            - "economic": métricas financieras (None si no hay retornos).
        """
        return {
            "classification": self.classification_metrics(),
            "calibration": self.calibration_metrics(n_bins=n_bins),
            "precision_recall": self.precision_recall_metrics(),
            "economic": (
                self.economic_metrics()
                if self.returns_strategy is not None
                else None
            ),
        }

    # =================================================================
    # UTILIDADES DE EXPORTACIÓN ACADÉMICA
    # =================================================================

    def to_summary_dataframe(self, n_bins=10):
        """
        Genera un DataFrame resumen con las métricas escalares,
        listo para exportación a tabla de tesis (LaTeX/Word/APA 7).

        Excluye arrays (curvas) que requieren visualización gráfica.

        Retorna
        -------
        pd.DataFrame
            DataFrame con columnas ['Categoría', 'Métrica', 'Valor'].
        """
        results = self.full_evaluation(n_bins=n_bins)
        rows = []

        # Métricas de clasificación (todas son escalares)
        for key, value in results["classification"].items():
            rows.append({
                "Categoría": "Discriminación",
                "Métrica": key,
                "Valor": round(value, 4),
            })

        # Métricas de calibración (solo Brier Score es escalar)
        rows.append({
            "Categoría": "Calibración",
            "Métrica": "brier_score",
            "Valor": round(results["calibration"]["brier_score"], 4),
        })

        # PR-AUC (escalar)
        rows.append({
            "Categoría": "Precision-Recall",
            "Métrica": "pr_auc",
            "Valor": round(results["precision_recall"]["pr_auc"], 4),
        })

        # Métricas económicas (si están disponibles)
        if results["economic"] is not None:
            for key, value in results["economic"].items():
                rows.append({
                    "Categoría": "Económica",
                    "Métrica": key,
                    "Valor": round(value, 4),
                })

        return pd.DataFrame(rows)
