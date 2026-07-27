from fastapi import APIRouter
from app.schemas import ModelInfoResponse

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "OK", "service": "quant-service"}

@router.get("/model-info", response_model=ModelInfoResponse)
def model_info():
    # Evitar dependencias circulares importando dentro de la función
    from app.main import app
    scaler_params = app.state.scaler_params
    hmm_prior = app.state.hmm_prior
    
    return ModelInfoResponse(
        model_version=scaler_params["model_version"],
        feature_version=scaler_params["feature_version"],
        feature_names=scaler_params["feature_names"],
        hmm_n_states=hmm_prior["n_states"],
        hmm_pi_0=hmm_prior["pi_0"],
        status="OK"
    )
