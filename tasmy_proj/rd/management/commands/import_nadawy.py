# rd/management/commands/import_nadawy.py

from django.core.management.base import BaseCommand
from django.db import transaction
from rd.models import Kopalnia, Przenosnik, Nadawa
import pandas as pd
from pathlib import Path


class Command(BaseCommand):
    help = (
        "Importuje dane Nadawa z pliku Excel"
        "Nie usuwa powtórek – tworzy rekord dla każdego wiersza. "
        "Brakujące przenośniki PODAJĄCE z kolumny 'co sypie' tworzy automatycznie."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Ścieżka do pliku .xlsx albo .csv z danymi nadaw."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nie zapisuje do bazy, tylko pokazuje statystyki."
        )

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        if file_path.suffix.lower() == ".csv":
            return pd.read_csv(file_path)
        if file_path.suffix.lower() in [".xlsx", ".xls"]:
            return pd.read_excel(file_path)
        raise ValueError("Obsługiwane są tylko pliki .csv, .xlsx, .xls")

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["file"])
        dry_run = options["dry_run"]

        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"Plik nie istnieje: {file_path}"))
            return

        df = self._read_file(file_path)

        required_cols = {
            "mine",
            "przenosnik_podajacy",
            "przenosnik_odbierajacy",
            "kat_deg",
            "ulozenie",
            "krata_zsypowa",
        }
        missing = required_cols - set(df.columns)
        if missing:
            self.stderr.write(self.style.ERROR(f"Brak kolumn w pliku: {missing}"))
            return

        created = 0
        skipped = 0
        created_sources = 0
        missing_targets = 0

        for idx, row in df.iterrows():
            mine_name = str(row["mine"]).strip()
            src_name = str(row["przenosnik_podajacy"]).strip()
            tgt_name = str(row["przenosnik_odbierajacy"]).strip()

            if not mine_name or mine_name.lower() == "nan":
                skipped += 1
                continue
            if not src_name or src_name.lower() == "nan":
                skipped += 1
                continue
            if not tgt_name or tgt_name.lower() == "nan":
                skipped += 1
                continue

            try:
                kopalnia = Kopalnia.objects.get(nazwa=mine_name)
            except Kopalnia.DoesNotExist:
                self.stderr.write(self.style.WARNING(
                    f"[{idx}] Nie ma kopalni '{mine_name}' w bazie. Pomijam."
                ))
                skipped += 1
                continue

            # PODAJĄCY: jeśli nie istnieje → tworzymy jako źródło referencyjne
            src, was_created_src = Przenosnik.objects.get_or_create(
                kopalnia=kopalnia,
                nazwa=src_name,
                defaults={
                    "oddzial": "źródło_nadawy",  # możesz zmienić lub usunąć
                    "dlugosc_m": None,
                    "transportowany_material": None,
                    "predkosc_tasmy_ms": None,
                    "kat_nachylenia_deg": None,
                    "liczba_nadaw": None,
                    "liczba_odbiorow": None,
                    "pochylniany": False,
                    "liczba_segmentow": None,
                    "data_ostatniego_wydruku": None,
                }
            )
            if was_created_src:
                created_sources += 1

            # ODBIERAJĄCY: musi istnieć w bazie (bo to przenośnik z conveyors_info)
            try:
                tgt = Przenosnik.objects.get(kopalnia=kopalnia, nazwa=tgt_name)
            except Przenosnik.DoesNotExist:
                self.stderr.write(self.style.WARNING(
                    f"[{idx}] Brak przenośnika ODBIERAJĄCEGO '{tgt_name}' w kopalni '{mine_name}'. Pomijam."
                ))
                missing_targets += 1
                skipped += 1
                continue

            # kąt
            kat = row.get("kat_deg", None)
            try:
                kat = float(kat) if pd.notna(kat) else None
            except Exception:
                kat = None

            # ułożenie
            ulozenie = row.get("ulozenie", None)
            ulozenie = str(ulozenie).strip().upper() if pd.notna(ulozenie) else None
            if ulozenie in ["NAN", "NONE", ""]:
                ulozenie = None

            krata = bool(row.get("krata_zsypowa", False))

            if dry_run:
                created += 1
                continue

            # zawsze tworzymy rekord – bez deduplikacji
            Nadawa.objects.create(
                przenosnik_podajacy=src,
                przenosnik_odbierajacy=tgt,
                kat_deg=kat,
                ulozenie=ulozenie,
                krata_zsypowa=krata
            )
            created += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN OK. Rekordów do utworzenia: {created}, "
                f"pominięte: {skipped}, "
                f"utworzone źródła (podające): {created_sources}, "
                f"brakujące odbierające: {missing_targets}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Import zakończony. Utworzone nadawy: {created}, "
                f"pominięte: {skipped}, "
                f"utworzone źródła (podające): {created_sources}, "
                f"brakujące odbierające: {missing_targets}"
            ))
