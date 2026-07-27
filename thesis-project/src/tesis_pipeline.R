#Instalar librerías necesarias si no están instaladas
#install.packages(c("quantmod", "FactoMineR", "depmixS4", "xgboost", "tseries", "lmtest", "forecast", "pROC", "DescTools", "ggplot2", "SHAPforxgboost"))

library(quantmod)
library(FactoMineR)
library(depmixS4)
library(xgboost)
library(tseries)
library(lmtest)
library(forecast)
library(pROC)
library(DescTools)
library(ggplot2)
library(SHAPforxgboost)

print("=== Iniciando Pipeline del Sistema Híbrido ISRI-HMM-XGB en R ===")

#Definir punto de corte para el entrenamiento
train_split_date <- as.Date("2021-12-31")

#==============================================================================
#1. Obtención y Preprocesamiento de Datos (DataEngine)
#==============================================================================
print("Módulo 1: Descargando y preprocesando datos con prevención de fuga...")

tickers <- c("^GSPC", "GC=F", "CL=F", "^TNX", "DX-Y.NYB")
names <- c("SP500", "GOLD", "OIL", "BOND10Y", "USD")

#Descargar desde 2015
getSymbols(tickers, from = "2015-01-01", to = Sys.Date(), warnings = FALSE, auto.assign = TRUE)
data_list <- list(GSPC, `GC=F`, `CL=F`, TNX, `DX-Y.NYB`)

#Unir cierres ajustados
data_adj <- do.call(merge, lapply(data_list, Ad))
colnames(data_adj) <- names

#Limpieza básica
data_adj <- na.locf(data_adj)
data_adj <- na.omit(data_adj)

#Retornos Logarítmicos
returns <- diff(log(data_adj))
returns <- na.omit(returns)

train_returns <- returns[index(returns) <= train_split_date]

#Winsorización (1% - 99%) basada SOLO en el entrenamiento
lower_bounds <- apply(train_returns, 2, quantile, probs=0.01, na.rm=TRUE)
upper_bounds <- apply(train_returns, 2, quantile, probs=0.99, na.rm=TRUE)

returns_win <- returns
for (i in 1:ncol(returns)) {
  returns_win[,i] <- pmin(pmax(returns[,i], lower_bounds[i]), upper_bounds[i])
}

#Normalización Z-score basada SOLO en el entrenamiento
scaler_means <- apply(train_returns, 2, mean, na.rm=TRUE)
scaler_sds <- apply(train_returns, 2, sd, na.rm=TRUE)

returns_scaled <- returns_win
for (i in 1:ncol(returns)) {
  returns_scaled[,i] <- (returns_win[,i] - scaler_means[i]) / scaler_sds[i]
}

#==============================================================================
#2. Extracción del Índice ISRI (PCAEngine)
#==============================================================================
print("Módulo 2: Extrayendo el ISRI mediante SVD/PCA...")

train_returns_scaled <- returns_scaled[index(returns_scaled) <= train_split_date]

#PCA ajustado solo en entrenamiento
pca_res <- prcomp(train_returns_scaled, center = FALSE, scale. = FALSE)
isri_values <- predict(pca_res, newdata = returns_scaled)[, 1]

#Reconstruir xts
isri <- xts(isri_values, order.by = index(returns_scaled))
colnames(isri) <- "ISRI"

#Auditoría Estadística
print("Auditoría: Test de Estacionariedad de Dickey-Fuller Aumentado (ADF) para ISRI...")
adf_test <- adf.test(as.numeric(isri), alternative="stationary")
print(adf_test)

#==============================================================================
#3. Identificación de Regímenes (HMMRegimes)
#==============================================================================
print("Módulo 3: Ajustando el Modelo Oculto de Markov (HMM)...")

train_isri <- isri[index(isri) <= train_split_date]

#Definir HMM de 3 estados
mod <- depmix(ISRI ~ 1, data = data.frame(ISRI = as.numeric(train_isri)), nstates = 3, family = gaussian())
#Ajustar HMM en el set de entrenamiento
set.seed(42)
fit_mod <- fit(mod, verbose = FALSE)

