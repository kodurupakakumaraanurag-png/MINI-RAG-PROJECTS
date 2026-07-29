import os
import sys

# Ensure parent directory is in the path so we can import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.rag_engine import RAGEngine

def main():
    # Define Campus Policies data
    policies_data = (
        "Campus Rules and Regulations Handbook:\n\n"
        "1. Library Borrowing Policy:\n"
        "- Standard students can borrow a maximum of 5 books at any given time.\n"
        "- The loan period is 14 days per book. A late fine of $1.00 per book per day will be charged for overdue items.\n"
        "- Library access is suspended if outstanding fines exceed $10.00.\n\n"
        "2. Hostel Curfew & Entry:\n"
        "- The hostel main gate closes at 9:30 PM on weekdays (Monday to Friday).\n"
        "- On weekends (Saturday and Sunday), the gate closes at 11:00 PM.\n"
        "- Any student arriving after curfew hours without prior written permission from the hostel warden will face disciplinary actions, including parent notification and a $20 fine.\n\n"
        "3. Internal Examination & Attendance:\n"
        "- Students must maintain at least 75% attendance in each subject to qualify for mid-term and end-term examinations.\n"
        "- Absence due to medical emergencies requires an official medical certificate submitted within 3 working days.\n\n"
        "4. Semester Tuition Fee Deadlines:\n"
        "- Tuition fee payments must be cleared by the 10th of the semester-start month.\n"
        "- Payments made between the 11th and 20th incur a late fee of $50.\n"
        "- Non-payment after the 20th results in suspension of student registration."
    )

    # Initialize RAG Engine
    engine = RAGEngine(max_words=100, overlap=20, top_k=2)

    # Chunk the policy data
    chunks = engine._chunk(policies_data)
    print(f"--- Campus FAQ Helpdesk ---")
    print(f"Total chunks created: {len(chunks)}\n")

    # Define test queries
    queries = [
        "How many books can I borrow from the library?",
        "Can I enter the hostel at 10 PM on a Saturday?",
        "Can I get into trouble for being late?"
    ]

    persona = "a friendly campus helpdesk assistant for students"

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
