import json
import math
import numpy as np
from typing import List, Dict, Any, Tuple
from app.models.db import get_db_conn
from app.utils.logger import get_logger, log_latency
from app.utils.chunker import split_text_by_words
from app.services.embedding import EmbeddingService

logger = get_logger("vector-store")

def compute_cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Computes Cosine Similarity between two vectors.
    Includes a highly optimized NumPy version and a pure-Python fallback.
    """
    try:
        # NumPy-accelerated calculation
        arr1 = np.array(v1, dtype=np.float32)
        arr2 = np.array(v2, dtype=np.float32)
        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return float(dot_product / (norm1 * norm2))
    except Exception as e:
        # Pure-Python fallback mathematical calculation
        dot_prod = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot_prod / (norm1 * norm2)

class VectorStore:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        
    def check_document_indexed(self, title: str) -> bool:
        """Checks if a document with this title already exists in our database."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM documents WHERE title = ?", (title,))
            return cursor.fetchone() is not None

    @log_latency("vector-store")
    def index_document(self, title: str, content: str) -> int:
        """
        Splits a document, generates embeddings for all its chunks,
        and saves everything to the SQLite vector store cache.
        """
        if self.check_document_indexed(title):
            logger.info(f"Document '{title}' is already indexed. Skipping.")
            return 0
            
        logger.info(f"Indexing document: '{title}'...")
        
        # 1. Chunk document
        chunks = split_text_by_words(content, chunk_size=250, chunk_overlap=40)
        logger.info(f"Split '{title}' into {len(chunks)} overlapping chunks.")
        
        with get_db_conn() as conn:
            cursor = conn.cursor()
            # 2. Insert document record
            cursor.execute("INSERT INTO documents (title, content) VALUES (?, ?)", (title, content))
            doc_id = cursor.lastrowid
            
            # 3. Embed and store each chunk
            for idx, chunk_content in enumerate(chunks):
                logger.info(f"Embedding chunk {idx + 1}/{len(chunks)} for '{title}'...")
                embedding = self.embedding_service.generate_embedding(chunk_content)
                embedding_json = json.dumps(embedding)
                
                cursor.execute(
                    "INSERT INTO document_chunks (document_id, chunk_index, content, embedding_json) VALUES (?, ?, ?, ?)",
                    (doc_id, idx, chunk_content, embedding_json)
                )
                
            conn.commit()
            
        logger.info(f"Successfully indexed document '{title}' (ID: {doc_id}) with {len(chunks)} chunks.")
        return doc_id

    @log_latency("vector-store")
    def similarity_search(self, query: str, top_k: int = 3, threshold: float = 0.65) -> List[Dict[str, Any]]:
        """
        Computes the query embedding, calculates similarity scores against all database chunks,
        filters by threshold, and returns the top K matches.
        """
        logger.info(f"Initiating similarity search for query: '{query}' (top_k={top_k}, threshold={threshold})")
        
        # 1. Embed query
        query_vector = self.embedding_service.generate_embedding(query)
        
        # 2. Fetch all chunks from DB to calculate similarities
        results = []
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    c.id as chunk_id, 
                    c.content as chunk_content, 
                    c.embedding_json, 
                    c.chunk_index,
                    d.title as doc_title, 
                    d.content as doc_full_content
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                chunk_id = row["chunk_id"]
                chunk_content = row["chunk_content"]
                doc_title = row["doc_title"]
                chunk_index = row["chunk_index"]
                
                try:
                    chunk_vector = json.loads(row["embedding_json"])
                except Exception as ex:
                    logger.error(f"Error parsing embedding JSON for chunk ID {chunk_id}: {str(ex)}")
                    continue
                    
                # Calculate cosine similarity
                score = compute_cosine_similarity(query_vector, chunk_vector)
                
                results.append({
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "title": doc_title,
                    "content": chunk_content,
                    "score": score
                })
                
        # 3. Sort by similarity score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # 4. Filter by grounding threshold and limit to Top K
        filtered_results = []
        for res in results:
            # Format and log the computed similarity scores
            logger.info(f"Similarity score for chunk {res['chunk_id']} from '{res['title']}': {res['score']:.4f}")
            
            if res["score"] >= threshold:
                filtered_results.append(res)
            else:
                logger.info(f"Discarding chunk {res['chunk_id']} (score {res['score']:.4f} is below threshold {threshold})")
                
            if len(filtered_results) >= top_k:
                break
                
        logger.info(f"Similarity search complete. Retrieved {len(filtered_results)} chunks meeting threshold.")
        return filtered_results
