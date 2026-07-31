import os
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

# Standard fallback text resume documents covering React Native, Firebase, Power BI, SQL, Python, and RAG systems
DEFAULT_RESUME = (
    "Candidate Profile:\n"
    "Name: Alex Mercer\n"
    "Target Role: Senior Full Stack & AI Engineer\n\n"
    "Technical Core Skills:\n"
    "- Frontend & Mobile: React Native, Expo, Redux, Javascript, TypeScript, HTML/CSS.\n"
    "- Backend & Database: Python (FastAPI, Flask), SQL (PostgreSQL, MySQL), Firebase (Firestore, Authentication, Cloud Functions).\n"
    "- Data Analytics & Business Intelligence: Power BI, DAX queries, data modeling, ETL pipelines.\n"
    "- Artificial Intelligence & NLP: Retrieval-Augmented Generation (RAG) systems, LangChain, semantic search, TF-IDF vector retrieval, LLM prompt engineering.\n\n"
    "Work Experience:\n"
    "1. Senior AI & Mobile Engineer | InnovateTech (2023 - Present)\n"
    "   - Architected and built a cross-platform mobile application using React Native and Firebase, achieving 100k+ downloads.\n"
    "   - Developed a local-first Python RAG system to query large technical manuals, improving retrieval latency by 35%.\n"
    "2. Data & Relational Systems Analyst | FinTech Corp (2021 - 2023)\n"
    "   - Managed complex relational PostgreSQL databases using advanced SQL queries and optimization techniques.\n"
    "   - Designed and built interactive executive performance dashboards in Power BI utilizing DAX for real-time reporting."
)

def main():
    resume_path = "resume.pdf"
    if os.path.exists(resume_path):
        documents = [resume_path]
    else:
        documents = [DEFAULT_RESUME]
        
    persona = "an interview coach helping the candidate rehearse answers about their own experience"
    
    bot = RAGEngine(
        documents=documents,
        persona=persona,
        max_words=80,
        overlap=15,
        title="Interview Coach"
    )
    
    console.clear()
    console.print(Panel.fit("🎯 INTERVIEW COACH BOT", style="bold green"))
    console.print("[dim]Coach Mode Active: Ask questions to practice your experience details or technical interview answers.[/dim]\n")
    
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
