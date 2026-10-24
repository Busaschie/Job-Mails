from django.core.management.base import BaseCommand

from jobs.models import Regel

# Aus profil.md abgeleitet ("NICHT im Profil") – im Admin jederzeit änderbar.
AUSSCHLUSS = [
    "SAP", "ABAP", ".NET", "C#", "C++", "Java", "Spring", "Oracle", "Kotlin", "Scala", "Golang", "Rust",
    "Procurement", "Einkauf", "Vertrieb", "Sales", "Buchhalter", "Controller", "Pflege",
    "Praktikum", "Praktikant", "Werkstudent", "Masterarbeit", "Bachelorarbeit", "Ausbildung", "Duales Studium", "Trainee",
]


class Command(BaseCommand):
    help = "Legt Standard-Ausschlussbegriffe an (vorhandene bleiben unverändert)."

    def handle(self, *args, **opt):
        neu = 0
        for b in AUSSCHLUSS:
            _, c = Regel.objects.get_or_create(begriff=b, defaults={"typ": Regel.Typ.NEGATIV})
            neu += c
        self.stdout.write(self.style.SUCCESS(f"{neu} neue Ausschlussregeln angelegt. Im Admin unter 'Regeln' anpassbar."))
