from django.core.management.base import BaseCommand

from jobs.models import Regel

# Aus profil.md abgeleitet ("NICHT im Profil") – im Admin jederzeit änderbar.
AUSSCHLUSS = [
    "SAP", "ABAP", ".NET", "C#", "C++", "Java", "Spring", "Oracle", "Kotlin", "Scala", "Golang", "Rust",
    "Procurement", "Einkauf", "Vertrieb", "Sales", "Buchhalter", "Controller", "Pflege",
    "Praktikum", "Praktikant", "Werkstudent", "Masterarbeit", "Bachelorarbeit", "Ausbildung", "Duales Studium", "Trainee",
]

# Positive Regeln: Stichwort in Titel/Kurztext -> Kategorie (Fallback in extract_jobs)
POSITIV = {
    "frontend": ["Frontend", "Front-End", "Front End", "Webentwickler", "Web Developer", "Webdesigner", "JavaScript", "TypeScript",
                 "React", "Vue", "Angular", "HTML", "CSS", "UX", "UI"],
    "vibecoding": ["Vibe Coding", "Vibe-Coding", "Vibecoding", "KI-Orchestrator", "KI Orchestrator", "AI Orchestrator",
                   "KI-Entwickler", "KI Entwickler", "AI Engineer", "Prompt Engineer", "LLM", "Automatisierung", "n8n", "Agentic"],
}


class Command(BaseCommand):
    help = "Legt Standard-Ausschlussbegriffe an (vorhandene bleiben unverändert)."

    def handle(self, *args, **opt):
        neu = 0
        for b in AUSSCHLUSS:
            _, c = Regel.objects.get_or_create(begriff=b, defaults={"typ": Regel.Typ.NEGATIV})
            neu += c
        pos = 0
        for ziel, begriffe in POSITIV.items():
            for b in begriffe:
                _, c = Regel.objects.get_or_create(begriff=b, defaults={"typ": Regel.Typ.POSITIV, "ziel": ziel})
                pos += c
        self.stdout.write(f"{pos} neue positive Regeln angelegt.")
        self.stdout.write(self.style.SUCCESS(f"{neu} neue Ausschlussregeln angelegt. Im Admin unter 'Regeln' anpassbar."))
