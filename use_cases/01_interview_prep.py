import os
import sys

# Ensure parent directory is in the path so we can import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.rag_engine import RAGEngine

def main():
    # Define Resume data
    resume_data = (
        "Candidate Profile & Project Notes:\n\n"
        "1. Real-time Logistics Tracker Project:\n"
        "- Built a cross-platform React Native mobile application that tracks package deliveries in real-time.\n"
        "- Integrated Google Maps API and WebSockets (Socket.io) for live, low-latency driver location updates.\n"
        "- Handles over 1,000 active daily users and reduced delivery query tickets by 25%.\n\n"
        "2. TechCorp Business Intelligence Internship:\n"
        "- Developed an interactive Power BI dashboard tracking sales metrics across 5 global regions.\n"
        "- Designed optimized SQL queries to aggregate and clean daily transaction data from a PostgreSQL database.\n"
        "- Streamlined data pipelines, which improved executive reporting speed by 40%.\n\n"
        "3. Technical Skills:\n"
        "- Languages: Python, JavaScript, SQL, HTML/CSS.\n"
        "- Frameworks & Tools: React Native, React.js, Power BI, Git.\n"
        "- Core Concepts: Retrieval-Augmented Generation (RAG), vector search, relational databases, REST APIs."
    )

    # Initialize RAG Engine
    # Default params: max_words=100, overlap=20, top_k=2
    engine = RAGEngine(max_words=80, overlap=15, top_k=2)

    # Chunk the resume data
    chunks = engine._chunk(resume_data)
    print(f"--- Interview Prep Coach ---")
    print(f"Total chunks created: {len(chunks)}\n")

    # Define test queries
    queries = [
        "Tell me about a project where you worked with real-time data.",
        "What's a project where you handled payments?",
        "What's your weakest area?"
    ]

    persona = "an interview coach helping the candidate rehearse answers about their own experience"

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
