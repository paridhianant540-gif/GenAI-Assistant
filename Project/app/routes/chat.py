import os
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.db import get_db_conn
from app.models.request import ChatRequest
from app.routes.auth import get_current_user_optional
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.llm import LLMService
from app.prompts.templates import SYSTEM_INSTRUCTION, format_rag_prompt
from app.utils.logger import get_logger

logger = get_logger("chat-router")
router = APIRouter(prefix="/api", tags=["RAG Chat"])

# Load Configurations
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))
TOP_K = int(os.getenv("TOP_K", "3"))

# Initialize Services
embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)
llm_service = LLMService()

@router.post("/chat")
def chat_endpoint(payload: ChatRequest, current_user: dict | None = Depends(get_current_user_optional)):
    """
    Core RAG chatbot endpoint.
    Retrieves history, runs similarity query, formats prompt, invokes LLM, and persists chat logs.
    """
    session_id = payload.sessionId
    user_message = payload.message.strip()
    user_id = current_user["id"] if current_user else None
    
    logger.info(f"Processing chat message for session: {session_id} (Authenticated user: {current_user['username'] if current_user else 'None'})")
    
    # 1. Fetch short conversation history (last 5 messages)
    history_messages = []
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM chat_history 
            WHERE session_id = ? 
            ORDER BY id DESC LIMIT 6
        """, (session_id,))
        rows = cursor.fetchall()
        # Order chronologically (oldest first)
        rows.reverse()
        for row in rows:
            role = "User" if row["role"] == "user" else "Assistant"
            history_messages.append(f"{role}: {row['content']}")
            
    history_str = "\n".join(history_messages)
    
    # 2. Perform embedding similarity retrieval
    try:
        retrieved_chunks = vector_store.similarity_search(
            query=user_message, 
            top_k=TOP_K, 
            threshold=SIMILARITY_THRESHOLD
        )
    except Exception as e:
        logger.error(f"Error during vector similarity search: {str(e)}")
        # Gracefully handle API embedding failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding API failure. Please check your API configuration or keys."
        )

    # 3. Grounding validation & decision-making
    if not retrieved_chunks:
        # Strict grounding: If all chunks fall below threshold, return immediate fallback response
        reply = "I could not find enough information in the knowledge base to answer this question."
        tokens_used = 0
        logger.info("Semantic similarity fell below threshold. Served safe fallback reply.")
    else:
        # Build context from the retrieved chunks
        context_parts = []
        for idx, chunk in enumerate(retrieved_chunks):
            context_parts.append(
                f"Source Document: {chunk['title']} (Similarity Score: {chunk['score']:.4f})\n"
                f"Content Chunk: {chunk['content']}"
            )
        context_str = "\n\n".join(context_parts)
        
        # Assemble grounded prompt
        formatted_prompt = format_rag_prompt(
            retrieved_context=context_str, 
            history=history_str, 
            user_question=user_message
        )
        
        # Invoke grounded LLM call
        try:
            reply, tokens_used = llm_service.generate_reply(
                prompt=formatted_prompt, 
                system_instruction=SYSTEM_INSTRUCTION
            )
        except Exception as e:
            logger.error(f"Error during LLM generation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM API failure. Please inspect credentials or rate limits."
            )
            
    # 4. Persist conversation history to SQLite
    with get_db_conn() as conn:
        cursor = conn.cursor()
        # Save user message
        cursor.execute(
            "INSERT INTO chat_history (session_id, user_id, role, content, tokens_used) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, "user", user_message, 0)
        )
        # Save assistant response
        cursor.execute(
            "INSERT INTO chat_history (session_id, user_id, role, content, tokens_used) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, "assistant", reply, tokens_used)
        )
        conn.commit()
        
    # 5. Format return payload (includes metadata inspectables)
    return {
        "reply": reply,
        "tokensUsed": tokens_used,
        "retrievedChunks": len(retrieved_chunks),
        # Return complete details of chunks for the UI RAG inspector panel
        "chunks": [
            {
                "title": chunk["title"],
                "content": chunk["content"],
                "score": round(chunk["score"], 4),
                "chunkIndex": chunk["chunk_index"]
            }
            for chunk in retrieved_chunks
        ]
    }

@router.get("/chat/history/{session_id}")
def get_session_history(session_id: str, current_user: dict | None = Depends(get_current_user_optional)):
    """Fetches full cached history for a session."""
    user_id = current_user["id"] if current_user else None
    
    with get_db_conn() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT role, content, tokens_used, created_at FROM chat_history 
                WHERE session_id = ? AND (user_id = ? OR user_id IS NULL)
                ORDER BY id ASC
            """, (session_id, user_id))
        else:
            cursor.execute("""
                SELECT role, content, tokens_used, created_at FROM chat_history 
                WHERE session_id = ? AND user_id IS NULL
                ORDER BY id ASC
            """, (session_id,))
            
        rows = cursor.fetchall()
        
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "tokensUsed": row["tokens_used"],
            "timestamp": row["created_at"]
        }
        for row in rows
    ]

@router.get("/documents")
def get_all_documents():
    """Lists raw documents currently indexed in the knowledge base."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, LENGTH(content) as length FROM documents ORDER BY title ASC")
        rows = cursor.fetchall()
        
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "lengthBytes": row["length"]
        }
        for row in rows
    ]
