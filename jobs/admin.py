from django.contrib import admin
from django.utils.html import format_html
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
    list_display = ("titel", "firma", "ort", "gehalt", "passung", "kategorie", "status", "erstellt_am")
    list_filter = ("passung", "kategorie", "status")
    search_fields = ("titel", "firma", "ort", "snippet")
    fields = ("titel", "firma", "ort", "gehalt", "alter_text", "status", "passung", "kategorie", "anzeige_link",
              "snippet", "daten", "seitentext", "fehler", "mail", "schluessel", "erstellt_am")
    readonly_fields = ("anzeige_link", "schluessel", "mail", "erstellt_am")

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
    list_display = ("titel", "firma", "ort", "gehalt", "passung", "kategorie", "status", "grund", "link")
    list_filter = ("kategorie", "passung", "status")
    ordering = ("passung", "kategorie", "-erstellt_am")
    actions = ["verwerfen", "als_passend"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            passung__in=["passt", "teilweise", "unklar"],
            status__in=[Stellenanzeige.Status.AUSGEWERTET, Stellenanzeige.Status.ABGERUFEN],
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
