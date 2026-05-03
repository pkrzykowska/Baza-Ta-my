import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from rd.models import Kopalnia, Przenosnik, Tasma, MontazTasmy


# -------------------------------------------------
# Funkcja czyszcząca liczby zmiennoprzecinkowe z Excela
# -------------------------------------------------
def clean_decimal(v):
    if pd.isna(v):
        return None
    s = str(v).strip().replace(",", ".")
    if s in ["", "-", "–", "nan", "None"]:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# -------------------------------------------------
# Funkcja czyszcząca liczby całkowite
# -------------------------------------------------
def clean_int(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s in ["", "-", "–", "nan", "None"]:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def clean_str(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


class Command(BaseCommand):
    """
    Komenda do importu danych z pliku b_info.xlsx.
    Importowane są:
    - kopalnie,
    - przenośniki,
    - taśmy,
    - montaże taśm.
    """
    help = (
        "Import taśm, przenośników i montaży z b_info.xlsx. "
        "Pierwszy montaż dla każdej taśmy z first_installation_date; "
        "regeneracja tylko dla R/R1/R2 z conv_instalation; "
        "przewidywana żywotność z predicted_lifetime; "
        "żywotność z lifetime."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        path = "b_info.xlsx"
        self.stdout.write(f"Wczytuję: {path}")

        df = pd.read_excel(path)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        imported_belts = 0
        imported_przen = 0
        mont_current_created = 0
        mont_first_created = 0
        first_id_set = 0
        skipped_rows = 0
        mont_first_updated = 0

        for _, row in df.iterrows():

            # =========================
            # 1. KOPALNIA
            # =========================
            mine_name = clean_str(row.get("mine", ""))
            if not mine_name:
                skipped_rows += 1
                continue

            kopalnia, _ = Kopalnia.objects.get_or_create(nazwa=mine_name)

            # =========================
            # 2. PRZENOŚNIK
            # =========================
            conveyor_name = clean_str(row.get("conveyor", ""))
            if not conveyor_name:
                skipped_rows += 1
                continue

            przen_defaults = {
                "transportowany_material": clean_str(row.get("transported_material")),
                "predkosc_tasmy_ms": clean_decimal(row.get("velocity")),
                "liczba_segmentow": clean_int(row.get("no_segments")),
                "data_ostatniego_wydruku": row.get("belt_status_info_printed") if pd.notna(row.get("belt_status_info_printed")) else None,
                "pochylniany": False,
                "liczba_nadaw": None,
                "liczba_odbiorow": None,
                "kat_nachylenia_deg": None,
            }

            przenosnik, created_pr = Przenosnik.objects.get_or_create(
                kopalnia=kopalnia,
                nazwa=conveyor_name,
                defaults=przen_defaults,
            )
            if created_pr:
                imported_przen += 1

            # =========================
            # 3. TAŚMA
            # =========================
            tasma_num = clean_str(row.get("section_name", ""))
            if not tasma_num:
                skipped_rows += 1
                continue

            belt_state = clean_str(row.get("belt_state")).upper()

            predicted_lifetime = clean_int(row.get("predicted_lifetime"))
            lifetime = clean_int(row.get("lifetime"))  # <-- NOWE: pobieramy lifetime

            conv_install_date = row.get("conv_instalation")
            conv_install_date = conv_install_date if pd.notna(conv_install_date) else None

            first_install_date = row.get("first_installation_date")
            first_install_date = first_install_date if pd.notna(first_install_date) else None

            tas_defaults = {
                "dlugosc_m": clean_decimal(row.get("section_length")),
                "stan": belt_state,
                "szerokosc_mm": clean_decimal(row.get("belt_width")),
                "wytrzymalosc_kN_na_m": clean_decimal(row.get("strength")),
                "srednica_linki_mm": clean_decimal(row.get("cord_diameter")),
                "okladka_gorna_mm": clean_decimal(row.get("top_cover")),
                "okladka_dolna_mm": clean_decimal(row.get("bottom_cover")),
                "przewidywana_zywotnosc_m": predicted_lifetime,
                "zywotnosc_m": lifetime,  # <-- NOWE: zapisujemy lifetime do bazy
            }

            tasma, created_ta = Tasma.objects.get_or_create(
                numer=tasma_num,
                defaults=tas_defaults,
            )

            # aktualizacja wartości jeśli się zmieniły
            changed = False
            for k, v in tas_defaults.items():
                if v is not None and getattr(tasma, k, None) != v:
                    setattr(tasma, k, v)
                    changed = True

            # regeneracja tylko dla R/R1/R2
            if belt_state in ["R", "R1", "R2"] and conv_install_date:
                if tasma.data_regeneracji != conv_install_date:
                    tasma.data_regeneracji = conv_install_date
                    changed = True

            if changed:
                tasma.save()

            imported_belts += 1

            # =========================
            # 4. MONTAŻ BIEŻĄCY TAŚMY
            # =========================
            if conv_install_date:
                _, created_curr = MontazTasmy.objects.get_or_create(
                    tasma=tasma,
                    przenosnik=przenosnik,
                    data=conv_install_date,
                    defaults={"typ": ""},
                )
                if created_curr:
                    mont_current_created += 1

            # =========================
            # 5. PIERWSZY MONTAŻ TAŚMY
            # =========================
            if first_install_date:
                first_montaz, created_first = MontazTasmy.objects.get_or_create(
                    tasma=tasma,
                    przenosnik=przenosnik,
                    data=first_install_date,
                    defaults={"typ": belt_state},
                )

                if created_first:
                    mont_first_created += 1
                else:
                    if belt_state and first_montaz.typ != belt_state:
                        first_montaz.typ = belt_state
                        first_montaz.save(update_fields=["typ"])
                        mont_first_updated += 1

                if tasma.pierwszy_montaz_id is None:
                    tasma.pierwszy_montaz_id = first_montaz.id
                    tasma.save(update_fields=["pierwszy_montaz_id"])
                    first_id_set += 1

        self.stdout.write(self.style.SUCCESS(f"Taśmy zaimportowane/uzupełnione: {imported_belts}"))
        self.stdout.write(self.style.SUCCESS(f"Przenośniki utworzone: {imported_przen}"))
        self.stdout.write(self.style.SUCCESS(f"Montaże bieżące utworzone: {mont_current_created}"))
        self.stdout.write(self.style.SUCCESS(f"Pierwsze montaże utworzone: {mont_first_created}"))
        self.stdout.write(self.style.SUCCESS(f"Pierwsze montaże zaktualizowane: {mont_first_updated}"))
        self.stdout.write(self.style.SUCCESS(f"Ustawiono pierwszy_montaz_id: {first_id_set}"))
        self.stdout.write(self.style.WARNING(f"Pominięto wierszy (braki nazw): {skipped_rows}"))

