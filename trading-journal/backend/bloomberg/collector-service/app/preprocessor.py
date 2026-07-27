import re
import logging
from typing import List, Dict
from sentence_transformers import SentenceTransformer, util

class HybridPreprocessor:
    def __init__(self):
        logging.info("Inicializando Preprocessor (Cargando capa de embeddings)...")
        # Capa A: Keywords deterministas ultra-rápidas
        self.keywords = re.compile(r'\b(QQQSPYSP500GLDGOLDOILBONDUSDFEDCPIINFLATIONRATESMARKETNVDAAAPLBTCETHCRYPTOSTOCKSTECHAI)\b', re.IGNORECASE)
        
        # Capa B: Embeddings locales para relevancia semántica fina
        # Descarga la primera vez que se inicializa (aprox 90MB)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Target embedding para comparar relevancia macro/mercado
        self.target_concept = "financial markets macroeconomics monetary policy stock market indices crypto technology earnings"
        self.target_embedding = self.model.encode(self.target_concept)
        self.similarity_threshold = 0.15  # Umbral de similitud coseno relajado
        logging.info("Preprocessor inicializado con éxito.")

        self.social_hints = ("reddit", "stocktwits", "twitter", "x.com", "finnhub social")

    def _is_social(self, item: Dict) -> bool:
        if str(item.get("feed_kind", "")).lower() == "social":
            return True
        source = str(item.get("source", "")).lower()
        url = str(item.get("url", "")).lower()
        return any(hint in source or hint in url for hint in self.social_hints)

    def process(self, raw_items: List[Dict]) -> List[Dict]:
        processed = []
        
        for item in raw_items:
            title = item.get("title", "")
            content = item.get("content", "")
            text = f"{title} {content}".strip()

            if self._is_social(item):
                if not text:
                    continue
                item_copy = item.copy()
                item_copy['relevance_score'] = 1.0
                processed.append(item_copy)
                continue
            
            # Capa A: Filtro Regex (Determinista, sin costo)
            if not self.keywords.search(text):
                continue  # Descartar: no menciona entidades de interés
                
            # Capa B: Scoring Semántico (Embeddings locales)
            item_emb = self.model.encode(text)
            sim_score = float(util.cos_sim(item_emb, self.target_embedding)[0][0])
            
            # Validar umbral
            if sim_score >= self.similarity_threshold:
                # Modificamos el diccionario de forma inmutable idealmente, pero para simplicidad mutamos
                item_copy = item.copy()
                item_copy['relevance_score'] = round(sim_score, 4)
                processed.append(item_copy)
                
        # Ordenar por score de mayor a menor
        processed.sort(key=lambda x: x['relevance_score'], reverse=True)
        return processed
