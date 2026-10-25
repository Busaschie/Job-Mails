from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import admin
from django.utils.timezone import localtime
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from .models import Bewerbung, Mail, PipelineLauf, Regel, Shortlist, Stellenanzeige
from .shortlist import mit_score, shortlist_basis


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
    list_display = ("anzeige", "firma", "beworben_am", "status")
    list_filter = ("status",)
    date_hierarchy = "beworben_am"
    fieldsets = (
        ("Bewerbung", {"fields": ("anzeige", "beworben_am", "status", "notizen")}),
        ("Stellenanzeige", {"fields": ("a_titel", "a_firma", "a_ort", "a_gehalt", "a_passung", "a_link", "a_auswertung")}),
    )
    readonly_fields = ("a_titel", "a_firma", "a_ort", "a_gehalt", "a_passung", "a_link", "a_auswertung")

    @admin.display(description="Titel")
    def a_titel(self, obj):
        return obj.anzeige.titel if obj.pk else ""

    @admin.display(description="Firma")
    def a_firma(self, obj):
        return obj.anzeige.firma if obj.pk else ""

    @admin.display(description="Ort")
    def a_ort(self, obj):
        return obj.anzeige.ort if obj.pk else ""

    @admin.display(description="Gehalt")
    def a_gehalt(self, obj):
        return obj.anzeige.gehalt if obj.pk else ""

    @admin.display(description="Passung / Kategorie")
    def a_passung(self, obj):
        return f"{obj.anzeige.get_passung_display()} / {obj.anzeige.kategorie}" if obj.pk else ""

    @admin.display(description="Anzeige")
    def a_link(self, obj):
        return StellenanzeigeAdmin.anzeige_link(self, obj.anzeige) if obj.pk else ""

    @admin.display(description="Auswertung (lesbar)")
    def a_auswertung(self, obj):
        return StellenanzeigeAdmin.daten_lesbar(self, obj.anzeige) if obj.pk else ""


    @admin.display(description="Firma")
    def firma(self, obj):
        return obj.anzeige.firma if obj.anzeige else ""


