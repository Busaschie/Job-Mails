from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import admin
from django.utils.timezone import localtime
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from unfold.widgets import INPUT_CLASSES, UnfoldAdminSelectWidget, UnfoldAdminTextareaWidget

from .models import Archiv, Bewerbung, BewerbungEreignis, Mail, PipelineLauf, Regel, Shortlist, Stellenanzeige
from . import anschreiben as anschreiben_mod
from .bewerbung import buche, verlauf_html
from .llm import RateLimitError
from .dashboard import NACHFASS_TAGE
from .shortlist import aktuell, archiv, mit_score, shortlist_basis


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


class StatusDatumWidget(forms.MultiWidget):
    """Status-Dropdown und Datum nebeneinander in einer Zeile."""

    def __init__(self, choices, attrs=None):
        super().__init__(
            [UnfoldAdminSelectWidget(choices=choices),
             forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "title": "Datum der Änderung (leer = heute)",
                                                       "class": " ".join(INPUT_CLASSES)})], attrs)

    def decompress(self, value):
        return list(value) if value else [None, None]

    def render(self, name, value, attrs=None, renderer=None):
        # Jedes Teil in eigenem Rahmen mit fester Breite (der Pfeil des Unfold-Selects haengt am Rahmen)
        ctx = self.get_context(name, value, attrs)
        teile = [self._render(w["template_name"], {"widget": w}, renderer) for w in ctx["widget"]["subwidgets"]]
        breiten = ("15rem", "11rem")
        html = "".join(f"<div style='width:{b}'>{t}</div>" for b, t in zip(breiten, teile))
        return mark_safe(f"<div style='display:flex;gap:.75rem;align-items:flex-start'>{html}</div>")


class StatusDatumField(forms.MultiValueField):
    """Liefert (status, datum)."""

    def __init__(self, choices, **kwargs):
        super().__init__(fields=(forms.ChoiceField(choices=choices, required=False), forms.DateField(required=False)),
                         widget=StatusDatumWidget(choices), require_all_fields=False, required=False, **kwargs)

    def compress(self, data_list):
        return tuple(data_list) if data_list else ("", None)


@admin.register(BewerbungEreignis)
class BewerbungEreignisAdmin(ModelAdmin):
    """Einzelner Verlaufseintrag (Link 'bearbeiten' im Verlauf); nach dem Speichern zurueck zur Anzeige."""
    fields = ("bewerbung", "datum", "status", "notiz")
    readonly_fields = ("bewerbung",)

    def has_module_permission(self, request):
        return False  # nicht in der Navigation

    def _zurueck(self, obj):
        return HttpResponseRedirect(reverse("admin:jobs_stellenanzeige_change", args=[obj.bewerbung.anzeige_id]))

    def response_change(self, request, obj):
        return self._zurueck(obj)

    def response_delete(self, request, obj_display, obj_id):
        anz = request.session.pop("_ereignis_anzeige", None)
        return HttpResponseRedirect(reverse("admin:jobs_stellenanzeige_change", args=[anz])) if anz else super().response_delete(request, obj_display, obj_id)

    def delete_model(self, request, obj):
        request.session["_ereignis_anzeige"] = obj.bewerbung.anzeige_id
        super().delete_model(request, obj)


class BewerbungForm(forms.ModelForm):
    status_kombi = StatusDatumField(list(Bewerbung.Status.choices), label="Status / Datum")
    notiz_neu = forms.CharField(required=False, label="Neue Notiz (wird mit Datum im Verlauf abgelegt)",
                                widget=UnfoldAdminTextareaWidget(attrs={"rows": 3, "style": "max-width:42rem"}))

    class Meta:
        model = Bewerbung
        fields = ("anzeige", "beworben_am")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status_kombi"].initial = (self.instance.status if self.instance.pk else Bewerbung.Status.GESENDET, None)


