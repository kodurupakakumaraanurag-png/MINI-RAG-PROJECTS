import os
import sys
import re

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

import anthropic
import openai
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class RAGEngine:
    def __init__(self, max_words=80, overlap=15, top_k=2):
        self.max_words = max_words
        self.overlap = overlap
        self.top_k = top_k

    def _chunk(self, text: str) -> list[dict]:
        """Splits text into overlapping word chunks and returns list of dictionaries."""
        words = text.split()
        chunks = []
        if not words:
            return chunks
            
        step = self.max_words - self.overlap
        if step <= 0:
            step = 1
            
        i = 0
        idx = 0
        while i < len(words):
            chunk_words = words[i:i + self.max_words]
            chunks.append({
                "index": idx,
                "text": " ".join(chunk_words)
            })
            idx += 1
            i += step
            if i >= len(words):
                break
        return chunks

    def retrieve(self, query: str, chunks: list[dict]) -> list[tuple[dict, float]]:
        """Fits TF-IDF on chunks, scores similarity, and returns ranked list of (chunk, score) tuples."""
        if not chunks:
            return []
            
        chunk_texts = [c["text"] for c in chunks]
        vectorizer = TfidfVectorizer(stop_words="english")
        
        try:
            chunk_vectors = vectorizer.fit_transform(chunk_texts)
            query_vector = vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, chunk_vectors).flatten()
        except Exception:
            # Fallback if TF-IDF fails (e.g., all words filtered as stop words)
            return [(c, 0.0) for c in chunks[:self.top_k]]
            
        ranked_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in ranked_indices[:self.top_k]:
            results.append((chunks[idx], float(similarities[idx])))
            
        return results

    def ask(self, query: str, retrieved_chunks: list[tuple[dict, float]], persona: str = None) -> str:
        """Generates grounded response using Anthropic or OpenAI API, with a local heuristic fallback."""
        # Enforce strict grounding: if retrieval score is zero, assume missing info
        if not retrieved_chunks or all(score == 0.0 for _, score in retrieved_chunks):
            return "I don't have that information"
            
        # Format retrieval context block
        context_str = ""
        for chunk, score in retrieved_chunks:
            context_str += f"[Source {chunk['index']}]\n{chunk['text']}\n\n"
            
        persona_str = persona or "a helpful RAG assistant"
        
        prompt = (
            f"You are {persona_str}.\n\n"
            "RULES FOR ANSWERING:\n"
            "1. Answer the User Query ONLY using the facts present in the Context section below.\n"
            "2. Do NOT use outside knowledge, extrapolate, or assume facts not explicitly mentioned.\n"
            "3. If the Context does not contain the answer, you must return exactly the string: \"I don't have that information\" and nothing else.\n"
            "4. Cite your facts by referencing the source label in brackets (e.g., [Source 0], [Source 1], etc.) inline whenever citing a fact.\n\n"
            "Context:\n"
            f"{context_str}\n"
            f"User Query: {query}\n\n"
            "Answer:"
        )
        
        # Detect API keys
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
        
        # Route fallback/cleanup if API_KEY is set to Gemini key (starts with AQ.)
        if openai_key and (openai_key.startswith("AQ.") or not openai_key.startswith("sk-")):
            gemini_key = openai_key
            openai_key = None
            
        if gemini_key:
            # Google Gemini 3.5 Flash
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 500
                    },
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": f"You are {persona_str}. You are a strictly grounded assistant. Answer only from the provided context. If the answer is not present, reply exactly with: I don't have that information"
                            }
                        ]
                    }
                }
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                res_data = res.json()
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                return self._heuristic_fallback(query, retrieved_chunks, persona_str)
                
        elif anthropic_key and anthropic_key.startswith("sk-ant-"):
            # Anthropic Claude 3.5 Sonnet
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=500,
                    temperature=0.2,
                    system=f"You are {persona_str}. You are a strictly grounded assistant. Answer only from the provided context. If the answer is not present, reply exactly with: I don't have that information",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text.strip()
            except Exception:
                return self._heuristic_fallback(query, retrieved_chunks, persona_str)
        elif openai_key:
            # OpenAI GPT-4o (handles sk-proj- or standard sk- keys)
            try:
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=500,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": f"You are {persona_str}. You are a strictly grounded assistant. Answer only from the provided context. If the answer is not present, reply exactly with: I don't have that information"},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content.strip()
            except Exception:
                return self._heuristic_fallback(query, retrieved_chunks, persona_str)
        else:
            return self._heuristic_fallback(query, retrieved_chunks, persona_str)

    def _heuristic_fallback(self, query: str, retrieved_chunks: list[tuple[dict, float]], persona: str) -> str:
        """Determins a fallback response programmatically by extracting sentences containing search query keywords."""
        keywords = [w.lower().strip(",.?!()\"'") for w in query.split()]
        stop_words = {"what", "is", "the", "of", "and", "a", "to", "in", "for", "on", "with", "at", "by", "an", "this", "that", "how", "why", "who", "where", "can", "could", "would", "should", "will", "do", "does", "did"}
        keywords = [w for w in keywords if w and w not in stop_words and len(w) > 2]
        
        sentences_found = []
        for chunk, score in retrieved_chunks:
            if score == 0.0:
                continue
            sentences = re.split(r'(?<=[.!?])\s+', chunk["text"])
            for sent in sentences:
                sent_clean = sent.lower()
                matches = sum(1 for kw in keywords if kw in sent_clean)
                if matches > 0:
                    sentences_found.append({
                        "text": sent.strip(),
                        "matches": matches,
                        "source": f"[Source {chunk['index']}]",
                        "score": score
                    })
                    
        sentences_found.sort(key=lambda x: (-x["matches"], -x["score"]))
        
        if not sentences_found:
            return "I don't have that information"
            
        selected_lines = []
        used_sents = set()
        for s in sentences_found[:3]:
            if s["text"] not in used_sents:
                selected_lines.append(f"{s['text']} {s['source']}")
                used_sents.add(s["text"])
                
        intro = f"[Local Heuristic Fallback] As {persona}, here is the matching facts from the document:\n\n"
        return intro + "\n\n".join(selected_lines)
