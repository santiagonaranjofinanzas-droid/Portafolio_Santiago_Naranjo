import json
import os
import redis
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from app.fetchers import gather_all_sources
from app.preprocessor import HybridPreprocessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))

def get_redis_client():
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        client.ping()
        return client
    except redis.ConnectionError:
        logging.error(f"No se pudo conectar a Redis en {REDIS_HOST}:{REDIS_PORT}. ¿Está Docker corriendo?")
        return None

#Inicializar Preprocessor globalmente (Cargará el modelo MiniLM)
preprocessor = HybridPreprocessor()

def collector_job():
    logging.info("Iniciando ciclo de recolección (Collector Job)...")
    redis_client = get_redis_client()
    
    # 1. Extracción (Capa 1)
    raw_feed = gather_all_sources()
    logging.info(f"Recolectados {len(raw_feed)} artículos en raw_feed.")
    
    if redis_client:
        redis_client.setex("raw_feed:latest", 7200, json.dumps(raw_feed))
    
    # 2. Preprocesamiento Híbrido (Capa 2)
    processed_feed = preprocessor.process(raw_feed)
    logging.info(f"Artículos que superaron el filtro híbrido: {len(processed_feed)}")
    
    if processed_feed:
        # 3. Guardar en Processed Feed con TTL de 2 horas (7200s)
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(processed_feed),
            "data": processed_feed
        }
        if redis_client:
            redis_client.setex("processed_feed:latest", 7200, json.dumps(payload))
            logging.info("processed_feed guardado exitosamente en Redis.")
        else:
            logging.info("Redis no está disponible. Mostrando el top 1 del processed_feed local:")
            logging.info(json.dumps(processed_feed[0], indent=2))

if __name__ == "__main__":
    logging.info("Iniciando Collector Service...")
    
    # Ejecutar inmediatamente una vez para poblar los buffers
    collector_job()
    
    # Programar cada 15 minutos
    scheduler = BlockingScheduler()
    scheduler.add_job(collector_job, 'interval', minutes=15)
    
    try:
        logging.info("Iniciando APScheduler...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Deteniendo Collector Service...")
