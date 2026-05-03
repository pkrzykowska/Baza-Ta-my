import pandas as pd
from django.core.management.base import BaseCommand
from rd.models import Kopalnia, Przenosnik, Tasma, Zlacze


def clean_decimal(v):
    if pd.isna(v):
        return None
    s = str(v).strip().replace(",", ".")
    if s in ["", "-", "–", "nan"]:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class Command(BaseCommand):
    help = (
        "Importuje złącza z b_info.xlsx na podstawie splice_before/splice_after, "
        "domyka pętle i zapisuje pozycję_od_poczatku_m."
    )

    def handle(self, *args, **options):
        path = "b_info.xlsx"
        self.stdout.write(f"Wczytuję: {path}")

        df = pd.read_excel(path)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        group_cols = ["mine", "conveyor", "belt_state"]

        imported = 0
        skipped = 0

        for (mine, conveyor, belt_state), g in df.groupby(group_cols, sort=False):
            g = g.reset_index(drop=True)
            if len(g) == 0:
                continue

            mine_name = str(mine).strip()
            conveyor_name = str(conveyor).strip()

            kopalnia, _ = Kopalnia.objects.get_or_create(nazwa=mine_name)
            przenosnik, _ = Przenosnik.objects.get_or_create(
                kopalnia=kopalnia,
                nazwa=conveyor_name,
                defaults={}
            )

            # ---------- policz narastająco pozycje od początku ----------
            lengths = []
            for i in range(len(g)):
                L = clean_decimal(g.iloc[i].get("section_length"))
                lengths.append(L or 0.0)

            cum_start = [0.0] * len(g)  # do początku odcinka
            cum_end = [0.0] * len(g)    # do końca odcinka
            running = 0.0
            for i, L in enumerate(lengths):
                cum_start[i] = running
                running += L
                cum_end[i] = running

            loop_total = running  # całkowita długość pętli

            # ---------- pierwsza i ostatnia taśma w grupie (do domknięcia) ----------
            first_section_name = str(g.iloc[0].get("section_name")).strip()
            last_section_name = str(g.iloc[len(g) - 1].get("section_name")).strip()

            first_tasma = None
            last_tasma = None

            if first_section_name and first_section_name != "nan":
                first_tasma, _ = Tasma.objects.get_or_create(numer=first_section_name)
            if last_section_name and last_section_name != "nan":
                last_tasma, _ = Tasma.objects.get_or_create(numer=last_section_name)

            for i in range(len(g)):
                row = g.iloc[i]

                section_name = str(row.get("section_name")).strip()
                if not section_name or section_name == "nan":
                    continue

                tasma_curr, _ = Tasma.objects.get_or_create(
                    numer=section_name,
                    defaults={
                        "dlugosc_m": clean_decimal(row.get("section_length")),
                        "szerokosc_mm": clean_decimal(row.get("belt_width")),
                        "wytrzymalosc_kN_na_m": clean_decimal(row.get("strength")),
                        "srednica_linki_mm": clean_decimal(row.get("cord_diameter")),
                        "okladka_gorna_mm": clean_decimal(row.get("top_cover")),
                        "okladka_dolna_mm": clean_decimal(row.get("bottom_cover")),
                        "stan": row.get("belt_state"),
                    }
                )

                # -----------------------------------------
                # 1) splice_before (pozycja = cum_start[i])
                # -----------------------------------------
                splice_before = row.get("splice_before")
                if pd.notna(splice_before) and str(splice_before).strip() not in ["", "-", "–"]:
                    if i == 0:
                        tasma_prev = last_tasma
                    else:
                        prev_section_name = str(g.iloc[i - 1].get("section_name")).strip()
                        tasma_prev = None
                        if prev_section_name and prev_section_name != "nan":
                            tasma_prev, _ = Tasma.objects.get_or_create(numer=prev_section_name)

                    data_wykonania = row.get("conv_instalation")
                    if pd.isna(data_wykonania):
                        data_wykonania = None

                    pos = cum_start[i]  # <-- tu pozycja złącza przed i-tym odcinkiem

                    zlacze, created = Zlacze.objects.get_or_create(
                        numer=str(splice_before).strip(),
                        przenosnik=przenosnik,
                        defaults={
                            "tasma_przed": tasma_prev,
                            "tasma_za": tasma_curr,
                            "dlugosc_m": 1.5,
                            "liczba_stopni": 2,
                            "skosnosc_deg": 0,
                            "data_wykonania": data_wykonania,
                            "data_usuniecia": None,
                            "pozycja_od_poczatku_m": pos,
                        }
                    )

                    if not created:
                        changed = False
                        if zlacze.tasma_przed is None and tasma_prev is not None:
                            zlacze.tasma_przed = tasma_prev; changed = True
                        if zlacze.tasma_za is None:
                            zlacze.tasma_za = tasma_curr; changed = True
                        if zlacze.data_wykonania is None and data_wykonania is not None:
                            zlacze.data_wykonania = data_wykonania; changed = True
                        if zlacze.dlugosc_m is None:
                            zlacze.dlugosc_m = 1.5; changed = True
                        if zlacze.liczba_stopni is None:
                            zlacze.liczba_stopni = 2; changed = True
                        if zlacze.skosnosc_deg is None:
                            zlacze.skosnosc_deg = 0; changed = True
                        if zlacze.pozycja_od_poczatku_m is None:
                            zlacze.pozycja_od_poczatku_m = pos; changed = True
                        if changed:
                            zlacze.save()

                    imported += 1

                # -----------------------------------------
                # 2) splice_after (pozycja = cum_end[i])
                # -----------------------------------------
                splice_after = row.get("splice_after")
                if pd.notna(splice_after) and str(splice_after).strip() not in ["", "-", "–"]:
                    if i == len(g) - 1:
                        tasma_next = first_tasma
                        next_row = g.iloc[0]
                    else:
                        next_row = g.iloc[i + 1]
                        next_section_name = str(next_row.get("section_name")).strip()
                        tasma_next = None
                        if next_section_name and next_section_name != "nan":
                            tasma_next, _ = Tasma.objects.get_or_create(numer=next_section_name)

                    data_wykonania = next_row.get("conv_instalation")
                    if pd.isna(data_wykonania):
                        data_wykonania = None

                    pos = cum_end[i]  # <-- tu pozycja złącza za i-tym odcinkiem

                    zlacze, created = Zlacze.objects.get_or_create(
                        numer=str(splice_after).strip(),
                        przenosnik=przenosnik,
                        defaults={
                            "tasma_przed": tasma_curr,
                            "tasma_za": tasma_next,
                            "dlugosc_m": 1.5,
                            "liczba_stopni": 2,
                            "skosnosc_deg": 0,
                            "data_wykonania": data_wykonania,
                            "data_usuniecia": None,
                            "pozycja_od_poczatku_m": pos,
                        }
                    )

                    if not created:
                        changed = False
                        if zlacze.tasma_przed is None:
                            zlacze.tasma_przed = tasma_curr; changed = True
                        if zlacze.tasma_za is None and tasma_next is not None:
                            zlacze.tasma_za = tasma_next; changed = True
                        if zlacze.data_wykonania is None and data_wykonania is not None:
                            zlacze.data_wykonania = data_wykonania; changed = True
                        if zlacze.dlugosc_m is None:
                            zlacze.dlugosc_m = 1.5; changed = True
                        if zlacze.liczba_stopni is None:
                            zlacze.liczba_stopni = 2; changed = True
                        if zlacze.skosnosc_deg is None:
                            zlacze.skosnosc_deg = 0; changed = True
                        if zlacze.pozycja_od_poczatku_m is None:
                            zlacze.pozycja_od_poczatku_m = pos; changed = True
                        if changed:
                            zlacze.save()

                    imported += 1

        self.stdout.write(self.style.SUCCESS(f"Utworzono/uzupełniono złączy: {imported}"))
        self.stdout.write(self.style.WARNING(f"Pominięto: {skipped}"))