#Inferencia para toda la serie usando los parámetros entrenados
mod_full <- depmix(ISRI ~ 1, data = data.frame(ISRI = as.numeric(isri)), nstates = 3, family = gaussian())
mod_full <- setpars(mod_full, getpars(fit_mod))
hmm_results <- posterior(mod_full)

#==============================================================================
#4. Solución Multicolinealidad: Segunda capa PCA ortogonal
#==============================================================================
print("Módulo 4: Ortogonalización SVD/PCA de características para XGBoost...")

#Matriz de características inicial
X_raw <- data.frame(
  ISRI = as.numeric(isri),
  Prob_S1 = hmm_results$S1,
  Prob_S2 = hmm_results$S2,
  Prob_S3 = hmm_results$S3
)

#Aplicar PCA/SVD sobre las características para eliminar multicolinealidad
X_train_raw <- X_raw[index(isri) <= train_split_date, ]
pca_features <- prcomp(X_train_raw, center = TRUE, scale. = TRUE)

#Extraer componentes principales ortogonales como input final
X_orthogonal <- predict(pca_features, newdata = X_raw)

#Target: Predecir si habrá transición de estado en t + 5
horizon <- 5
states <- hmm_results$state
target <- c(states[-(1:horizon)] != states[1:(length(states)-horizon)], rep(NA, horizon))
target <- as.numeric(target)

#==============================================================================
#5. Predicción con XGBoost (XGBPredictor)
#==============================================================================
print("Módulo 5: Entrenando XGBoost con características ortogonales...")

df_final <- data.frame(X_orthogonal)
df_final$Target <- target
df_final <- df_final[!is.na(df_final$Target), ]

#Construcción de Splits (Purga y Embargo)
train_idx <- which(index(isri)[1:nrow(df_final)] <= train_split_date)
#Purga: descartar últimos 'horizon' días del entrenamiento
train_idx <- train_idx[1:(length(train_idx) - horizon)]

X_train <- as.matrix(df_final[train_idx, 1:ncol(X_orthogonal)])
y_train <- df_final$Target[train_idx]

test_idx <- which(index(isri)[1:nrow(df_final)] > train_split_date)
X_test <- as.matrix(df_final[test_idx, 1:ncol(X_orthogonal)])
y_test <- df_final$Target[test_idx]

#Manejo de desbalance
pos_weight <- sum(y_train == 0) / sum(y_train == 1)
if(is.infinite(pos_weight)  is.na(pos_weight)) pos_weight <- 1.0

dtrain <- xgb.DMatrix(data = X_train, label = y_train)
dtest <- xgb.DMatrix(data = X_test, label = y_test)

params <- list(
  objective = "binary:logistic",
  eval_metric = "auc",
  max_depth = 5,
  eta = 0.05,
  scale_pos_weight = pos_weight
)

set.seed(42)
xgb_model <- xgb.train(params = params, data = dtrain, nrounds = 150, verbose = 0)

y_prob_train <- predict(xgb_model, dtrain)
y_prob_test <- predict(xgb_model, dtest)
y_pred_test <- ifelse(y_prob_test > 0.5, 1, 0)

#==============================================================================
#6. Auditoría y Evaluación (Out-Of-Sample)
#==============================================================================
print("=== Resultados Out-Of-Sample (OOS) ===")

roc_test <- roc(y_test, y_prob_test, quiet=TRUE)
auc_val <- as.numeric(auc(roc_test))
brier_val <- mean((y_prob_test - y_test)^2)

print(sprintf("ROC AUC: %.4f", auc_val))
print(sprintf("Brier Score: %.4f", brier_val))

print("--- Auditoría Estadística Rigurosa (OOS) ---")
residuos <- y_test - y_prob_test

#Test Ljung-Box sobre residuos
lb_test <- Box.test(residuos, type = "Ljung-Box", lag = 10)
print("Ljung-Box Test (Autocorrelación de Residuos):")
print(lb_test)

#Test Causalidad de Granger
granger_data <- data.frame(Target = df_final$Target, ISRI = as.numeric(isri)[1:nrow(df_final)])
granger_test <- grangertest(Target ~ ISRI, order = 5, data = granger_data)
print("Granger Causality (ISRI -> Target):")
print(granger_test)

print("=== Pipeline R Completado con Éxito ===")


