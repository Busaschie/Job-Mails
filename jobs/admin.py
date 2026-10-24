from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Bewerbung, Mail, Regel


class BewerbungInline(TabularInline):
    model = Bewerbung
    extra = 0


@admin.register(Regel)
class RegelAdmin(ModelAdmin):
    list_display = ("begriff", "typ", "aktiv")
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
    actions = ["als_passend", "zur_pruefung"]

    @admin.action(description="Als „Kommt in Frage“ markieren")
    def als_passend(self, request, queryset):
        queryset.update(ordner=Mail.Ordner.PASSEND)

    @admin.action(description="In „Zur Überprüfung“ verschieben")
    def zur_pruefung(self, request, queryset):
        queryset.update(ordner=Mail.Ordner.PRUEFEN)


@admin.register(Bewerbung)
class BewerbungAdmin(ModelAdmin):
    list_display = ("mail", "beworben_am", "status")
    list_filter = ("status",)
    date_hierarchy = "beworben_am"
