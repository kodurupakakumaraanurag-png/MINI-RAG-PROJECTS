import os
import sys

# Ensure parent directory is in the path so we can import engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.rag_engine import RAGEngine

def main():
    # Dense academic notes on CPU scheduling
    os_scheduling_data = (
        "Operating System CPU Scheduling Notes:\n\n"
        "1. First-Come, First-Served (FCFS) Scheduling:\n"
        "- The CPU is allocated to processes in the exact order they request it.\n"
        "- Non-preemptive algorithm that is simple to write and implement using a FIFO queue.\n"
        "- A major disadvantage is the convoy effect: a single long process running first can delay many short processes waiting behind it, resulting in poor CPU and device utilization.\n\n"
        "2. Shortest-Job-First (SJF) Scheduling:\n"
        "- The CPU is assigned to the process with the smallest next CPU burst.\n"
        "- Optimal algorithm because it yields the absolute minimum average waiting time for a set of processes.\n"
        "- Hard to implement because the length of the next CPU burst cannot be predicted precisely in advance.\n\n"
        "3. Round Robin (RR) Scheduling:\n"
        "- Designed for time-sharing systems, similar to FCFS but preemptive.\n"
        "- Each process gets a small slice of CPU time called a time quantum (typically 10-100 ms) in a circular queue.\n"
        "- While fair, RR introduces system overhead. This overhead comes from frequent context switching, where the system must save the register state of the running process and load the next process's state."
    )

    # Initialize RAG Engine with tuned parameters for dense text:
    # max_words=50, overlap=12
    engine = RAGEngine(max_words=50, overlap=12, top_k=2)

    # Chunk the academic data
    chunks = engine._chunk(os_scheduling_data)
    print(f"--- Study Buddy Revision Assistant ---")
    print(f"Total chunks created: {len(chunks)}\n")

    # Define test queries
    queries = [
        "Which scheduling algorithm causes the convoy effect and why?",
        "Why does Round Robin add overhead?"
    ]

    persona = "a patient study partner helping the student revise for an exam, using simple explanations"

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
