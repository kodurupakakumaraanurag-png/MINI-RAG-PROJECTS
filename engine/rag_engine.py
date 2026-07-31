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

    def _is_greeting(self, query: str) -> bool:
        clean = re.sub(r'[^\w\s]', '', query.lower().strip())
        greetings = {
            "hi", "hello", "hey", "hello there", "hi there", "greetings", "good morning", 
            "good afternoon", "good evening", "howdy", "hola", "yo", "who are you", 
            "what are you", "what is your name", "how are you", "help", "chitchat",
            "are you there", "good day"
        }
        return clean in greetings or any(clean == g for g in greetings) or clean.startswith("hi ") or clean.startswith("hello ") or clean.startswith("hey ")

    def ask(self, query: str, retrieved_chunks: list[tuple[dict, float]], persona: str = None, strict_grounding: bool = True) -> str:
        """Generates grounded response using Anthropic or OpenAI API, with a local heuristic fallback."""
        persona_str = persona or "a helpful RAG assistant"
        is_greet = self._is_greeting(query)

        # Enforce strict grounding: if retrieval score is zero, assume missing info, unless it is a greeting/chitchat or strict grounding is disabled
        if not is_greet and strict_grounding:
            if not retrieved_chunks or all(score == 0.0 for _, score in retrieved_chunks):
                return "I don't have that information"
            
        # Format retrieval context block
        context_str = ""
        for chunk, score in retrieved_chunks:
            context_str += f"[Source {chunk['index']}]\n{chunk['text']}\n\n"
            
        if is_greet:
            prompt = (
                f"You are {persona_str}.\n\n"
                "The user is greeting you or initiating conversation. "
                "Respond politely and introduce yourself as your persona, inviting them to ask questions about your documents. Keep it short."
            )
            system_instr = f"You are {persona_str}. Respond politely to the user greeting or chitchat. Keep it brief and friendly."
        elif strict_grounding:
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
            system_instr = f"You are {persona_str}. You are a strictly grounded assistant. Answer only from the provided context. If the answer is not present, reply exactly with: I don't have that information"
        else:
            prompt = (
                f"You are {persona_str}.\n\n"
                "Answer the User Query. If relevant facts are present in the Context section below, use them and cite them using bracket labels (e.g. [Source 0]). "
                "If the Context does not contain the answer, you must use your pre-trained general knowledge to answer the query accurately like a normal AI. "
                "Do not use bracket citations if the information comes from your own pre-trained knowledge.\n\n"
                "Context:\n"
                f"{context_str}\n"
                f"User Query: {query}\n\n"
                "Answer:"
            )
            system_instr = f"You are {persona_str}. Prioritize context facts and use citations if context has the answer; otherwise, use your general knowledge to answer the user query."
        
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
                                "text": system_instr
                            }
                        ]
                    }
                }
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                res.raise_for_status()
                res_data = res.json()
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                if is_greet:
                    return f"Hello! As {persona_str}, how can I help you today?"
                return self._heuristic_fallback(query, retrieved_chunks, persona_str, strict_grounding)
                
        elif anthropic_key and anthropic_key.startswith("sk-ant-"):
            # Anthropic Claude 3.5 Sonnet
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=500,
                    temperature=0.2,
                    system=system_instr,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text.strip()
            except Exception:
                if is_greet:
                    return f"Hello! As {persona_str}, how can I help you today?"
                return self._heuristic_fallback(query, retrieved_chunks, persona_str, strict_grounding)
        elif openai_key:
            # OpenAI GPT-4o (handles sk-proj- or standard sk- keys)
            try:
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=500,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": system_instr},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content.strip()
            except Exception:
                if is_greet:
                    return f"Hello! As {persona_str}, how can I help you today?"
                return self._heuristic_fallback(query, retrieved_chunks, persona_str, strict_grounding)
        else:
            if is_greet:
                return f"Hello! As {persona_str}, how can I help you today?"
            return self._heuristic_fallback(query, retrieved_chunks, persona_str, strict_grounding)

    def _heuristic_fallback(self, query: str, retrieved_chunks: list[tuple[dict, float]], persona: str, strict_grounding: bool = True) -> str:
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
            if not strict_grounding:
                return f"I'm sorry, I couldn't find a direct answer in the document, and the AI model is currently offline. Please try again."
            return "I don't have that information"
            
        selected_lines = []
        used_sents = set()
        for s in sentences_found[:3]:
            if s["text"] not in used_sents:
                selected_lines.append(f"{s['text']} {s['source']}")
                used_sents.add(s["text"])
                
        intro = f"[Local Heuristic Fallback] As {persona}, here is the matching facts from the document:\n\n"
        return intro + "\n\n".join(selected_lines)
