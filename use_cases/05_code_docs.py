import os
import sys

# Ensure parent directory is in the path so we can import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.rag_engine import RAGEngine

def main():
    # RAGEngine API Documentation as the context
    api_docs = (
        "RAGEngine Codebase API Documentation:\n\n"
        "1. Function: RAGEngine._chunk(text: str) -> List[Dict[str, Any]]\n"
        "- Description: Splitting large input text documents into smaller word-based chunks.\n"
        "- Parameters:\n"
        "  * text (str): The input string to chunk.\n"
        "- Class parameters used:\n"
        "  * max_words (int): Maximum words per chunk.\n"
        "  * overlap (int): Word overlap count between adjacent chunks.\n"
        "- Return: A list of dictionaries containing 'index' (0-indexed position) and 'text' (the chunked string).\n"
        "- Importance of overlap: The overlap represents the number of shared words between consecutive chunks. It matters because it prevents loss of semantic context at the boundaries. If a critical detail is split in half across a boundary, overlap ensures it is captured completely in at least one chunk.\n\n"
        "2. Function: RAGEngine.retrieve(query: str, chunks: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]\n"
        "- Description: Searches chunked documents for matches to the user's query.\n"
        "- Parameters:\n"
        "  * query (str): The search phrase or question.\n"
        "  * chunks (List[Dict]): The chunked documents to search within.\n"
        "- Internal logic: Converts chunks to TF-IDF matrix using TfidfVectorizer(stop_words='english') and computes cosine similarity with query's TF-IDF vector.\n"
        "- Class parameters used:\n"
        "  * top_k (int): Specifies how many top-ranking results to return.\n"
        "- Return: Sorted list of tuples: (chunk, cosine_similarity_score), ordered descending by similarity.\n\n"
        "3. Function: RAGEngine.ask(query: str, retrieved_chunks: List[Tuple[Dict, float]], persona: str = None) -> str\n"
        "- Description: Generates a grounded response via Anthropic's Claude 3.5 Sonnet API.\n"
        "- Parameters:\n"
        "  * query (str): User's question.\n"
        "  * retrieved_chunks (List): Selected context chunks from retrieve().\n"
        "  * persona (str, optional): Overrides system behavior with custom tone.\n"
        "- Strictly enforced grounding behavior:\n"
        "  * The LLM must only use facts stated in context.\n"
        "  * If context lacks required info, it returns exactly the fallback string: 'I don't have that information'.\n"
        "  * Each piece of information in the final answer must cite the source using formatting like [Source X]."
    )

    # Initialize RAG Engine
    engine = RAGEngine(max_words=100, overlap=20, top_k=2)

    # Chunk the API docs
    chunks = engine._chunk(api_docs)
    print(f"--- Developer Code Docs Assistant ---")
    print(f"Total chunks created: {len(chunks)}\n")

    # Define test queries
    queries = [
        "What does overlap do in chunk_text, and why does it matter?",
        "What does the ask() function return if nothing relevant is found?"
    ]

    persona = "a precise technical assistant explaining this library's API to a developer"

    # Execute queries
    for q in queries:
        print(f"Query: \"{q}\"")
        retrieved = engine.retrieve(q, chunks)
        print("Retrieved Chunks:")
        for chunk, score in retrieved:
            print(f" - [Source {chunk['index']}] (Similarity: {score:.4f}): {chunk['text'][:100]}...")
        
        answer = engine.ask(q, retrieved, persona=persona)
        print(f"Answer:\n{answer}\n")
        print("-" * 50)

if __name__ == "__main__":
    main()
