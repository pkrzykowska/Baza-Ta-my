from django.core.management.base import BaseCommand
from rd.models import MontazTasmy, Zlacze
from datetime import date


class Command(BaseCommand):
    help = "Uzupełnia pola zlacze_przed i zlacze_za w MontazTasmy na podstawie tabeli Zlacze."

    def handle(self, *args, **options):
        updated = 0
        skipped = 0

        for m in MontazTasmy.objects.select_related("tasma", "przenosnik"):
            # jeśli już coś jest wpisane, to nie ruszamy
            if m.zlacze_przed_id or m.zlacze_za_id:
                skipped += 1
                continue

            # Złącze PRZED taśmą = takie, gdzie taśma jest "za"
            zl_przed_qs = Zlacze.objects.filter(
                przenosnik=m.przenosnik,
                tasma_za=m.tasma
            )

            # Złącze ZA taśmą = takie, gdzie taśma jest "przed"
            zl_za_qs = Zlacze.objects.filter(
                przenosnik=m.przenosnik,
                tasma_przed=m.tasma
            )

            # jeśli mamy daty wykonania, wybieramy najbliższe do daty montażu
            def pick_closest(qs):
                if not qs.exists():
                    return None
                if m.data:
                    best = None
                    best_diff = None
                    for z in qs:
                        if z.data_wykonania:
                            diff = abs((z.data_wykonania - m.data).days)
                            if best is None or diff < best_diff:
                                best = z
                                best_diff = diff
                    if best:
                        return best
                # fallback: pierwsze po dacie
                return qs.order_by("data_wykonania", "id").first()

            zl_przed = pick_closest(zl_przed_qs)
            zl_za = pick_closest(zl_za_qs)

            if zl_przed or zl_za:
                m.zlacze_przed = zl_przed
                m.zlacze_za = zl_za
                m.save()
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Zaktualizowano montaży: {updated}"))
        self.stdout.write(self.style.WARNING(f"Pominięto (brak pasujących złączy lub już były): {skipped}"))








