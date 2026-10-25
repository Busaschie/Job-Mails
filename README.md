# Job-Mails

Django-Projekt, das Job-Alert-Mails von Indeed, StepStone und Jobware aus einem IMAP-Postfach liest, die einzelnen Stellen extrahiert, mit einem LLM gegen das eigene Profil bewertet und in einem Admin-Dashboard (django-unfold) als **Shortlist** aufbereitet. Bewerbungen und ihr Status werden im selben System verfolgt.

## Ablauf (Pipeline)

```
IMAP-Postfach ──scan_mails──▶ Ordner …/Indeed
                  │
            parse_mails ──▶ einzelne Stellenanzeigen (ohne Duplikate, PostgreSQL)
                  │
            extract_jobs ──▶ Titel-Regeln (Ausschlussbegriffe) → LLM: Daten, Passung, Kategorie
                  │
              Admin: Shortlist (Score), Bewerbungen, Dashboard, Pipeline-Läufe
```

1. **`scan_mails`** holt Mails mit „indeed“ im Absender aus `IMAP_FOLDER` und verschiebt sie nach `<IMAP_BASE_FOLDER>/Indeed`.
2. **`parse_mails`** liest die Mails im Ordner `Indeed`, zerlegt sie in einzelne Jobs (Titel, Firma, Ort, Gehalt, Kurztext, Link). Duplikate werden über die Indeed-ID (`jk`) bzw. einen Hash erkannt.
3. **`extract_jobs`** bewertet jede Anzeige: erst Ausschlussbegriffe im Titel (`Regel`), dann das LLM mit dem Profil aus `profil.md`. Ergebnis: strukturiertes JSON, `passung` (passt / teilweise / unklar / ausschluss) und `kategorie` (frontend / vibecoding / pruefung).
4. **`run_pipeline`** führt die drei Schritte nacheinander aus, schützt sich per Sperrdatei vor Doppelläufen und protokolliert jeden Lauf im Admin.

## Voraussetzungen

- Python 3.12+ (entwickelt mit 3.14), Docker (PostgreSQL), optional Ollama (lokales LLM)
- IMAP-Postfach mit den Ordnern `Verwaltung/Bewerbung/Indeed`, `…/Frontend`, `…/VibeCoding`, `…/Pruefung`

## Einrichtung

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env        # dann Werte eintragen (siehe unten)
docker compose up -d          # PostgreSQL auf DB_PORT (Standard 5433)

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_regeln  # Standard-Ausschlussbegriffe, danach im Admin anpassen
python manage.py runserver
```

Admin: <http://localhost:8000/admin/>

### `.env`

| Schlüssel | Bedeutung |
|---|---|
| `IMAP_HOST`, `IMAP_PORT`, `IMAP_SSL`, `IMAP_USER`, `IMAP_PASSWORD` | Zugang zum Postfach |
| `IMAP_FOLDER` | Quellordner mit den Indeed-Mails (z. B. `INBOX`) |
| `IMAP_BASE_FOLDER` | Basisordner für die Zielordner (Standard `Verwaltung/Bewerbung`) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL (wird von `docker-compose.yml` mitgenutzt) |
| `LLM_PROVIDER` | `ollama`, `groq` oder `anthropic` |
| `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` | lokales Modell |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq (z. B. `openai/gpt-oss-120b`) |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude (API-Guthaben nötig, getrennt vom Abo) |

Die `.env` und `profil.md` liegen **nicht** im Git-Repository (siehe `.gitignore`).

### `profil.md`

Berufsrelevantes Bewerberprofil, das dem LLM bei der Bewertung mitgegeben wird: Skills, Erfahrung, „nicht im Profil“, „kein Ausschlussgrund“ und Wünsche. Nach inhaltlichen Änderungen `PROMPT_VERSION` in `jobs/management/commands/extract_jobs.py` erhöhen und neu bewerten (siehe unten).

## Befehle

| Befehl | Zweck |
|---|---|
| `python manage.py run_pipeline [--limit 40]` | kompletter Lauf (scan → parse → extract) |
| `python manage.py scan_mails [--dry-run]` | Mails sortieren (`--dry-run` verschiebt nichts) |
| `python manage.py parse_mails [--all]` | Anzeigen aus den Mails im Ordner `Indeed` lesen |
| `python manage.py extract_jobs --aus-mail --limit 300` | neue Anzeigen aus dem Kurztext bewerten |
| `python manage.py extract_jobs --aus-mail --veraltet --retry --limit 300` | alle mit altem Prompt bzw. Fehler neu bewerten |
| `python manage.py extract_jobs --id 248` | genau eine Anzeige (Nr. aus dem Admin) |
| `python manage.py extract_jobs --suche Firma --alle` | Anzeigen nach Titel/Firma neu bewerten |
| `python manage.py seed_regeln` | Standard-Ausschlussbegriffe anlegen |
| `python manage.py ba_check --limit 20` | Überschneidung mit der Jobbörse der Bundesagentur prüfen (nur Anzeige) |

Bei einem LLM-Tageslimit (Groq) bricht `extract_jobs` selbst ab; fertige Anzeigen bleiben gespeichert, später mit demselben Befehl fortsetzen.

## Admin-Bereiche

- **Dashboard:** Shortlist-Größe, neue Mails/Anzeigen (24 h), Kategorien, Passung, Mails pro Ordner, Pipeline-Läufe, Bewerbungen.
- **Shortlist:** passende Anzeigen nach **Score** sortiert (Passung, Wunsch-Kategorie, Aktualität, Gehalt; Beworbene ans Ende). Aktionen: *Als beworben markieren*, *Verwerfen*, *Als „Passt“ markieren*.
- **Stellenanzeigen:** alle Anzeigen mit lesbarer Auswertung, Bewerbungsfeldern (Datum, Status, Notizen), Roh-JSON (eingeklappt) und Suche per Nummer.
- **Regeln:** Ausschlussbegriffe (Ganzwort-Treffer im Titel, z. B. `SAP`, `Java` – nicht `JavaScript`).
- **Pipeline-Läufe:** Protokoll der automatischen Läufe.

## Volltext per Lesezeichen

Indeed blockiert automatisierte Seitenabrufe, und das Skript umgeht den Bot-Schutz bewusst nicht. Für Details einzelner Anzeigen:

1. `http://localhost:8000/import/` öffnen (als Admin angemeldet) und den Button *Job-Text übernehmen* in die Lesezeichenleiste ziehen.
2. Anzeige auf Indeed selbst öffnen, Lesezeichen klicken – der Text wird lokal gespeichert, die Seite bietet die nächste Anzeige an.
3. `extract_jobs` (ohne `--aus-mail`) wertet die Anzeige mit dem Volltext aus (inkl. Muss-Abgleich).

