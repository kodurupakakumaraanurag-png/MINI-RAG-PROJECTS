import os
import sys

# Ensure parent directory is in the path so we can import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.rag_engine import RAGEngine

def main():
    # Backpack store catalog and policy data
    backpack_data = (
        "Nomad Backpack Store - Product and Policy Details:\n\n"
        "1. Product Details (Nomad Pro Backpack):\n"
        "- Laptop Compatibility: Includes a dedicated, padded laptop sleeve that fits up to 16-inch laptops (including 15-inch models).\n"
        "- Available Colors: Comes in Midnight Black, Olive Green, Steel Blue, and Charcoal Gray.\n"
        "- Material & Durability: Made from water-resistant 900D ballistic polyester with reinforced double stitching.\n"
        "- Key Features: USB charging port, anti-theft back pocket, and heavy-duty YKK zippers.\n\n"
        "2. Store Return Policy:\n"
        "- Customers can return purchases within a 15-day window from the delivery date for a full refund.\n"
        "- Items must be in brand new, unused condition with all tags and original packaging intact.\n"
        "- Returns initiated after 15 days from delivery are strictly not eligible for refunds or store credits.\n\n"
        "3. Shipping Information:\n"
        "- Free standard shipping within the continental US for all orders over $75; otherwise, flat rate $4.99.\n"
        "- Express shipping options are available at checkout: 2-Day Shipping for $12.99.\n\n"
        "4. Product Warranty:\n"
        "- Every backpack includes a 2-Year Limited Warranty covering manufacturing defects in materials or craftsmanship (e.g. zipper or strap failure)."
    )

    # Initialize RAG Engine
    engine = RAGEngine(max_words=80, overlap=15, top_k=2)

    # Chunk the e-commerce data
    chunks = engine._chunk(backpack_data)
    print(f"--- E-Commerce Support Agent ---")
    print(f"Total chunks created: {len(chunks)}\n")

    # Define test queries
    queries = [
        "Does the backpack fit a 15-inch laptop, and what colors does it come in?",
        "If I return the backpack after 20 days, will I get a refund?"
    ]

    persona = "a polite customer support agent for an online backpack store"

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
