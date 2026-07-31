import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from rich.console import Console
from rich.panel import Panel
from rag_engine import RAGEngine

console = Console()

# Dense academic notes covering Operating System scheduling algorithms
OS_DOCS = [
    "First-Come, First-Served (FCFS) Process Scheduling:\n"
    "- FCFS is a non-preemptive scheduling policy. The CPU is allocated to processes in the exact order they arrive in the ready queue.\n"
    "- Main disadvantage is the Convoy Effect, where small processes wait behind a single CPU-heavy process, increasing average wait time.",
    
    "Shortest Job First (SJF) Process Scheduling:\n"
    "- SJF associates each process with the length of its next CPU burst and schedules the process with the smallest burst time.\n"
    "- SJF is mathematically optimal as it guarantees the minimum average waiting time for a set of processes.\n"
    "- SJF can be preemptive (Shortest Remaining Time First) or non-preemptive.",
    
    "Round Robin (RR) Process Scheduling:\n"
    "- Round Robin is a preemptive scheduling algorithm designed for time-sharing systems.\n"
    "- The CPU scheduler allocates a small, fixed unit of time called the 'time quantum' (or time slice) to each process in turn.\n"
    "- Once a process's time quantum expires, it is preempted and put back at the tail of the ready queue.",
    
    "Context Switching Overhead:\n"
    "- A context switch is the mechanism of saving the state (context) of a running process so it can be resumed later, and loading the saved state of another.\n"
    "- Context switching is pure computational overhead; no useful work is done during this transition.\n"
    "- If the Round Robin time quantum is extremely small, context switching overhead increases dramatically and slows down the CPU."
]

def main():
    persona = "a patient study partner helping the student revise for an exam, using simple explanations"
    
    # Tuned parameters: max_words=50, overlap=12 for dense academic concept retrieval
    bot = RAGEngine(
        documents=OS_DOCS,
        persona=persona,
        max_words=50,
        overlap=12,
        title="OS Study Buddy"
    )
    
    console.clear()
    console.print(Panel.fit("📚 OS STUDY BUDDY", style="bold yellow"))
    console.print("[dim]Study Partner Mode: Ask questions about FCFS, SJF, Round Robin, or Context Switching to revise.[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold cyan] You ❯ [/bold cyan]")
            if user_input.lower().strip() in ["exit", "quit"]:
                console.print("[bold red]Goodbye! 👋[/bold red]")
                break
            if not user_input.strip():
                continue
            bot.ask(user_input)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Goodbye! 👋[/bold red]")
            break

if __name__ == "__main__":
    main()