class StellenanzeigeForm(forms.ModelForm):
    """Bewerbungsfelder direkt im Formular der Anzeige (statt Inline unten)."""
    beworben_am = forms.DateField(required=False, label="Beworben am",
                                  widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    bewerbung_status = forms.ChoiceField(required=False, label="Bewerbungsstatus",
                                         choices=[("", "— keine Bewerbung —")] + list(Bewerbung.Status.choices))
    bewerbung_notizen = forms.CharField(required=False, label="Notizen zur Bewerbung",
                                        widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = Stellenanzeige
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        b = getattr(self.instance, "bewerbung", None) if self.instance.pk else None
        if b:
            self.fields["beworben_am"].initial = b.beworben_am
            self.fields["bewerbung_status"].initial = b.status
            self.fields["bewerbung_notizen"].initial = b.notizen


@admin.register(Stellenanzeige)
class StellenanzeigeAdmin(ModelAdmin):
    form = StellenanzeigeForm
    list_display = ("nr", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "status", "beworben", "erstellt_am")
    list_filter = ("quelle", "passung", "kategorie", "status")
    search_fields = ("titel", "firma", "ort", "snippet")
    fieldsets = (
        (None, {"fields": ("kopfzeile", "portal", "titel", "firma", "ort", "gehalt", "alter_text", "status", "passung", "kategorie",
                           "anzeige_link", "snippet", "daten_lesbar", "seitentext")}),
        ("Bewerbung", {"fields": ("beworben_am", "bewerbung_status", "bewerbung_notizen")}),
        ("Rohdaten (JSON)", {"classes": ("collapse",), "fields": ("daten",)}),
        ("Technisches", {"classes": ("collapse",), "fields": ("fehler", "mail", "schluessel", "duplikat_von")}),
    )
    readonly_fields = ("nr", "kopfzeile", "portal", "daten_lesbar", "anzeige_link", "schluessel", "mail", "erstellt_am", "duplikat_von")

    @admin.display(description="Beworben")
    def beworben(self, obj):
        b = getattr(obj, "bewerbung", None)
        return f"{b.get_status_display()} ({b.beworben_am:%d.%m.%Y})" if b and b.beworben_am else (b.get_status_display() if b else "")

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

    @admin.display(description="Nr. / Erstellt am")
    def kopfzeile(self, obj):
        if not obj.pk:
            return "–"
        return format_html('<span style="display:inline-flex;gap:3rem;flex-wrap:wrap"><span><strong>{}</strong></span><span>{}</span></span>',
                           obj.pk, localtime(obj.erstellt_am).strftime("%d.%m.%Y %H:%M"))

    @admin.display(description="Jobportal")
    def portal(self, obj):
        return obj.get_quelle_display() if obj.pk else "–"

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
        cd = form.cleaned_data
        datum, status, notizen = cd.get("beworben_am"), cd.get("bewerbung_status"), cd.get("bewerbung_notizen", "")
        if datum or status or notizen:
            b, _ = Bewerbung.objects.get_or_create(anzeige_id=obj.pk)
            b.beworben_am, b.notizen = datum, notizen
            b.status = status or b.status or Bewerbung.Status.GESENDET
            b.save()
        else:
            Bewerbung.objects.filter(anzeige_id=obj.pk).delete()

    @admin.display(description="Anzeige")
    def anzeige_link(self, obj):
        if obj.quelle == "indeed":
            art = "Indeed-Anzeige" if "viewjob" in obj.url else "Indeed-Werbeanzeige (Tracking-Link)"
        else:
            art = f"{obj.get_quelle_display()}-Anzeige"
        return format_html('<a href="{}" target="_blank" rel="noopener">{} öffnen</a>', obj.url, art)


@admin.register(Shortlist)
class ShortlistAdmin(StellenanzeigeAdmin):
    list_display = ("nr", "punkte", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "beworben", "grund", "link")
    list_filter = ("quelle", "kategorie", "passung", "status")
    actions = ["als_beworben", "verwerfen", "als_passend"]

    def get_ordering(self, request):
        return ["-score", "-erstellt_am"]  # Methode statt Attribut: score ist annotiert, kein Modellfeld

    def get_queryset(self, request):
        return mit_score(shortlist_basis(Shortlist._default_manager.all()))

    @admin.display(description="Score", ordering="score")
    def punkte(self, obj):
        return obj.score

    @admin.display(description="Begründung")
    def grund(self, obj):
        d = obj.daten or {}
        return (d.get("passung_grund") or d.get("begruendung") or "")[:140]

    @admin.display(description="Anzeige")
    def link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">öffnen</a>', obj.url)

    @admin.action(description="Als beworben markieren (heute)")
    def als_beworben(self, request, queryset):
        from datetime import date
        neu = 0
        for a in queryset:
            _, c = Bewerbung.objects.get_or_create(
                anzeige_id=a.pk, defaults={"beworben_am": date.today(), "status": Bewerbung.Status.GESENDET})
            neu += c
        self.message_user(request, f"{neu} Bewerbung(en) angelegt ({queryset.count() - neu} bestanden bereits).")

    @admin.action(description="Verwerfen (Ausschluss)")
    def verwerfen(self, request, queryset):
        queryset.update(passung="ausschluss")

    @admin.action(description="Als „Passt“ markieren")
    def als_passend(self, request, queryset):
        queryset.update(passung="passt")


@admin.register(PipelineLauf)
class PipelineLaufAdmin(ModelAdmin):
    list_display = ("gestartet", "beendet", "status", "mails_neu", "anzeigen_neu", "ausgewertet", "fehler")
    list_filter = ("status",)
    readonly_fields = [f.name for f in PipelineLauf._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
