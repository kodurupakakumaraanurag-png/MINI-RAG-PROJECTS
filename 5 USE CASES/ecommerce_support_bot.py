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

# E-commerce store documents covering product specs, return policies, shipping, and warranty
ECOMMERCE_DOCS = [
    "Product Catalog - Everyday Backpack (BP-102):\n"
    "- Product Name: Everyday Backpack (Model: BP-102).\n"
    "- Price: Rs. 1,999.\n"
    "- Specifications: 22L carrying capacity, features a padded compartment that fits up to a 15-inch laptop.\n"
    "- Available Colors: Charcoal Black, Navy Blue, and Desert Sand.",
    
    "Return and Refund Policy:\n"
    "- We offer a 15-day return policy on all our products.\n"
    "- Items must be in brand-new, unused condition with original packaging intact to be eligible for a full refund."
    "- Return shipping requests must be filed online within the 15-day window from the date of delivery.",
    
    "Shipping and Delivery Policy:\n"
    "- Standard delivery takes between 4 to 6 business days for delivery to most locations.\n"
    "- A flat shipping fee of Rs. 49 is charged for standard delivery on orders."
    "- Orders are dispatched within 24 hours of placement.",
    
    "Warranty Terms:\n"
    "- The Everyday Backpack (BP-102) includes a 1-year product warranty.\n"
    "- The warranty specifically covers defects in materials or workmanship on zippers and stitching.\n"
    "- It does not cover general wear and tear, tears from overload, or accidental damages."
]

def main():
    persona = "a polite customer support agent for an online backpack store"
    
    bot = RAGEngine(
        documents=ECOMMERCE_DOCS,
        persona=persona,
        max_words=80,
        overlap=15,
        title="Store Support"
    )
    
    console.clear()
    console.print(Panel.fit("🛍️ E-COMMERCE SUPPORT BOT", style="bold magenta"))
    console.print("[dim]Customer Support Active: Ask about the Everyday Backpack (BP-102), returns, delivery, or warranty.[/dim]\n")
    
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
