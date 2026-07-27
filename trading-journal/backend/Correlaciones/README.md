#Systemic Risk Detector (RMT & MST)

##Hipótesis
La transición de un mercado desde una fase de expansión hacia un régimen de crisis induce una contracción topológica no lineal (colapso dimensional en la matriz de covarianza condicional) observable estadísticamente antes que la caída del precio unidimensional.

##Datos
Retornos logarítmicos diarios de un universo multiactivo ($N=26$) abarcando periodos expansivos y de recesión documentados macroeconómicamente.

##Validación
**Combinatorial Purged and Embargoed Cross-Validation (CPCV)** para control estricto de fuga causal en modelos dependientes de tiempo.

##Resultados
Clasificador OOS de regímenes risk-off basado en TVTP-HMM y XGBoost monótono que alcanza un Coeficiente de Correlación de Matthews (MCC) de **0.5344** y ROC-AUC de **0.8186**, superando al benchmark de volatilidad univariada. Presenta una sensibilidad de crisis de **90.3%**, documentando empíricamente la Precision y el Lead-time promedio para aislar eventos verdaderamente preventivos.

##Limitaciones
El clasificador estructural presenta inestabilidad matemática si se introduce un exceso de activos masivamente correlacionados (ej. criptomonedas especulativas) o si la serie temporal inicial es demasiado corta para converger la estimación incondicional de covarianza.