## Automatischer Lauf (Windows Task Scheduler)

`run_pipeline.bat` startet `run_pipeline` und schreibt in `pipeline.log` (Start, Ausgabe, Ende mit Exit-Code).

Aufgabe z. B. mit:

```powershell
schtasks /Create /TN "Job-Mails Pipeline" /TR "<Pfad>\programm\run_pipeline.bat" /SC DAILY /ST 07:00 /RI 180 /DU 12:00
```

(07, 10, 13, 16 und 19 Uhr). Voraussetzung: Rechner läuft, Docker (PostgreSQL) und – bei `LLM_PROVIDER=ollama` – Ollama sind gestartet. In der Aufgabenplanung ggf. „Verlauf für alle Aufgaben aktivieren“.

## Projektstruktur

```
programm/            Django-Projekt (settings, urls)
jobs/                App: Models, Admin, Dashboard, Shortlist, Import-Seite
  indeed.py          Parser für Indeed-Alert-Mails
  llm.py             LLM-Anbieter (ollama | groq | anthropic)
  shortlist.py       Shortlist-Filter und Score
  management/commands/   scan_mails, parse_mails, extract_jobs, run_pipeline, …
templates/admin/     Dashboard-Template (django-unfold)
docker-compose.yml   PostgreSQL
run_pipeline.bat     Einstieg für den Task Scheduler
```

## Fehlersuche

- **Alle Anzeigen „Fehler“ nach LLM-Ausfall:** `extract_jobs --aus-mail --retry` wiederholt sie.
- **`password authentication failed` / falscher Port:** `docker compose down -v`, `docker compose up -d`; läuft schon ein Postgres auf 5432, `DB_PORT=5433` nutzen.
- **Ordner nicht gefunden:** Zielordner im Postfach anlegen (`…/Indeed`, `…/Frontend`, `…/VibeCoding`, `…/Pruefung`), IMAP-Namen exakt wie im Server.
- **Umlaute/`charmap` im Log:** Die `.bat` setzt `PYTHONUTF8=1`; bei manuellem Start ebenfalls setzen.
- **Pipeline läuft nicht an:** Aufgabenplanung → Letzte Laufzeit/Ergebnis prüfen, `pipeline.log` lesen, ggf. veraltete `.pipeline.lock` löschen.

## Hinweise

- Das LLM bewertet nur nach dem Kurztext aus der Mail (Titel, Firma, Ort, Gehalt, Kurztext), solange kein Volltext gespeichert ist; die Passung ist dann ein Hinweis, kein endgültiges Urteil.
- Bei Cloud-LLMs (Groq, Claude) gehen Anzeigentext und das berufsbezogene Profil an den jeweiligen Anbieter; bei Ollama bleibt alles lokal.
