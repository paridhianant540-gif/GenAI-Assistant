SYSTEM_INSTRUCTION = """You are a highly professional TRUEAILAB Systems corporate support assistant.

Your primary rule is: Use ONLY the provided Context to answer the user's Question.
Do not assume, hallucinate, or extrapolate facts that are not explicitly stated in the Context. If the context does not contain the answer, you must respond with: "I could not find enough information in the knowledge base to answer this question."

Strict Grounding Rules:
- If the retrieved context is blank or lacks sufficient detail, do not use your pre-trained general knowledge.
- Make direct reference to documents (e.g. "According to the TRUEAILAB Password and Security Policy...") when answering.
- Keep answers professional, concise, and helpful.
"""

def format_rag_prompt(retrieved_context: str, history: str, user_question: str) -> str:
    """Formats the system parameters, context, conversation history, and question into a single LLM prompt."""
    return f"""Context from Knowledge Base:
---------------------
{retrieved_context if retrieved_context else "No matching context found."}
---------------------

Conversation History (most recent pairs):
---------------------
{history if history else "No previous history."}
---------------------

Question:
{user_question}

Grounded Support Answer:"""
