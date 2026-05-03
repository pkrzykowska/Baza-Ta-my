import pandas as pd
from django.core.management.base import BaseCommand

from rd.models import Kopalnia, Przenosnik


def clean_decimal(value):
    """Na potrzeby importu: zamienia '-', '', NaN na None, resztę na float."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s in ["", "-", "–"]:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def clean_int(value):
    """Na potrzeby importu: zamienia '-', '', NaN na None/int."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s in ["", "-", "–"]:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def clean_bool(value):
    if pd.isna(value):
        return False
    s = str(value).strip().lower()
    return s in ["1", "true", "t", "yes", "y", "tak"]


class Command(BaseCommand):
    help = "Importuje przenośniki z pliku conveyors_info.xls"

    def handle(self, *args, **options):
        file_path = "conveyors_info.xlsx"
        self.stdout.write(f"Wczytuję: {file_path}")

        df = pd.read_excel(file_path)
        # wywalamy ewentualne kolumny 'Unnamed'
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        count = 0

        for _, row in df.iterrows():
            mine_name = row["mine"]
            conveyor_name = row["conveyor"]

            # --- KOPALNIA ---
            kopalnia, _ = Kopalnia.objects.get_or_create(
                nazwa=mine_name
            )

            # --- PRZENOŚNIK  ---
            defaults = {
                # jeśli w Excelu nie ma tej kolumny, po prostu zostanie pusty string
                "oddzial": "" if pd.isna(row.get("division")) else str(row.get("division")),
                "dlugosc_m": clean_decimal(row.get("loop_length")),
                "transportowany_material": "" if pd.isna(row.get("transported_material")) else str(row.get("transported_material")),
                "predkosc_tasmy_ms": clean_decimal(row.get("velocity")),
                # poniższe są opcjonalne – jak nie ma kolumny, zostaną None/0
                "kat_nachylenia_deg": clean_decimal(row.get("inclination_deg")),
                "liczba_nadaw": clean_int(row.get("no_feeds")) or 0,
                "liczba_odbiorow": clean_int(row.get("no_discharge")) or 0,
                "pochylniany": clean_bool(row.get("inclined")),
                "liczba_segmentow": clean_int(row.get("no_segments")) or 0,
            }

            Przenosnik.objects.update_or_create(
                kopalnia=kopalnia,
                nazwa=conveyor_name,
                defaults=defaults,
            )

            count += 1

        self.stdout.write(self.style.SUCCESS(f"Zaimportowano/uzupełniono {count} przenośników"))