@admin.register(Bewerbung)
class BewerbungAdmin(ModelAdmin):
    form = BewerbungForm
    list_display = ("anzeige", "firma", "beworben_am", "status", "seit")
    list_filter = ("status",)
    date_hierarchy = "beworben_am"
    fieldsets = (
        ("Bewerbung", {"fields": ("anzeige", "beworben_am", "status_kombi", "notiz_neu", "verlauf")}),
        ("Stellenanzeige", {"fields": ("a_titel", "a_firma", "a_ort", "a_gehalt", "a_passung", "a_link", "a_auswertung")}),
    )
    readonly_fields = ("verlauf", "a_titel", "a_firma", "a_ort", "a_gehalt", "a_passung", "a_link", "a_auswertung")

    @admin.display(description="Verlauf")
    def verlauf(self, obj):
        return verlauf_html(obj)

    def save_model(self, request, obj, form, change):
        alt = Bewerbung.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if obj.pk else None
        status, datum = form.cleaned_data.get("status_kombi") or ("", None)
        obj.status = status or obj.status or Bewerbung.Status.GESENDET
        super().save_model(request, obj, form, change)
        buche(obj, alt, datum or (obj.beworben_am if alt is None else None), form.cleaned_data.get("notiz_neu", ""))

    @admin.display(description="Seit")
    def seit(self, obj):
        if not obj.beworben_am:
            return ""
        from datetime import date
        n = (date.today() - obj.beworben_am).days
        warn = " ⚠ nachfassen" if obj.status == Bewerbung.Status.GESENDET and n >= NACHFASS_TAGE else ""
        return f"{n} Tage{warn}"

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
    bewerbung_status = StatusDatumField([("", "— keine Bewerbung —")] + list(Bewerbung.Status.choices), label="Bewerbungsstatus / Datum")
    bewerbung_notizen = forms.CharField(required=False, label="Neue Notiz (wird mit Datum im Verlauf abgelegt)",
                                        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3, "style": "max-width:42rem"}))

    class Meta:
        model = Stellenanzeige
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        b = getattr(self.instance, "bewerbung", None) if self.instance.pk else None
        if b:
            self.fields["beworben_am"].initial = b.beworben_am
            self.fields["bewerbung_status"].initial = (b.status, None)


