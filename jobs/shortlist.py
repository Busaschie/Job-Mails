"""Gemeinsame Logik für Shortlist (Admin) und Dashboard."""
from datetime import timedelta

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

WUNSCH = ["frontend", "vibecoding"]


def shortlist_basis(qs):
    """Passt immer; Teilweise/Unklar nur bei Wunsch-Kategorie (Frontend/VibeCoding)."""
    return qs.filter(duplikat_von__isnull=True, status__in=["ausgewertet", "abgerufen"]).filter(
        Q(passung="passt") | (Q(passung__in=["teilweise", "unklar"]) & Q(kategorie__in=WUNSCH))
    )


def _punkte(*whens):
    return Case(*whens, default=Value(0), output_field=IntegerField())


def mit_score(qs):
    """Score: Passung (max 50) + Wunsch-Kategorie (30) + Aktualität (max 15) + Gehalt genannt (5); beworben ans Ende."""
    jetzt = timezone.now()
    return qs.annotate(
        score=(
            _punkte(When(passung="passt", then=Value(50)), When(passung="teilweise", then=Value(25)),
                    When(passung="unklar", then=Value(10)))
            + _punkte(When(kategorie__in=WUNSCH, then=Value(30)))
            + _punkte(When(~Q(gehalt=""), then=Value(5)))
            + _punkte(When(erstellt_am__gte=jetzt - timedelta(days=7), then=Value(15)),
                      When(erstellt_am__gte=jetzt - timedelta(days=14), then=Value(8)))
            + _punkte(When(bewerbung__isnull=False, then=Value(-1000)))
        )
    )
