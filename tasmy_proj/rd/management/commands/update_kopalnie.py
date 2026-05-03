import pandas as pd
from django.core.management.base import BaseCommand
from rd.models import Kopalnia


class Command(BaseCommand):
    help = "Uzupełnia dane w tabeli Kopalnia na podstawie b_info.xlsx (wydobywany_material)."

    def handle(self, *args, **options):
        path = "b_info.xlsx"
        self.stdout.write(f"Wczytuję: {path}")

        df = pd.read_excel(path)
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        updated = 0
        skipped = 0

        # bierzemy po 1 materiale na kopalnie (pierwszy niepusty)
        for mine, g in df.groupby("mine", sort=False):
            mine_name = str(mine).strip()

            # szukamy pierwszego sensownego materiału
            material = None
            for v in g["transported_material"].tolist():
                if pd.notna(v):
                    s = str(v).strip()
                    if s and s.lower() != "nan":
                        material = s
                        break

            kopalnia, _ = Kopalnia.objects.get_or_create(nazwa=mine_name)

            if material and not kopalnia.wydobywany_material:
                kopalnia.wydobywany_material = material
                kopalnia.save()
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Zaktualizowano kopalnie: {updated}"))
        self.stdout.write(self.style.WARNING(f"Pominięto (już miały dane / brak materiału): {skipped}"))




