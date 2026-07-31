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

# Campus FAQs covering fee deadlines & late fees, hostel curfew, library policy, and exams
CAMPUS_DOCS = [
    "Semester Tuition Fee Payment Policy:\n"
    "- Tuition fees must be paid before the start of each semester. The final payment deadline is the first day of instruction.\n"
    "- Any payments made after the deadline will be subject to a flat late fee penalty of Rs. 500.",
    
    "Hostel Curfew Regulations:\n"
    "- All hostel residents must adhere to strict campus entry curfews for safety purposes.\n"
    "- The curfew time is 9:30 PM on weekdays (Monday through Friday).\n"
    "- Over weekends (Saturday and Sunday), the curfew is extended to 11:00 PM.\n"
    "- Violation of curfew guidelines results in disciplinary notice from the warden.",
    
    "Central Library Borrowing and Book Circulation Policy:\n"
    "- Students can borrow books using their Student ID card.\n"
    "- A student is allowed to borrow a maximum of 4 books at any single time.\n"
    "- Books can be kept for a borrowing period of up to 14 days. Renewals are permitted before the due date if there are no holds.\n"
    "- Overdue books attract standard daily late return fines.",
    
    "Academic Assessment and Internal Examination Schedule:\n"
    "- The academic calendar lists two sets of mid-semester internal assessments.\n"
    "- The first internal exams are held during the 7th week of the academic semester.\n"
    "- The second internal exams are conducted during the 12th week of the academic semester.\n"
    "- Make-up exams are only allowed for documented medical emergencies."
]

def main():
    persona = "a friendly campus helpdesk assistant for students"
    
    bot = RAGEngine(
        documents=CAMPUS_DOCS,
        persona=persona,
        max_words=80,
        overlap=15,
        title="Campus Helpdesk"
    )
    
    console.clear()
    console.print(Panel.fit("🎓 CAMPUS FAQ ASSISTANT", style="bold cyan"))
    console.print("[dim]Ask about fees, hostel curfew hours, library borrowing terms, or internal exams schedule.[/dim]\n")
    
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
