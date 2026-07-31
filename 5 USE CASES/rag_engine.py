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

import pypdf
import anthropic
import openai
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.markdown import Markdown

class RAGEngine:
    def __init__(self, documents, persona, max_words=80, overlap=15, title=""):
        """
        Initializes the RAG Engine.
        
        Args:
            documents (list): List of strings (raw texts) or PDF file paths.
            persona (str): Persona string Claude should adopt.
            max_words (int): Maximum words per chunk. Default 80.
            overlap (int): Number of overlapping words between chunks. Default 15.
            title (str): Title for the UI panel display.
        """
        self.persona = persona
        self.max_words = max_words
        self.overlap = overlap
        self.title = title
        
        # Initialize Rich console with custom dark theme aesthetics
        custom_theme = Theme({
            "info": "dim cyan",
            "warning": "bold yellow",
            "error": "bold red",
            "success": "bold green",
            "badge": "bold white on blue"
        })
        self.console = Console(theme=custom_theme)
        
        # Detect API keys
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
        
        # Route fallback/cleanup if API_KEY is set to Gemini key (starts with AQ.)
        if self.openai_key and (self.openai_key.startswith("AQ.") or not self.openai_key.startswith("sk-")):
            self.gemini_key = self.openai_key
            self.openai_key = None
            
        # Initialize Anthropic Client conditionally
        self.client = None
        if self.anthropic_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.anthropic_key)
            except Exception:
                pass
                
        # Model default
        self.model_name = "claude-3-5-sonnet-20241022"
        
        # Load and parse documents
        self.documents = []
        if isinstance(documents, str):
            documents = [documents]
            
        for idx, doc in enumerate(documents):
            if isinstance(doc, str) and doc.lower().endswith(".pdf"):
                if os.path.exists(doc):
                    try:
                        reader = pypdf.PdfReader(doc)
                        text = ""
                        for page in reader.pages:
                            extracted = page.extract_text()
                            if extracted:
                                text += extracted + "\n"
                        if text.strip():
                            self.documents.append({
                                "content": text,
                                "source": os.path.basename(doc)
                            })
                    except Exception as e:
                        self.console.print(f"[warning]Failed to parse PDF {doc}: {e}[/warning]")
                else:
                    self.console.print(f"[warning]PDF file not found: {doc}[/warning]")
            elif isinstance(doc, str):
                self.documents.append({
                    "content": doc,
                    "source": f"Source {idx + 1}"
                })
        
        # Sliding-window chunking
        self.chunks = []
        for doc in self.documents:
            doc_chunks = self._chunk(doc["content"])
            for ch in doc_chunks:
                self.chunks.append({
                    "text": ch,
                    "source": doc["source"]
                })
                
        # Vectorization using TF-IDF
        chunk_texts = [c["text"] for c in self.chunks]
        if not chunk_texts:
            # Fallback if no content was loaded
            chunk_texts = ["empty"]
            self.chunks = [{"text": "No content loaded.", "source": "System"}]
            
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.chunk_vectors = self.vectorizer.fit_transform(chunk_texts)

    def _chunk(self, text):
        """Splits text into overlapping chunks using a sliding window of words."""
        words = text.split()
        chunks = []
        if not words:
            return chunks
            
        step = self.max_words - self.overlap
        if step <= 0:
            step = 1  # Guard against infinite loops or negative step sizes
            
        i = 0
        while i < len(words):
            chunk_words = words[i:i + self.max_words]
            chunks.append(" ".join(chunk_words))
            i += step
            if i >= len(words):
                break
        return chunks

    def normalize_query(self, raw_query):
        """
        Sends the raw query to Claude or Gemini or OpenAI to normalize spelling mistakes, slang,
        and expand implicit intents to create an optimized keyword query for TF-IDF.
        """
        prompt = (
            "You are a search query optimizer. Your job is to process raw user queries for a TF-IDF search index.\n"
            "Instructions:\n"
            "1. Fix any spelling mistakes, typos, or slang.\n"
            "2. Expand implicit search intents so they map to standard database keywords.\n"
            "3. Output ONLY the clean, search-optimized query string.\n"
            "4. Do NOT include any explanations, intros, markdown, quotes, or notes.\n\n"
            f"Raw User Query: {raw_query}"
        )
        
        if self.gemini_key:
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_key}"
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
                        "temperature": 0.0,
                        "maxOutputTokens": 100
                    },
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": "You output only the optimized search query text. Never add metadata, quotes, introductory or conversational filler."
                            }
                        ]
                    }
                }
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                res_data = res.json()
                normalized = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if normalized.startswith('"') and normalized.endswith('"'):
                    normalized = normalized[1:-1].strip()
                return normalized
            except Exception:
                return raw_query

        elif self.client:
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=100,
                    temperature=0.0,
                    system="You output only the optimized search query text. Never add metadata, quotes, introductory or conversational filler.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                normalized = response.content[0].text.strip()
                # Remove wrapped quotes if Claude added them
                if normalized.startswith('"') and normalized.endswith('"'):
                    normalized = normalized[1:-1].strip()
                return normalized
            except Exception:
                return raw_query
                
        elif self.openai_key:
            try:
                client = openai.OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=100,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": "You output only the optimized search query text. Never add metadata, quotes, introductory or conversational filler."},
                        {"role": "user", "content": prompt}
                    ]
                )
                normalized = response.choices[0].message.content.strip()
                if normalized.startswith('"') and normalized.endswith('"'):
                    normalized = normalized[1:-1].strip()
                return normalized
            except Exception:
                return raw_query
        else:
            return raw_query

    def retrieve(self, query, top_k=3):
        """Normalizes query and retrieves the top_k matching chunks using TF-IDF and cosine similarity."""
        normalized_query = self.normalize_query(query)
        
        if not hasattr(self, "chunk_vectors") or self.chunk_vectors.shape[0] == 0:
            return [], normalized_query
            
        query_vector = self.vectorizer.transform([normalized_query])
        similarities = cosine_similarity(query_vector, self.chunk_vectors).flatten()
        
        # Argpartion / argsort to find the top k
        top_k = min(top_k, len(similarities))
        top_k_indices = np.argsort(similarities)[::-1][:top_k]
        
        retrieved = []
        for idx in top_k_indices:
            chunk_info = self.chunks[idx].copy()
            chunk_info["score"] = float(similarities[idx])
            retrieved.append(chunk_info)
            
        return retrieved, normalized_query

    def _is_greeting(self, query: str) -> bool:
        clean = re.sub(r'[^\w\s]', '', query.lower().strip())
        greetings = {
            "hi", "hello", "hey", "hello there", "hi there", "greetings", "good morning", 
            "good afternoon", "good evening", "howdy", "hola", "yo", "who are you", 
            "what are you", "what is your name", "how are you", "help", "chitchat",
            "are you there", "good day"
        }
        return clean in greetings or any(clean == g for g in greetings) or clean.startswith("hi ") or clean.startswith("hello ") or clean.startswith("hey ")

    def ask(self, query, top_k=3, strict_grounding=True):
        """Retrieves contexts, queries Claude/Gemini/OpenAI with grounding constraints, and renders styled output."""
        is_greet = self._is_greeting(query)
        
        with self.console.status("[bold green]Analyzing context and generating response...", spinner="dots"):
            # Fetch retrieved context
            retrieved_chunks, normalized_query = self.retrieve(query, top_k=top_k)
            
            # Construct text blocks for context
            context_str = ""
            for idx, chunk in enumerate(retrieved_chunks):
                # Present each block with source label clearly
                context_str += f"[{chunk['source']}]\n{chunk['text']}\n\n"
                
            if is_greet:
                prompt = (
                    f"You are {self.persona}.\n\n"
                    "The user is greeting you or initiating conversation. "
                    "Respond politely and introduce yourself as your persona, inviting them to ask questions about your documents. Keep it short."
                )
                system_instr = f"You are {self.persona}. Respond politely to the user greeting or chitchat. Keep it brief and friendly."
            elif strict_grounding:
                prompt = (
                    f"You are {self.persona}.\n\n"
                    "RULES FOR ANSWERING:\n"
                    "1. Answer the User Query ONLY using the facts present in the Context section below.\n"
                    "2. Do NOT use outside knowledge, extrapolate, or assume facts not explicitly mentioned.\n"
                    "3. If the Context does not contain the answer, say: 'I\'m sorry, but I do not have information about that in the provided documents.'\n"
                    "4. Cite your facts by referencing the source label in brackets (e.g., [resume.pdf], [Source 1], etc.) inline whenever citing a fact.\n"
                    "5. FORMATTING: Format lists cleanly using standard markdown (e.g. * or - for bullet points, 1. 2. for numbered lists). Never output literal characters like 'o' or custom shapes as bullet points. Do not leave blank lines between numbered list headers and their sub-bullets.\n\n"
                    "Context:\n"
                    f"{context_str}\n"
                    f"User Query: {query}\n\n"
                    "Answer:"
                )
                system_instr = f"You are {self.persona}. You are a grounded QA assistant. Answer only from the provided context. If the answer is not present, say that you don't know. Format markdown lists cleanly using standard '*' or '-' bullets, avoiding raw text characters like 'o'."
            else:
                prompt = (
                    f"You are {self.persona}.\n\n"
                    "Answer the User Query. If relevant facts are present in the Context section below, use them and cite them using bracket labels (e.g. [resume.pdf]). "
                    "If the Context does not contain the answer, you must use your pre-trained general knowledge to answer the query accurately like a normal AI. "
                    "Do not use bracket citations if the information comes from your own pre-trained knowledge.\n"
                    "FORMATTING: Format lists cleanly using standard markdown (e.g. * or - for bullet points, 1. 2. for numbered lists). Never output literal characters like 'o' or custom shapes as bullet points. Do not leave blank lines between numbered list headers and their sub-bullets.\n\n"
                    "Context:\n"
                    f"{context_str}\n"
                    f"User Query: {query}\n\n"
                    "Answer:"
                )
                system_instr = f"You are {self.persona}. Prioritize context facts and use citations if context has the answer; otherwise, use your general knowledge to answer the user query. Format markdown lists cleanly using standard '*' or '-' bullets, avoiding raw text characters like 'o'."
            
            response_text = ""
            if self.gemini_key:
                try:
                    import requests
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_key}"
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
                            "maxOutputTokens": 600
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
                    response_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception as e:
                    if is_greet:
                        response_text = f"Hello! As {self.persona}, how can I help you today?"
                    else:
                        response_text = f"**Error calling Gemini API:** {str(e)}"
                    
            elif self.client:
                try:
                    response = self.client.messages.create(
                        model=self.model_name,
                        max_tokens=600,
                        temperature=0.2,
                        system=system_instr,
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    response_text = response.content[0].text.strip()
                except Exception as e:
                    if is_greet:
                        response_text = f"Hello! As {self.persona}, how can I help you today?"
                    else:
                        response_text = f"**Error calling Anthropic API:** {str(e)}"
                    
            elif self.openai_key:
                try:
                    client = openai.OpenAI(api_key=self.openai_key)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        max_tokens=600,
                        temperature=0.2,
                        messages=[
                            {"role": "system", "content": system_instr},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    response_text = response.choices[0].message.content.strip()
                except Exception as e:
                    if is_greet:
                        response_text = f"Hello! As {self.persona}, how can I help you today?"
                    else:
                        response_text = f"**Error calling OpenAI API:** {str(e)}"
            else:
                if is_greet:
                    response_text = f"Hello! As {self.persona}, how can I help you today?"
                else:
                    response_text = "No configured API key found (tried GEMINI_API_KEY, ANTHROPIC_API_KEY, and OPENAI_API_KEY / API_KEY)."
                
        # Render the response elements with high-aesthetic styling
        self.console.print()
        self.console.print(f"[bold yellow]Normalized Query ❯[/bold yellow] [badge] {normalized_query} [/badge]")
        self.console.print()
        
        panel = Panel(
            Markdown(response_text),
            title=f"[bold green]{self.title}[/bold green]" if self.title else "Response",
            border_style="cyan",
            expand=False
        )
        self.console.print(panel)
        self.console.print()