@admin.register(Stellenanzeige)
class StellenanzeigeAdmin(ModelAdmin):
    form = StellenanzeigeForm
    list_display = ("nr", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "interessant", "status", "beworben", "erstellt_am")
    list_filter = ("interessant", "quelle", "passung", "kategorie", "status")
    actions = ["als_interessant", "nicht_interessant", "anschreiben_erstellen"]
    search_fields = ("titel", "firma", "ort", "snippet")
    fieldsets = (
        (None, {"fields": ("kopfzeile", "portal", "titel", "firma", "ort", "gehalt", "alter_text", "status", "passung", "kategorie", "interessant",
                           "anzeige_link", "snippet", "daten_lesbar", "seitentext")}),
        ("Bewerbung", {"fields": ("beworben_am", "bewerbung_status", "bewerbung_notizen", "bewerbung_verlauf")}),
        ("Anschreiben (Entwurf)", {"fields": ("anschreiben",)}),
        ("Rohdaten (JSON)", {"classes": ("collapse",), "fields": ("daten",)}),
        ("Technisches", {"classes": ("collapse",), "fields": ("fehler", "mail", "schluessel", "duplikat_von")}),
    )
    readonly_fields = ("bewerbung_verlauf", "nr", "kopfzeile", "portal", "daten_lesbar", "anzeige_link", "schluessel", "mail", "erstellt_am", "duplikat_von")

    def get_queryset(self, request):
        return aktuell(super().get_queryset(request))  # aeltere (>4 Wochen) liegen im Archiv

    @admin.action(description="Als interessant markieren")
    def als_interessant(self, request, queryset):
        n = Stellenanzeige.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).update(interessant=True)
        self.message_user(request, f"{n} Anzeige(n) als interessant markiert.")

    @admin.action(description="Markierung 'interessant' entfernen")
    def nicht_interessant(self, request, queryset):
        n = Stellenanzeige.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).update(interessant=False)
        self.message_user(request, f"{n} Markierung(en) entfernt.")

    @admin.action(description="Anschreiben-Entwurf erstellen (max. 5)")
    def anschreiben_erstellen(self, request, queryset):
        fertig = 0
        for a in Stellenanzeige.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))[:5]):
            try:
                a.anschreiben = anschreiben_mod.erstelle(a)
            except RateLimitError as e:
                self.message_user(request, f"Abbruch (Limit): {e}", level="error")
                break
            except Exception as e:
                self.message_user(request, f"{a.pk}: {str(e)[:200]}", level="error")
                continue
            a.save(update_fields=["anschreiben"])
            fertig += 1
        self.message_user(request, f"{fertig} Entwurf/Entwürfe erstellt - in der Anzeige unter 'Anschreiben (Entwurf)'.")

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
        status, status_datum = cd.get("bewerbung_status") or ("", None)
        datum, notizen = cd.get("beworben_am"), cd.get("bewerbung_notizen", "")
        if datum or status or notizen:
            b, neu = Bewerbung.objects.get_or_create(anzeige_id=obj.pk)
            alt = None if neu else b.status
            b.beworben_am = datum
            b.status = status or b.status or Bewerbung.Status.GESENDET
            b.save()
            buche(b, alt, status_datum or (datum if neu else None), notizen)
        else:
            Bewerbung.objects.filter(anzeige_id=obj.pk).delete()

    @admin.display(description="Verlauf")
    def bewerbung_verlauf(self, obj):
        return verlauf_html(getattr(obj, "bewerbung", None) if obj.pk else None)

    @admin.display(description="Anzeige")
    def anzeige_link(self, obj):
        if obj.quelle == "indeed":
            art = "Indeed-Anzeige" if "viewjob" in obj.url else "Indeed-Werbeanzeige (Tracking-Link)"
        else:
            art = f"{obj.get_quelle_display()}-Anzeige"
        return format_html('<a href="{}" target="_blank" rel="noopener">{} öffnen</a>', obj.url, art)


@admin.register(Shortlist)
class ShortlistAdmin(StellenanzeigeAdmin):
    list_display = ("nr", "punkte", "titel", "firma", "ort", "gehalt", "passung", "kategorie", "interessant", "beworben", "grund", "link")
    list_filter = ("interessant", "quelle", "kategorie", "passung", "status")
    actions = ["als_interessant", "nicht_interessant", "anschreiben_erstellen", "als_beworben", "verwerfen", "als_passend"]

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
            b, c = Bewerbung.objects.get_or_create(
                anzeige_id=a.pk, defaults={"beworben_am": date.today(), "status": Bewerbung.Status.GESENDET})
            if c:
                buche(b, None, b.beworben_am)
            neu += c
        self.message_user(request, f"{neu} Bewerbung(en) angelegt ({queryset.count() - neu} bestanden bereits).")

    @admin.action(description="Verwerfen (Ausschluss)")
    def verwerfen(self, request, queryset):
        queryset.update(passung="ausschluss")

    @admin.action(description="Als „Passt“ markieren")
    def als_passend(self, request, queryset):
        queryset.update(passung="passt")


@admin.register(Archiv)
class ArchivAdmin(StellenanzeigeAdmin):
    list_filter = ("quelle", "passung", "kategorie")

    def get_queryset(self, request):
        return archiv(ModelAdmin.get_queryset(self, request))


@admin.register(PipelineLauf)
class PipelineLaufAdmin(ModelAdmin):
    list_display = ("gestartet", "beendet", "status", "mails_neu", "anzeigen_neu", "ausgewertet", "fehler")
    list_filter = ("status",)
    readonly_fields = [f.name for f in PipelineLauf._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
