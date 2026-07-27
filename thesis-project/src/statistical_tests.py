import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss, grangercausalitytests
from statsmodels.stats.diagnostic import acorr_ljungbox
from scipy.stats import norm
import warnings

class StatisticalAuditor:
    """
    Clase para realizar validaciones estadísticas rigurosas requeridas en una tesis.
    Evalúa estacionariedad, causalidad de Granger, autocorrelación de residuos
    y superioridad predictiva mediante el test de Diebold-Mariano.
    """
    
    @staticmethod
    def test_stationarity(series, series_name="Serie"):
        """
        Aplica tests ADF y KPSS para confirmar la estacionariedad.
        ADF H0: Existe raíz unitaria (No estacionaria).
        KPSS H0: La serie es estacionaria alrededor de una tendencia determinista.
        """
        results = {"Serie": series_name}
        
        # Eliminamos NaNs para evitar errores
        clean_series = series.dropna()
        if len(clean_series) < 10:
            return {"Error": "Serie muy corta"}
            
        # Test ADF
        adf_stat, adf_pvalue, _, _, _, _ = adfuller(clean_series, autolag='AIC')
        results['ADF_Statistic'] = adf_stat
        results['ADF_pvalue'] = adf_pvalue
        results['Estacionaria (ADF)'] = adf_pvalue < 0.05
        
        # Test KPSS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kpss_stat, kpss_pvalue, _, _ = kpss(clean_series, regression='c', nlags="auto")
            results['KPSS_Statistic'] = kpss_stat
            results['KPSS_pvalue'] = kpss_pvalue
            results['Estacionaria (KPSS)'] = kpss_pvalue > 0.05
            
        return results

    @staticmethod
    def test_ljung_box(residuals, lags=10):
        """
        Test de Ljung-Box sobre los residuos para probar la no-autocorrelación.
        H0: Los residuos se distribuyen de forma independiente (no hay autocorrelación).
        """
        clean_resids = residuals.dropna()
        if len(clean_resids) < lags + 1:
            return {"Error": "Pocos datos para Ljung-Box"}
            
        lb_results = acorr_ljungbox(clean_resids, lags=[lags], return_df=True)
        p_value = lb_results['lb_pvalue'].iloc[0]
        
        return {
            'LjungBox_pvalue': p_value,
            'No_Autocorrelacion': p_value > 0.05 # Si es >0.05, no podemos rechazar independencia
        }

    @staticmethod
    def test_granger_causality(data, maxlag=5, target_col='Target', predictor_col='Predictor'):
        """
        Test de causalidad de Granger.
        H0: El Predictor no causa en el sentido de Granger al Target.
        data debe contener el Target en la primera columna y el Predictor en la segunda.
        """
        clean_data = data[[target_col, predictor_col]].dropna()
        
        if len(clean_data) < maxlag * 3:
            return {"Error": "Pocos datos para Granger"}
            
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # grangercausalitytests imprime mucha info, por lo que suprimimos o usamos verbose=False
            gc_res = grangercausalitytests(clean_data, maxlag=[maxlag], verbose=False)
            
        # Tomamos el p-value del test SSR basado en F test para el maxlag
        f_pvalue = gc_res[maxlag][0]['ssr_ftest'][1]
        
        return {
            'Granger_pvalue': f_pvalue,
            'Rechaza_H0 (Causa)': f_pvalue < 0.05
        }

    @staticmethod
    def diebold_mariano_test(y_true, y_pred_model, y_pred_baseline, h=1, power=2):
        """
        Implementación simple del Test de Diebold-Mariano.
        H0: Ambos modelos tienen el mismo poder predictivo.
        H1: Los modelos tienen distinto poder predictivo (se evalúa la media de la diferencia de pérdidas).
        """
        y_true = np.asarray(y_true)
        y_pred_model = np.asarray(y_pred_model)
        y_pred_baseline = np.asarray(y_pred_baseline)
        
        # Funciones de pérdida (MSE si power=2, MAE si power=1)
        e1 = np.abs(y_true - y_pred_model)**power
        e2 = np.abs(y_true - y_pred_baseline)**power
        
        d = e1 - e2
        mean_d = np.mean(d)
        
        def autocovariance(Xi, N, k, Xs):
            autoCov = 0
            for i in np.arange(0, N-k):
                autoCov += ((Xi[i+k])-Xs)*(Xi[i]-Xs)
            return (1/(N))*autoCov

        gamma = []
        for lag in range(0, h):
            gamma.append(autocovariance(d, len(d), lag, mean_d))
            
        V_d = gamma[0] + 2 * sum(gamma[1:])
        
        if V_d == 0:
            return {"DM_Statistic": np.nan, "DM_pvalue": np.nan, "Conclusion": "Varianza Cero"}
            
        # Estadístico de Diebold-Mariano
        DM_stat = mean_d / np.sqrt(V_d / len(d))
        
        # P-value (bilateral)
        p_value = 2 * (1 - norm.cdf(abs(DM_stat)))
        
        # Si el estadístico es negativo, el modelo 1 (e1) tiene menos error.
        return {
            'DM_Statistic': DM_stat,
            'DM_pvalue': p_value,
            'Modelo_Propuesto_Mejor': (p_value < 0.05) and (DM_stat < 0)
        }
