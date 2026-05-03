from django.db import models


class Kopalnia(models.Model):
    """
    Tabela: kopalnia
    id – serial (PK – Django robi samo)
    """
    nazwa = models.CharField(max_length=100)
    rodzaj = models.CharField(max_length=50)
    wydobywany_material = models.CharField(max_length=50)
    miasto = models.CharField(max_length=80)

    class Meta:
        verbose_name = "Kopalnia"
        verbose_name_plural = "Kopalnie"

    def __str__(self):
        return self.nazwa


class Przenosnik(models.Model):
    """
    Tabela: przenosnik
    """
    kopalnia = models.ForeignKey(
        Kopalnia,
        on_delete=models.CASCADE,
        related_name="przenosniki",
    )
    oddzial = models.CharField(max_length=50, blank=True, null=True)
    nazwa = models.CharField(max_length=100)

    dlugosc_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    transportowany_material = models.CharField(max_length=50, blank=True, null=True)
    predkosc_tasmy_ms = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    kat_nachylenia_deg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    liczba_nadaw = models.IntegerField(blank=True, null=True)
    liczba_odbiorow = models.IntegerField(blank=True, null=True)
    pochylniany = models.BooleanField(default=False)
    liczba_segmentow = models.IntegerField(blank=True, null=True)
    data_ostatniego_wydruku = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Przenośnik"
        verbose_name_plural = "Przenośniki"

    def __str__(self):
        return self.nazwa


class Tasma(models.Model):
    """
    Tabela: tasma
    """
    numer = models.CharField(max_length=50)

    szerokosc_mm = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    dlugosc_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    wytrzymalosc_kN_na_m = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    srednica_linki_mm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    grubosc_mm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    okladka_gorna_mm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    okladka_dolna_mm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    stan = models.CharField(max_length=20, blank=True, null=True)
    data_produkcji = models.DateField(blank=True, null=True)
    data_regeneracji = models.DateField(blank=True, null=True)

    # predicted_lifetime z Excela
    przewidywana_zywotnosc_m = models.IntegerField(blank=True, null=True)

    # lifetime z Excela (NOWE POLE – potrzebne do raportów)
    zywotnosc_m = models.IntegerField(blank=True, null=True)

    # w ERD: int, bez relacji – zostawiamy jako zwykłe pole
    pierwszy_montaz_id = models.IntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Taśma"
        verbose_name_plural = "Taśmy"

    def __str__(self):
        return self.numer


class Zlacze(models.Model):
    """
    Tabela: zlacze
    """
    numer = models.CharField(max_length=50)

    przenosnik = models.ForeignKey(
        Przenosnik,
        on_delete=models.CASCADE,
        related_name="zlacza",
    )

    dlugosc_m = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    skosnosc_deg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    liczba_stopni = models.IntegerField(blank=True, null=True)

    data_wykonania = models.DateField(blank=True, null=True)
    data_usuniecia = models.DateField(blank=True, null=True)
    wykonawca = models.CharField(max_length=100, blank=True, null=True)

    tasma_przed = models.ForeignKey(
        Tasma,
        on_delete=models.SET_NULL,
        related_name="zlacza_przed",
        blank=True,
        null=True,
    )
    tasma_za = models.ForeignKey(
        Tasma,
        on_delete=models.SET_NULL,
        related_name="zlacza_za",
        blank=True,
        null=True,
    )

    pozycja_od_poczatku_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = "Złącze"
        verbose_name_plural = "Złącza"

    def __str__(self):
        return self.numer


class Nadawa(models.Model):
    """
    Tabela: nadawa
    """
    przenosnik_podajacy = models.ForeignKey(
        Przenosnik,
        on_delete=models.CASCADE,
        related_name="nadawy_podajace",
    )
    przenosnik_odbierajacy = models.ForeignKey(
        Przenosnik,
        on_delete=models.CASCADE,
        related_name="nadawy_odbierajace",
    )

    kat_deg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ulozenie = models.CharField(max_length=50, blank=True, null=True)
    krata_zsypowa = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Nadawa"
        verbose_name_plural = "Nadawy"

    def __str__(self):
        return f"Nadawa {self.id}"


class MontazTasmy(models.Model):
    """
    Tabela: montaz_tasmy
    """
    tasma = models.ForeignKey(
        Tasma,
        on_delete=models.CASCADE,
        related_name="montaze",
    )
    przenosnik = models.ForeignKey(
        Przenosnik,
        on_delete=models.CASCADE,
        related_name="montaze_tasm",
    )

    data = models.DateField()
    typ = models.CharField(max_length=30, blank=True, null=True)

    zlacze_przed = models.ForeignKey(
        Zlacze,
        on_delete=models.SET_NULL,
        related_name="montaze_przed",
        blank=True,
        null=True,
    )
    zlacze_za = models.ForeignKey(
        Zlacze,
        on_delete=models.SET_NULL,
        related_name="montaze_za",
        blank=True,
        null=True,
    )

    uwagi = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Montaż taśmy"
        verbose_name_plural = "Montaże taśm"

    def __str__(self):
        return f"Montaż taśmy {self.tasma} na {self.przenosnik}"
