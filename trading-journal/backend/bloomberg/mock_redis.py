import redis
import json

r = redis.Redis(host='localhost', port=6380, decode_responses=True)

#Portfolio Base
r.set("portfolio:nav", 3000.0)
r.set("portfolio:hwm", 3000.0)
r.delete("portfolio:nav_history")
r.rpush("portfolio:nav_history", *[2950.0, 2980.0, 3010.0, 2990.0, 3000.0])

#Quant Data
quant_data = {
    "regime_probabilities": {"low": 0.62, "high": 0.13, "transition": 0.25},
    "stress_probability_t5": 0.41,
    "status": "normal"
}
r.set("quant:latest", json.dumps(quant_data))
r.set("quant:stress_prob", 0.41)

#MiroFish Data
mirofish_data = {
    "R_narr": -0.32,
    "omega_narr": 0.61,
    "dominant_theme": "fed_hawkish",
    "confidence": 0.85,
    "sources_used": 14,
    "reasoning": "El mercado teme subidas de tasas prolongadas tras los últimos comentarios de la FED. La volatilidad está repuntando en foros retail."
}
r.set("mirofish:latest", json.dumps(mirofish_data))

#Limpiar Trades
r.delete("trades:all")

print("Redis mockeado exitosamente con NAV $3000.")
