import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import os
from sklearn.metrics import confusion_matrix, roc_curve, auc
from sklearn.calibration import calibration_curve

class ThesisVisualizer:
    """
    Motor de visualización especializado para la tesis de sistemas híbridos ISRI-HMM-XGB.
    """
    def __init__(self, output_dir=None):
        if output_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.output_dir = os.path.abspath(os.path.join(script_dir, '../resultados/graficos'))
        else:
            self.output_dir = output_dir
            
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Configuración estética visual premium institucional (Bloomberg-Stripe)
        sns.set_theme(style="ticks", context="paper", font_scale=1.2)
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        plt.rcParams['axes.prop_cycle'] = plt.cycler('color', ['#635BFF', '#00D4FF', '#0A2540', '#FF5252', '#00E676']) # Stripe-ish colors
        plt.rcParams['figure.figsize'] = (12, 6)
        plt.rcParams['axes.titlesize'] = 16
        plt.rcParams['axes.titleweight'] = 'bold'
        plt.rcParams['axes.labelsize'] = 14
        plt.rcParams['axes.labelcolor'] = '#425466'
        plt.rcParams['xtick.color'] = '#425466'
        plt.rcParams['ytick.color'] = '#425466'
        plt.rcParams['text.color'] = '#0A2540'

    def save_plot(self, name):
        path = os.path.join(self.output_dir, f"{name}.png")
        plt.tight_layout()
        plt.savefig(path, dpi=300)
        plt.close()
        print(f"Gráfico guardado: {path}")

    def plot_pca_loadings(self, loadings):
        """Gráfico de barras de los pesos del PC1."""
        plt.figure(figsize=(10, 5))
        # Asegurar que los loadings sean 1D para barplot
        x_values = loadings.iloc[:, 0] if isinstance(loadings, pd.DataFrame) else loadings
        sns.barplot(x=x_values, y=loadings.index, palette="mako")
        plt.title("Contribución de Activos al PC1 (Estructura del ISRI)")
        plt.xlabel("Loading (Peso Relativo)")
        plt.ylabel("Activo")
        self.save_plot("pca_loadings")

    def plot_isri_timeseries(self, isri):
        """Evolución temporal del ISRI con hitos macro."""
        plt.figure()
        plt.plot(isri.index, isri.values, color='#2c3e50', alpha=0.8, label='ISRI (PC1)')
        
        # Zonas sombreadas para eventos macro (Usando colores compatibles con Matplotlib)
        events = [
            ('2020-02-20', '2020-04-15', 'Crisis COVID-19', 'red'),
            ('2022-03-16', '2023-01-01', 'Subida de Tipos FED', 'blue')
        ]
        
        for start, end, label, color in events:
            plt.axvspan(pd.to_datetime(start), pd.to_datetime(end), color=color, alpha=0.1, label=label)
            
        plt.title("Evolución Temporal del Índice Sintético de Rotación (ISRI)")
        plt.legend()
        self.save_plot("isri_timeseries")

    def plot_hmm_states(self, isri, states):
        """ISRI coloreado por estado dominante."""
        plt.figure()
        # Mapeo de estados a colores significativos
        color_map = {0: 'forestgreen', 1: 'gold', 2: 'crimson'} 
        
        for state in np.unique(states):
            mask = (states == state)
            # Usar .loc para filtrado booleano correcto en Series/DataFrame
            plt.scatter(isri.index[mask], isri.loc[mask], 
                        color=color_map.get(state, 'gray'), 
                        label=f'Estado {state}', s=10, alpha=0.6)
            
        plt.title("Segmentación de Regímenes HMM sobre el ISRI")
        plt.legend()
        self.save_plot("hmm_regimes_scatter")

    def plot_regime_distributions(self, isri, states):
        """Distribución de retornos por régimen."""
        # Asegurar que ambos sean Series 1D para evitar ValueError en DataFrame construction
        s_isri = isri.squeeze() if hasattr(isri, 'squeeze') else isri
        s_states = states.squeeze() if hasattr(states, 'squeeze') else states
        data = pd.DataFrame({'ISRI': s_isri, 'Estado': s_states})
        plt.figure()
        sns.boxplot(x='Estado', y='ISRI', data=data, palette="Set2")
        plt.title("Análisis Estadístico de Regímenes: Distribución del ISRI")
        self.save_plot("regime_distributions")

    def plot_state_probabilities(self, probs):
        """Áreas apiladas de probabilidades marginales."""
        plt.figure()
        plt.stackplot(probs.index, probs.T, labels=probs.columns, alpha=0.7)
        plt.title("Evolución de Probabilidades de Estado (Filtro Forward)")
        plt.ylabel("Probabilidad")
        plt.legend(loc='lower left')
        self.save_plot("state_probabilities")

    def plot_confusion_matrix(self, y_true, y_pred, title="Matriz de Confusión (OOS 2022+)"):
        """Mapa de calor de la matriz de confusión."""
        cm = confusion_matrix(y_true, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['No Transición', 'Transición'], 
                    yticklabels=['No Transición', 'Transición'])
        plt.title(title)
        plt.ylabel('Realidad')
        plt.xlabel('Predicción')
        self.save_plot("confusion_matrix_oos")

    def plot_roc_curves(self, results_dict):
        """Comparación de Curvas ROC Train vs Test."""
        plt.figure()
        for label, (y_true, y_prob) in results_dict.items():
            fpr, tpr, _ = roc_curve(y_true, y_prob)
            roc_auc = auc(fpr, tpr)
            plt.plot(fpr, tpr, label=f'{label} (AUC = {roc_auc:.4f})')
            
        plt.plot([0, 1], [0, 1], 'k--', alpha=0.5)
        plt.title("Curvas ROC: Capacidad de Discriminación del Sistema")
        plt.xlabel("Tasa de Falsos Positivos")
        plt.ylabel("Tasa de Verdaderos Positivos")
        plt.legend()
        self.save_plot("roc_curves_comparison")

    def plot_calibration_curve(self, y_true, y_prob):
        """Diagrama de fiabilidad (Calibración)."""
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10)
        plt.figure()
        plt.plot(prob_pred, prob_true, marker='o', label='XGBoost Calibrado')
        plt.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='Calibración Perfecta')
        plt.title("Diagrama de Fiabilidad (Curva de Calibración)")
        plt.xlabel("Probabilidad Predicha")
        plt.ylabel("Fracción Real de Positivos")
        plt.legend()
        self.save_plot("calibration_curve")

    def plot_feature_importance(self, model, feature_names):
        """Importancia de características de XGBoost."""
        importances = model.feature_importances_
        idx = np.argsort(importances)
        
        plt.figure(figsize=(10, 8))
        plt.barh(range(len(idx)), importances[idx], align='center', color='#34495e')
        plt.yticks(range(len(idx)), [feature_names[i] for i in idx])
        plt.title("Importancia de Características (Gini Importance)")
        plt.xlabel("Peso Relativo")
        self.save_plot("feature_importance")
