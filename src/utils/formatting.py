import random
from typing import Optional
from rich.console import Console
from rich.panel import Panel

console = Console()

RABBIT_ART = (
    "  (\\_/)\n"
    "  (o-o)   <-- Dr. Hops 👓\n"
    " c( 🔬)o"
)

BIOTECH_INTERJECTIONS = [
    "By my ribosomes!",
    "Spliceosome alert!",
    "Great transcription factors!",
    "Sacred double helix!",
    "Holy polymerase chain reaction!",
    "My nucleotides are tingling!",
    "By the power of CRISPR-Cas9!",
    "RNA transcription initiated!",
    "Fascinating phenotype!",
    "Let's optimize this enzyme kinetics!",
    "According to my sequencing alignment!",
    "By the cellular membranes!",
    "Mitochondrial surge detected!",
    "By my telomeres!",
]


def get_random_interjection() -> str:
    return random.choice(BIOTECH_INTERJECTIONS)


def speak(text: str, title: str = "Dr. Hops", include_interjection: bool = True):
    """Output a message from Dr. Hops, the nerdy biotech rabbit, with custom speech bubbles."""
    interjection = f"{get_random_interjection()} " if include_interjection else ""
    full_message = f"{interjection}{text}"
    
    # Render rich speech bubble
    speech_panel = Panel(
        full_message,
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        expand=False,
    )
    
    console.print()
    console.print(RABBIT_ART)
    console.print(speech_panel)
    console.print()


def print_success(text: str):
    console.print(f"[bold green]✔ SUCCESS:[/bold green] {text}")


def print_error(text: str):
    console.print(f"[bold red]✘ ERROR:[/bold red] {text}")


def print_warning(text: str):
    console.print(f"[bold yellow]⚠ WARNING:[/bold yellow] {text}")


def print_info(text: str):
    console.print(f"[bold blue]ℹ INFO:[/bold blue] {text}")
