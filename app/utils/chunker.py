import re
from typing import List

def clean_text(text: str) -> str:
    """Removes extra white spaces and sanitizes text formatting."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def split_text_by_words(text: str, chunk_size: int = 250, chunk_overlap: int = 40) -> List[str]:
    """
    Splits text into chunks based on word count with a sliding window overlap.
    Averages 1.3 tokens per word, so ~250 words is ~325 tokens, which is ideal.
    """
    text = clean_text(text)
    words = text.split(' ')
    
    if len(words) <= chunk_size:
        return [text]
        
    chunks = []
    step = chunk_size - chunk_overlap
    if step <= 0:
        step = chunk_size // 2  # Guard against negative or zero steps
        
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append(chunk_text)
        # Stop once we have consumed the rest of the text
        if i + chunk_size >= len(words):
            break
            
    return chunks

def split_text_recursively(text: str, max_chars: int = 1000, overlap_chars: int = 200) -> List[str]:
    """
    Splits text by structural boundaries (paragraphs, sentences)
    to maintain grammatical integrity before falling back to character counts.
    """
    text = clean_text(text)
    if len(text) <= max_chars:
        return [text]
        
    # Split by sentence endings first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            # Start new chunk, incorporating overlap from the end of current_chunk if possible
            if len(sentence) > max_chars:
                # If a single sentence is larger than max_chars, split it by words
                words = sentence.split(' ')
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= max_chars:
                        sub_chunk = f"{sub_chunk} {word}".strip() if sub_chunk else word
                    else:
                        chunks.append(sub_chunk)
                        sub_chunk = word
                current_chunk = sub_chunk
            else:
                current_chunk = sentence
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks
