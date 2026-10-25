from django.contrib import admin
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from .models import Bewerbung, Mail, Regel, Shortlist, Stellenanzeige


class BewerbungInline(TabularInline):
    model = Bewerbung
    extra = 0


@admin.register(Regel)
class RegelAdmin(ModelAdmin):
    list_display = ("begriff", "typ", "ziel", "aktiv")
    list_filter = ("typ", "aktiv")
    search_fields = ("begriff",)
    list_editable = ("aktiv",)


@admin.register(Mail)
class MailAdmin(ModelAdmin):
    list_display = ("titel", "firma", "absender", "empfangen_am", "ordner")
    list_filter = ("ordner", "absender")
    search_fields = ("betreff", "titel", "firma", "treffer")
    date_hierarchy = "empfangen_am"
    inlines = [BewerbungInline]
    actions = ["nach_frontend", "nach_vibecoding", "nach_pruefung"]

    @admin.action(description="Nach „Frontend“")
    def nach_frontend(self, request, queryset):
        queryset.update(ordner=Mail.Ordner.FRONTEND)

    @admin.action(description="Nach „VibeCoding“")
    def nach_vibecoding(self, request, queryset):
        queryset.update(ordner=Mail.Ordner.VIBECODING)

    @admin.action(description="Nach „Pruefung“")
    def nach_pruefung(self, request, queryset):
        queryset.update(ordner=Mail.Ordner.PRUEFUNG)


@admin.register(Bewerbung)
class BewerbungAdmin(ModelAdmin):
    list_display = ("mail", "beworben_am", "status")
    list_filter = ("status",)
    date_hierarchy = "beworben_am"


@admin.register(Stellenanzeige)
class StellenanzeigeAdmin(ModelAdmin):
    list_display = ("nr", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "status", "erstellt_am")
    list_filter = ("passung", "kategorie", "status")
    search_fields = ("titel", "firma", "ort", "snippet")
    fieldsets = (
        (None, {"fields": (("nr", "erstellt_am"), "titel", "firma", "ort", "gehalt", "alter_text", "status", "passung", "kategorie",
                           "anzeige_link", "snippet", "daten_lesbar", "seitentext")}),
        ("Rohdaten (JSON)", {"classes": ("collapse",), "fields": ("daten",)}),
        ("Technisches", {"classes": ("collapse",), "fields": ("fehler", "mail", "schluessel")}),
    )
    readonly_fields = ("nr", "daten_lesbar", "anzeige_link", "schluessel", "mail", "erstellt_am")

    @admin.display(description="Auswertung (lesbar)")
    def daten_lesbar(self, obj):
        d = obj.daten or {}
        if not d:
            return "–"

        def ul(items):
            items = [i for i in (items or []) if i]
            return "<ul style='margin:.2rem 0 .2rem 1.2rem;list-style:disc'>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>" if items else ""

        def sec(titel, body):
            return f"<div style='margin:.6rem 0'><strong>{escape(titel)}</strong><div>{body}</div></div>" if body else ""

        def zeile(label, wert):
            return f"<div><span style='opacity:.7'>{escape(label)}:</span> {escape(str(wert))}</div>" if wert else ""

        icon = {"erfuellt": "✅", "teilweise": "🟡", "fehlt": "❌", "unklar": "❔"}
        abgleich = d.get("muss_abgleich") or []
        tab = ""
        if abgleich:
            tab = "<table style='border-collapse:collapse;width:100%'>" + "".join(
                f"<tr><td style='padding:.2rem .5rem;white-space:nowrap'>{icon.get(z.get('status'), '•')} {escape(str(z.get('status', '')))}</td>"
                f"<td style='padding:.2rem .5rem'>{escape(str(z.get('anforderung', '')))}</td>"
                f"<td style='padding:.2rem .5rem;opacity:.7'>{escape(str(z.get('profil_beleg', '')))}</td></tr>"
                for z in abgleich if isinstance(z, dict)
            ) + "</table>"
        html = (
            sec("Passung", zeile("Ergebnis", d.get("passung")) + zeile("Grund", d.get("passung_grund"))
                + zeile("Ausschlussart", d.get("ausschluss_art")) + zeile("Beleg", d.get("ausschluss_beleg")))
            + sec("Eckdaten", zeile("Ort", d.get("ort")) + zeile("Gehalt", d.get("gehalt")) + zeile("Arbeitsmodell", d.get("arbeitsmodell"))
                  + zeile("Anstellung", d.get("anstellungsart")) + zeile("Erfahrung", d.get("erfahrung"))
                  + zeile("Sprachen", ", ".join(d.get("sprachen") or [])) + zeile("Kategorie", d.get("kategorie"))
                  + zeile("Begründung", d.get("begruendung")) + zeile("Datenbasis", d.get("datenbasis")))
            + sec("Muss-Abgleich mit Profil", tab)
            + sec("Muss-Anforderungen", ul(d.get("muss_anforderungen")))
            + sec("Aufgaben", ul(d.get("aufgaben")))
            + sec("Anforderungen", ul(d.get("anforderungen")))
            + sec("Skills", escape(", ".join(d.get("skills") or [])))
            + sec("Bonus", ul(d.get("bonus")))
            + sec("Benefits", ul(d.get("benefits")))
        )
        return mark_safe(html)

    @admin.display(description="Nr.", ordering="id")
    def nr(self, obj):
        return obj.pk

    def get_search_results(self, request, queryset, search_term):
        # Suche nach reiner Zahl = Nummer der Anzeige
        if search_term.strip().isdigit():
            return queryset.filter(pk=int(search_term)), False
        return super().get_search_results(request, queryset, search_term)

    def save_model(self, request, obj, form, change):
        # Volltext von Hand eingefügt -> für die Detail-Auswertung freigeben
        if "seitentext" in form.changed_data and obj.seitentext.strip():
            obj.status = Stellenanzeige.Status.ABGERUFEN
            obj.fehler = ""
        super().save_model(request, obj, form, change)

    @admin.display(description="Anzeige")
    def anzeige_link(self, obj):
        art = "Indeed-Anzeige" if "viewjob" in obj.url else "Werbeanzeige (Tracking-Link)"
        return format_html('<a href="{}" target="_blank" rel="noopener">{} öffnen</a>', obj.url, art)


@admin.register(Shortlist)
class ShortlistAdmin(StellenanzeigeAdmin):
    list_display = ("nr", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "status", "grund", "link")
    list_filter = ("kategorie", "passung", "status")
    ordering = ("passung", "kategorie", "-erstellt_am")
    actions = ["verwerfen", "als_passend"]

    def get_queryset(self, request):
        from django.db.models import Q
        aktiv = [Stellenanzeige.Status.AUSGEWERTET, Stellenanzeige.Status.ABGERUFEN]
        return super().get_queryset(request).filter(status__in=aktiv).filter(
            Q(passung="passt") | (Q(passung__in=["teilweise", "unklar"]) & Q(kategorie__in=["frontend", "vibecoding"]))
        )

    @admin.display(description="Begründung")
    def grund(self, obj):
        d = obj.daten or {}
        return (d.get("passung_grund") or d.get("begruendung") or "")[:140]

    @admin.display(description="Anzeige")
    def link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">öffnen</a>', obj.url)

    @admin.action(description="Verwerfen (Ausschluss)")
    def verwerfen(self, request, queryset):
        queryset.update(passung="ausschluss")

    @admin.action(description="Als „Passt“ markieren")
    def als_passend(self, request, queryset):
        queryset.update(passung="passt")
