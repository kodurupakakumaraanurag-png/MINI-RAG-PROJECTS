# Modular RAG System with 5 Mini Use-Cases

A modular, reusable Retrieval-Augmented Generation (RAG) system with five distinct configurations demonstrating strict grounding, custom text chunking, and persona-driven outputs.

---

## 1. Use Case Comparison Table

The table below summarizes the configurations across all five applications:

| Use Case | Chunk Size (`max_words`) | Overlap (`overlap`) | Top-K | Persona Tone | Key Technical Insight |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **01. Interview Prep** | `80` | `15` | `2` | Professional interview coach | Word count tuned for resume project descriptions to avoid combining distinct projects in a single chunk. |
| **02. Campus FAQ** | `100` | `20` | `2` | Friendly campus assistant | Larger chunk size to cover multiple bullet points within curfew or library rules. |
| **03. Study Buddy** | `50` | `12` | `2` | Patient study partner | Chunk size tuned down to `50` words for dense academic OS scheduling text to capture highly granular concepts (e.g., FCFS, SJF) without dilution. |
| **04. E-Commerce Support** | `80` | `15` | `2` | Polite customer support agent | Compact chunks to isolate individual product attributes (colors, size) and return policies. |
| **05. Code Docs** | `100` | `20` | `2` | Precise technical developer assistant | Matches structured docstrings and function inputs, ensuring code samples and params stay together. |

---

## 2. 4-Part Interview Speaking Framework

When discussing this architecture in a technical interview, use the following structured overview:

### Part 1: What It Does
This is a modular, multi-use case RAG (Retrieval-Augmented Generation) system designed to test and enforce strict factual grounding across diverse contexts. It ingests domain documents, segments them into semantically overlapping chunks, retrieves relevant sections based on user questions, and routes the context to an LLM. It supports custom personas, forces citations using `[Source X]` tags, and implements a strict fallback behavior: returning *"I don't have that information"* if the question cannot be answered using only the provided context.

### Part 2: How It Works
1. **Document Segmenting**: The engine splits text into word-based chunks of size `max_words` with a sliding `overlap` window. This sliding boundary prevents semantic context from being split in half at chunk endings.
2. **Vector Retrieval**: It uses a local `TfidfVectorizer` (with English stop-word filtering) and computes the **Cosine Similarity** between the query vector and chunk vectors. It returns the top-`K` matching chunks.
3. **LLM Grounding & Citations**: It builds a structured message incorporating the retrieved chunks labeled with their source indices. The system prompt instructs the model to answer using only the provided chunks, cite sources inline (e.g., `[Source 0]`), and return the exact fallback phrase if the information is missing.
4. **Resiliency Fallback**: The client dynamically checks credentials (`sk-ant-...` vs `sk-proj-...`), choosing Anthropic Claude or OpenAI GPT-4o. If an API limit or outage occurs, the engine automatically routes queries to a local grounded heuristic engine to ensure continuous delivery.

### Part 3: Technical Decisions Made
- **Granular Academic Chunking**: For the **Study Buddy** use case (Operating Systems), the chunk size was reduced to `50` words with an `overlap` of `12`. Academic text is highly dense—a single paragraph can describe multiple distinct algorithms. Diluting this with a larger chunk size would lead to irrelevant text being retrieved, wasting tokens and confusing the model.
- **TF-IDF Keyword Retrieval**: Rather than loading heavy neural embedding models (like HuggingFace or OpenAI embeddings) which introduce latency and external API costs, the system uses TF-IDF vectorization. For small-scale, document-specific guides, TF-IDF provides near-zero latency and matches exact query terms efficiently.
- **Dynamic Multi-Provider Client & Local Fallback**: We designed the engine to support both Anthropic and OpenAI clients based on API key prefix. We also built a local heuristic fallback engine that parses the queries and documents deterministically when API services or billing limits are hit.

### Part 4: Limitations Acknowledged
- **Synonym Mismatch in TF-IDF**: Because the retriever uses TF-IDF, it relies on exact or overlapping word matches. If a user asks a query using synonyms (e.g., "CPU allocation rules" instead of "Process scheduling algorithms"), the retrieval scores will be low. *Mitigation:* In a production system, this would be upgraded to dense vector embeddings (like `text-embedding-3-small` or `bge-large-en`) to capture semantic meaning.
- **Keyword Over-Matching**: Since the TF-IDF vectorizer ignores stop words and evaluates word frequencies, short query words (like "late") might match multiple sections (e.g., library late fees vs tuition late fees) and require fine-tuning of similarity thresholds to prevent returning noise.
