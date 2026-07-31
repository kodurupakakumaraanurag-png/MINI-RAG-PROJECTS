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

# API docstrings for chunk_text(), retrieve(), and ask()
API_DOCS = [
    "API Function: chunk_text(text, max_words=80, overlap=15)\n"
    "- Description: Splits a continuous text document into smaller, overlapping text segments (chunks) using a sliding-window algorithm.\n"
    "- Parameters:\n"
    "  * text (str): The continuous string content to be split.\n"
    "  * max_words (int): The maximum count of words per output chunk.\n"
    "  * overlap (int): The word overlap size between consecutive chunks.\n"
    "- Returns: list of strings (each representing a text chunk).",
    
    "API Method: retrieve(query, top_k=3)\n"
    "- Description: Processes raw user query via normalization, converts the query text to a TF-IDF vector, calculates cosine similarity metrics against all chunk vectors, and ranks them.\n"
    "- Parameters:\n"
    "  * query (str): Raw input search query from the user.\n"
    "  * top_k (int): Total count of highest-scoring documents to return.\n"
    "- Returns: A tuple of (retrieved_chunks, normalized_query_text) where retrieved_chunks is a list of dictionaries with keys: 'text', 'source', 'score'.",
    
    "API Method: ask(query, top_k=3)\n"
    "- Description: High-level orchestration function. It calls the retrieve method to get relevant context blocks, builds a heavily constrained system prompt enclosing retrieved context, posts the request to the Claude API, and prints a formatted Rich UI Markdown response panel.\n"
    "- Parameters:\n"
    "  * query (str): Raw input query from user.\n"
    "  * top_k (int): Number of source documents used to build the context."
]

def main():
    persona = "a precise technical assistant explaining this library's API to a developer"
    
    # Tuned parameters for code documentation lookup: max_words=60, overlap=10
    bot = RAGEngine(
        documents=API_DOCS,
        persona=persona,
        max_words=60,
        overlap=10,
        title="Code Docs Assistant"
    )
    
    console.clear()
    console.print(Panel.fit("⚡ CODE DOCS ASSISTANT", style="bold blue"))
    console.print("[dim]Developer Mode: Ask questions about chunk_text(), retrieve(), or ask() methods.[/dim]\n")
    
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
