import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime
import webbrowser

import pandas as pd
import django

#DJANGO SETUP
BASE_DIR = os.path.dirname(os.path.abspath(__file__))      # tasmy_proj/app
PROJECT_ROOT = os.path.dirname(BASE_DIR)                   # tasmy_proj

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tasmy_proj.settings")
django.setup()

#MODELE
from rd.models import Kopalnia, Przenosnik, Tasma, Zlacze, MontazTasmy


def s(x):
    return "" if x is None else str(x)


def safe_filename(name: str) -> str:
    bad = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for ch in bad:
        name = name.replace(ch, "_")
    return name


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Przenośniki – taśmy i złącza")
        self.geometry("1250x720")


        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.mines_by_name = {}
        self.all_conveyors = []
        self.filtered_conveyors = []

        self.build_ui()
        self.load_mines()
        self.load_conveyors()

    #UI
    def build_ui(self):
        #GÓRNY PASEK
        top = ttk.Frame(self, padding=(10, 10, 10, 6))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Kopalnia:").pack(side=tk.LEFT)

        self.mine_var = tk.StringVar()
        self.mine_combo = ttk.Combobox(top, textvariable=self.mine_var, state="readonly", width=40)
        self.mine_combo.pack(side=tk.LEFT, padx=6)
        self.mine_combo.bind("<<ComboboxSelected>>", lambda e: self.on_mine_change())

        ttk.Button(top, text="Odśwież", command=self.reload_all).pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(top, text="Dodaj przenośnik", command=self.add_conveyor).pack(side=tk.LEFT, padx=5)

        #PODZIAŁ OKNA LEWO/PRAWO
        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=4)

        #LEWA STRONA
        ttk.Label(left, text="Szukaj przenośnika:").pack(anchor="w")

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(left, textvariable=self.search_var)
        self.search_entry.pack(anchor="w", pady=(0, 8), fill=tk.X)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_search_filter())

        ttk.Label(left, text="Przenośniki w kopalni").pack(anchor="w")

        list_wrap = ttk.Frame(left)
        list_wrap.pack(fill=tk.BOTH, expand=True)

        self.conveyor_list = tk.Listbox(list_wrap, height=26)
        self.conveyor_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.conveyor_list.bind("<<ListboxSelect>>", lambda e: self.select_conveyor())

        list_scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.conveyor_list.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.conveyor_list.configure(yscrollcommand=list_scroll.set)

        #PRAWA STRONA
        self.details = ttk.LabelFrame(right, text="Dane przenośnika", padding=10)
        self.details.pack(fill=tk.X)

        self.lbl_conv = ttk.Label(self.details, text="Wybierz przenośnik z listy po lewej.")
        self.lbl_conv.pack(anchor="w")

        ops1 = ttk.Frame(right)
        ops1.pack(fill=tk.X, pady=(10, 2))

        ttk.Button(ops1, text="Dodaj taśmę", command=self.add_mount).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops1, text="Usuń taśmę", command=self.delete_mount).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops1, text="Wymień złącze", command=self.replace_joint).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops1, text="Edytuj taśmę", command=self.edit_mount).pack(side=tk.LEFT, padx=5)

        ops2 = ttk.Frame(right)
        ops2.pack(fill=tk.X, pady=(2, 8))

        ttk.Button(ops2, text="Wymień TAŚMĘ + nowe złącze ZA", command=self.replace_belt).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops2, text="Wymień FRAGMENT + nowe złącze", command=self.replace_fragment_split).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops2, text="Drukuj (HTML → PDF)", command=self.print_table_only).pack(side=tk.LEFT, padx=5)

        # RAPORTY
        ttk.Button(ops2, text="Raport: kończąca się żywotność", command=self.report_lifetime_ending).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops2, text="Raport: przekroczona żywotność", command=self.report_lifetime_exceeded).pack(side=tk.LEFT, padx=5)

        ttk.Label(right, text="Montaż taśmy na przenośniku (montaz_tasmy)").pack(anchor="w")

        #TABELA
        cols = ("id", "data", "typ", "tasma", "dlugosc_m", "zl_przed", "zl_za", "uwagi")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=18)

        headings = {
            "id": "ID",
            "data": "Data",
            "typ": "Typ",
            "tasma": "Taśma (numer)",
            "dlugosc_m": "Długość [m]",
            "zl_przed": "Złącze przed",
            "zl_za": "Złącze za",
            "uwagi": "Uwagi"
        }
        widths = {
            "id": 60,
            "data": 110,
            "typ": 90,
            "tasma": 170,
            "dlugosc_m": 110,
            "zl_przed": 140,
            "zl_za": 140,
            "uwagi": 260
        }

        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="center" if c != "uwagi" else "w")

        tree_wrap = ttk.Frame(right)
        tree_wrap.pack(fill=tk.BOTH, expand=True, pady=6)

        yscroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        xscroll = ttk.Scrollbar(tree_wrap, orient="horizontal")
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.configure(command=self.tree.yview)
        xscroll.configure(command=self.tree.xview)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#f6f6f6")

        self.status = ttk.Label(self, text="")
        self.status.pack(fill=tk.X, padx=10, pady=(0, 8))

    #HELPERS
    def clear_tree(self):
        for it in self.tree.get_children():
            self.tree.delete(it)

    def parse_date_or_none(self, txt: str):
        txt = (txt or "").strip()
        if not txt:
            return None
        try:
            return datetime.strptime(txt, "%Y-%m-%d").date()
        except Exception:
            return None

    def safe_float_or_none(self, txt: str):
        txt = (txt or "").strip().replace(",", ".")
        if not txt:
            return None
        try:
            return float(txt)
        except Exception:
            return None

    def recalc_segments(self, conveyor):
        try:
            cnt = MontazTasmy.objects.filter(przenosnik_id=conveyor.id).count()
            if hasattr(conveyor, "liczba_segmentow"):
                conveyor.liczba_segmentow = cnt
                conveyor.save(update_fields=["liczba_segmentow"])
        except Exception:
            pass

    def compute_total_belts_len(self, conveyor):
        total = 0.0
        mounts = MontazTasmy.objects.select_related("tasma").filter(przenosnik_id=conveyor.id)
        for m in mounts:
            if m.tasma and getattr(m.tasma, "dlugosc_m", None) is not None:
                try:
                    total += float(m.tasma.dlugosc_m)
                except Exception:
                    pass
        return round(total, 2)

    def sync_conveyor_length_from_belts(self, conveyor: Przenosnik):
        try:
            total = self.compute_total_belts_len(conveyor)
            conveyor.dlugosc_m = total
            conveyor.save(update_fields=["dlugosc_m"])
        except Exception:
            pass

    def refresh_conveyor_summary(self, conveyor: Przenosnik):
        self.recalc_segments(conveyor)
        self.sync_conveyor_length_from_belts(conveyor)
        self.show_conveyor_details(conveyor)

    #LOAD
    def reload_all(self):
        self.load_mines()
        self.load_conveyors()
        self.clear_tree()
        self.lbl_conv.config(text="Wybierz przenośnik z listy po lewej.")
        self.status.config(text="")

    def on_mine_change(self):
        self.search_var.set("")
        self.load_conveyors()
        self.clear_tree()
        self.lbl_conv.config(text="Wybierz przenośnik z listy po lewej.")
        self.status.config(text="")

    def load_mines(self):
        mines = list(Kopalnia.objects.all().order_by("nazwa"))
        self.mines_by_name = {m.nazwa: m for m in mines}
        self.mine_combo["values"] = [m.nazwa for m in mines]
        if mines and not self.mine_var.get():
            self.mine_var.set(mines[0].nazwa)

    def load_conveyors(self):
        self.conveyor_list.delete(0, tk.END)

        mine = self.mines_by_name.get(self.mine_var.get())
        if not mine:
            self.all_conveyors = []
            self.filtered_conveyors = []
            return

        self.all_conveyors = list(Przenosnik.objects.filter(kopalnia=mine).order_by("nazwa"))
        self.apply_search_filter()

    def apply_search_filter(self):
        q = (self.search_var.get() or "").strip().lower()

        if not q:
            self.filtered_conveyors = list(self.all_conveyors)
        else:
            self.filtered_conveyors = []
            for c in self.all_conveyors:
                name = (c.nazwa or "").lower()
                oddz = (getattr(c, "oddzial", "") or "").lower()
                if q in name or q in oddz:
                    self.filtered_conveyors.append(c)

        self.conveyor_list.delete(0, tk.END)
        for c in self.filtered_conveyors:
            self.conveyor_list.insert(tk.END, c.nazwa)

    def get_selected_conveyor(self):
        idxs = self.conveyor_list.curselection()
        if not idxs:
            return None
        return self.filtered_conveyors[idxs[0]]

    def select_conveyor(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            return
        self.load_mounts(conveyor)
        self.show_conveyor_details(conveyor)

    def show_conveyor_details(self, c: Przenosnik):
        mounts_cnt = MontazTasmy.objects.filter(przenosnik_id=c.id).count()
        suma_tasm = self.compute_total_belts_len(c)

        txt = (
            f"Nazwa: {s(c.nazwa)} | Oddział: {s(getattr(c, 'oddzial', ''))}\n"
            f"Długość przenośnika: {s(getattr(c, 'dlugosc_m', ''))} m | "
            f"Taśmy (odcinki): {mounts_cnt} | Suma długości taśm: {s(suma_tasm)} m\n"
            f"Prędkość: {s(getattr(c, 'predkosc_tasmy_ms', ''))} m/s | "
            f"Materiał: {s(getattr(c, 'transportowany_material', ''))}\n"
            f"Segmenty: {s(getattr(c, 'liczba_segmentow', ''))} | "
            f"Pochylniany: {s(getattr(c, 'pochylniany', ''))} | "
            f"Kąt: {s(getattr(c, 'kat_nachylenia_deg', ''))}°"
        )
        self.lbl_conv.config(text=txt)

    def load_mounts(self, conveyor: Przenosnik):
        self.clear_tree()

        mounts = list(
            MontazTasmy.objects.select_related("tasma", "zlacze_przed", "zlacze_za")
            .filter(przenosnik_id=conveyor.id)
            .order_by("id")
        )

        if not mounts:
            self.status.config(text="Brak wpisów w montaz_tasmy dla tego przenośnika.")
            self.show_conveyor_details(conveyor)
            return

        self.status.config(text=f"Wczytano montaże: {len(mounts)}")

        for idx, m in enumerate(mounts, start=1):
            tasma_num = s(m.tasma.numer) if m.tasma else ""
            dl = s(m.tasma.dlugosc_m) if (m.tasma and getattr(m.tasma, "dlugosc_m", None) is not None) else ""
            zl_przed = s(m.zlacze_przed.numer) if m.zlacze_przed else ""
            zl_za = s(m.zlacze_za.numer) if m.zlacze_za else ""

            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=(
                m.id, s(m.data), s(m.typ), tasma_num, dl, zl_przed, zl_za, s(m.uwagi)
            ), tags=(tag,))

        self.show_conveyor_details(conveyor)

    def get_selected_mount(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Brak wyboru", "Zaznacz wiersz montażu w tabeli.")
            return None
        mount_id = self.tree.item(sel[0])["values"][0]
        try:
            return MontazTasmy.objects.select_related("tasma", "zlacze_przed", "zlacze_za").get(id=mount_id)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie mogę pobrać montażu: {e}")
            return None

    #OPERACJE
    def add_conveyor(self):
        mine = self.mines_by_name.get(self.mine_var.get())
        if not mine:
            messagebox.showwarning("Brak kopalni", "Wybierz kopalnię.")
            return

        win = tk.Toplevel(self)
        win.title("Dodaj przenośnik")
        win.geometry("520x420")

        fields = [
            ("Nazwa", "nazwa"),
            ("Oddział (opcjonalnie)", "oddzial"),
            ("Długość [m]", "dlugosc_m"),
            ("Transportowany materiał", "transportowany_material"),
            ("Prędkość taśmy [m/s]", "predkosc_tasmy_ms"),
            ("Kąt nachylenia [deg]", "kat_nachylenia_deg"),
            ("Liczba segmentów (opcjonalnie)", "liczba_segmentow"),
            ("Pochylniany (0/1)", "pochylniany"),
        ]
        entries = {}

        for i, (label, key) in enumerate(fields):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            ent = ttk.Entry(win, width=30)
            ent.grid(row=i, column=1, padx=10, pady=6)
            entries[key] = ent

        def save():
            try:
                nazwa = entries["nazwa"].get().strip()
                if not nazwa:
                    messagebox.showwarning("Brak danych", "Podaj nazwę przenośnika.")
                    return

                c = Przenosnik(kopalnia=mine, nazwa=nazwa)
                oddz = entries["oddzial"].get().strip()
                c.oddzial = oddz if oddz else None

                def set_float(attr):
                    txt = entries[attr].get().strip()
                    if txt:
                        setattr(c, attr, float(txt.replace(",", ".")))

                def set_int(attr):
                    txt = entries[attr].get().strip()
                    if txt:
                        setattr(c, attr, int(txt))

                def set_str(attr):
                    txt = entries[attr].get().strip()
                    if txt:
                        setattr(c, attr, txt)

                set_float("dlugosc_m")
                set_str("transportowany_material")
                set_float("predkosc_tasmy_ms")
                set_float("kat_nachylenia_deg")
                if entries["liczba_segmentow"].get().strip():
                    set_int("liczba_segmentow")

                poch = entries["pochylniany"].get().strip()
                if poch:
                    c.pochylniany = poch in ("1", "True", "true", "tak", "TAK")

                c.save()
                win.destroy()
                self.load_conveyors()
                self.status.config(text="Dodano nowy przenośnik.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz", command=save).grid(row=len(fields), column=0, columnspan=2, pady=14)

    def add_mount(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        win = tk.Toplevel(self)
        win.title("Dodaj montaż (odcinek)")
        win.geometry("560x460")

        labels = [
            ("Data (RRRR-MM-DD) puste = dziś", "data"),
            ("Typ (np. N / R1 / R2)", "typ"),
            ("Taśma numer", "tasma_numer"),
            ("Długość taśmy [m] (opcjonalnie)", "tasma_dlugosc"),
            ("Złącze PRZED numer", "zl_przed"),
            ("Złącze ZA numer", "zl_za"),
            ("Uwagi (opcjonalnie)", "uwagi"),
        ]
        entries = {}
        for i, (lab, key) in enumerate(labels):
            ttk.Label(win, text=lab).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            ent = ttk.Entry(win, width=35)
            ent.grid(row=i, column=1, padx=10, pady=6)
            entries[key] = ent

        def save():
            try:
                dtxt = entries["data"].get().strip()
                typ = entries["typ"].get().strip()
                tnum = entries["tasma_numer"].get().strip()
                tlen = entries["tasma_dlugosc"].get().strip()
                z1 = entries["zl_przed"].get().strip()
                z2 = entries["zl_za"].get().strip()
                uw = entries["uwagi"].get().strip()

                if not tnum or not z1 or not z2:
                    messagebox.showwarning("Brak danych", "Wpisz: taśma numer, złącze PRZED i złącze ZA.")
                    return

                d = date.today()
                if dtxt:
                    y, m, dd = dtxt.split("-")
                    d = date(int(y), int(m), int(dd))

                tasma, _ = Tasma.objects.get_or_create(numer=tnum)
                if tlen:
                    tasma.dlugosc_m = float(tlen.replace(",", "."))
                    tasma.save()

                zl_przed, _ = Zlacze.objects.get_or_create(numer=z1, przenosnik=conveyor)
                zl_za, _ = Zlacze.objects.get_or_create(numer=z2, przenosnik=conveyor)

                MontazTasmy.objects.create(
                    przenosnik=conveyor,
                    tasma=tasma,
                    data=d,
                    typ=typ or None,
                    zlacze_przed=zl_przed,
                    zlacze_za=zl_za,
                    uwagi=uw or None
                )

                self.refresh_conveyor_summary(conveyor)
                win.destroy()
                self.load_mounts(conveyor)
                self.status.config(text="Dodano odcinek (montaż).")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz", command=save).grid(row=len(labels), column=0, columnspan=2, pady=14)

    def delete_mount(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        m = self.get_selected_mount()
        if not m:
            return

        txt = f"Na pewno usunąć odcinek (montaż) ID={m.id}?\nTaśma: {s(m.tasma.numer) if m.tasma else ''}"
        if not messagebox.askyesno("Potwierdź", txt):
            return

        try:
            m.delete()
            self.refresh_conveyor_summary(conveyor)
            self.load_mounts(conveyor)
            self.status.config(text="Usunięto odcinek (montaż).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def edit_mount(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        m = self.get_selected_mount()
        if not m:
            return

        win = tk.Toplevel(self)
        win.title("Edytuj wiersz (montaż taśmy)")
        win.geometry("600x520")

        cur_date = s(m.data)
        cur_typ = s(m.typ)
        cur_tasma = s(m.tasma.numer) if m.tasma else ""
        cur_len = s(m.tasma.dlugosc_m) if (m.tasma and getattr(m.tasma, "dlugosc_m", None) is not None) else ""
        cur_z1 = s(m.zlacze_przed.numer) if m.zlacze_przed else ""
        cur_z2 = s(m.zlacze_za.numer) if m.zlacze_za else ""
        cur_uw = s(m.uwagi)

        fields = [
            ("Data (YYYY-MM-DD)", "data", cur_date),
            ("Typ", "typ", cur_typ),
            ("Taśma (numer)", "tasma", cur_tasma),
            ("Długość taśmy [m]", "dlugosc", cur_len),
            ("Złącze PRZED (numer)", "z1", cur_z1),
            ("Złącze ZA (numer)", "z2", cur_z2),
            ("Uwagi", "uwagi", cur_uw),
        ]

        entries = {}
        for i, (lab, key, val) in enumerate(fields):
            ttk.Label(win, text=lab).grid(row=i, column=0, sticky="w", padx=10, pady=8)
            ent = ttk.Entry(win, width=40)
            ent.grid(row=i, column=1, padx=10, pady=8)
            ent.insert(0, val)
            entries[key] = ent

        def save():
            try:
                new_date = self.parse_date_or_none(entries["data"].get())
                if new_date is None:
                    messagebox.showwarning("Błąd", "Data jest wymagana (YYYY-MM-DD).")
                    return

                new_typ = entries["typ"].get().strip() or None
                new_tasma_num = entries["tasma"].get().strip()
                if not new_tasma_num:
                    messagebox.showwarning("Błąd", "Numer taśmy jest wymagany.")
                    return

                new_len = self.safe_float_or_none(entries["dlugosc"].get())
                new_z1 = entries["z1"].get().strip()
                new_z2 = entries["z2"].get().strip()
                if not new_z1 or not new_z2:
                    messagebox.showwarning("Błąd", "Złącze PRZED i ZA są wymagane.")
                    return

                new_uw = entries["uwagi"].get().strip() or None

                tasma, _ = Tasma.objects.get_or_create(numer=new_tasma_num)
                if new_len is not None:
                    tasma.dlugosc_m = new_len
                    tasma.save()

                zl_przed, _ = Zlacze.objects.get_or_create(numer=new_z1, przenosnik=conveyor)
                zl_za, _ = Zlacze.objects.get_or_create(numer=new_z2, przenosnik=conveyor)

                m.data = new_date
                m.typ = new_typ
                m.tasma = tasma
                m.zlacze_przed = zl_przed
                m.zlacze_za = zl_za
                m.uwagi = new_uw
                m.save()

                self.refresh_conveyor_summary(conveyor)
                win.destroy()
                self.load_mounts(conveyor)
                self.status.config(text="Zapisano zmiany w wierszu.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz", command=save).grid(row=len(fields), column=0, columnspan=2, pady=16)

    def replace_belt(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        old = self.get_selected_mount()
        if not old:
            return

        win = tk.Toplevel(self)
        win.title("Wymiana TAŚMY (NOWE złącze ZA)")
        win.geometry("560x340")

        ttk.Label(win, text=f"Montaż ID: {old.id} | Stara taśma: {s(old.tasma.numer) if old.tasma else ''}").pack(pady=8)

        ttk.Label(win, text="Nowa taśma (numer):").pack()
        ent_t = ttk.Entry(win, width=45)
        ent_t.pack(pady=4)

        ttk.Label(win, text="NOWE złącze ZA (numer):").pack()
        ent_z = ttk.Entry(win, width=45)
        ent_z.pack(pady=4)

        def save():
            try:
                new_tnum = ent_t.get().strip()
                new_znum = ent_z.get().strip()

                if not new_tnum or not new_znum:
                    messagebox.showwarning("Brak danych", "Podaj numer nowej taśmy oraz numer nowego złącza ZA.")
                    return

                new_tasma, _ = Tasma.objects.get_or_create(numer=new_tnum)

                data_ = old.data
                typ_ = old.typ
                uwagi_ = old.uwagi
                zl_przed_ = old.zlacze_przed
                old_zl_za = old.zlacze_za

                old.delete()

                if old_zl_za is not None:
                    try:
                        old_zl_za.delete()
                    except Exception:
                        pass

                new_zl_za, _ = Zlacze.objects.get_or_create(numer=new_znum, przenosnik=conveyor)

                MontazTasmy.objects.create(
                    przenosnik=conveyor,
                    tasma=new_tasma,
                    data=data_,
                    typ=typ_,
                    zlacze_przed=zl_przed_,
                    zlacze_za=new_zl_za,
                    uwagi=uwagi_
                )

                self.refresh_conveyor_summary(conveyor)
                win.destroy()
                self.load_mounts(conveyor)
                self.status.config(text="Wymieniono taśmę.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz wymianę", command=save).pack(pady=14)

    def replace_fragment_split(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        m = self.get_selected_mount()
        if not m:
            return

        if not m.tasma:
            messagebox.showwarning("Brak taśmy", "Ten montaż nie ma przypisanej taśmy.")
            return

        old_belt = m.tasma
        old_len = getattr(old_belt, "dlugosc_m", None)
        if old_len is None:
            messagebox.showwarning("Brak długości", "Taśma nie ma wpisanej długości.")
            return

        win = tk.Toplevel(self)
        win.title("Wymiana FRAGMENTU (podział odcinka)")
        win.geometry("600x420")

        ttk.Label(win, text=f"Montaż ID: {m.id} | Stara taśma: {old_belt.numer} | Długość: {old_len} m").pack(pady=8)

        ttk.Label(win, text="Ile metrów wymieniasz (fragment) [m]:").pack()
        ent_frag = ttk.Entry(win, width=20)
        ent_frag.pack(pady=4)

        ttk.Label(win, text="Nowa taśma (numer) dla fragmentu:").pack()
        ent_new_num = ttk.Entry(win, width=45)
        ent_new_num.pack(pady=4)

        ttk.Label(win, text="Nowe złącze w miejscu podziału (numer):").pack()
        ent_joint_mid = ttk.Entry(win, width=45)
        ent_joint_mid.pack(pady=4)

        def save():
            try:
                frag_txt = ent_frag.get().strip()
                new_num = ent_new_num.get().strip()
                mid_joint_num = ent_joint_mid.get().strip()

                if not frag_txt or not new_num or not mid_joint_num:
                    messagebox.showwarning("Brak danych", "Uzupełnij: długość fragmentu, numer nowej taśmy i numer nowego złącza.")
                    return

                frag_len = float(frag_txt.replace(",", "."))
                old_len_float = float(old_len)

                if frag_len <= 0 or frag_len >= old_len_float:
                    messagebox.showwarning("Błędna długość", "Fragment musi być > 0 i < długości odcinka.")
                    return

                old_part_len = old_len_float - frag_len

                old_belt.dlugosc_m = old_part_len
                old_belt.save()

                new_belt, _ = Tasma.objects.get_or_create(numer=new_num)
                new_belt.dlugosc_m = frag_len
                new_belt.save()

                zl_mid, _ = Zlacze.objects.get_or_create(numer=mid_joint_num, przenosnik=conveyor)

                old_zl_za = m.zlacze_za
                m.zlacze_za = zl_mid
                m.save()

                MontazTasmy.objects.create(
                    przenosnik=conveyor,
                    tasma=new_belt,
                    data=m.data,
                    typ=m.typ,
                    zlacze_przed=zl_mid,
                    zlacze_za=old_zl_za,
                    uwagi="fragment po wymianie"
                )

                self.refresh_conveyor_summary(conveyor)
                win.destroy()
                self.load_mounts(conveyor)
                self.status.config(text="Wymieniono fragment.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz podział", command=save).pack(pady=14)

    def replace_joint(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        m = self.get_selected_mount()
        if not m:
            return

        win = tk.Toplevel(self)
        win.title("Wymień złącze")
        win.geometry("520x260")

        ttk.Label(win, text=f"Montaż ID: {m.id} | Taśma: {s(m.tasma.numer) if m.tasma else ''}").pack(pady=8)

        which = tk.StringVar(value="za")
        frm = ttk.Frame(win)
        frm.pack(pady=6)
        ttk.Radiobutton(frm, text="Złącze PRZED", variable=which, value="przed").grid(row=0, column=0, padx=10)
        ttk.Radiobutton(frm, text="Złącze ZA", variable=which, value="za").grid(row=0, column=1, padx=10)

        ttk.Label(win, text="Nowy numer złącza:").pack(pady=(12, 4))
        ent = ttk.Entry(win, width=40)
        ent.pack()

        def save():
            try:
                new_num = ent.get().strip()
                if not new_num:
                    messagebox.showwarning("Brak danych", "Podaj numer nowego złącza.")
                    return

                new_joint, _ = Zlacze.objects.get_or_create(numer=new_num, przenosnik=conveyor)

                if which.get() == "przed":
                    m.zlacze_przed = new_joint
                else:
                    m.zlacze_za = new_joint

                m.save()
                win.destroy()
                self.load_mounts(conveyor)
                self.status.config(text="Zmieniono złącze.")
            except Exception as e:
                messagebox.showerror("Błąd", str(e))

        ttk.Button(win, text="Zapisz", command=save).pack(pady=14)

    #RAPORTY (Z EXCELA)
    def _num_or_none(self, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        txt = str(v).strip().replace(",", ".")
        if not txt or txt.lower() in ("nan", "none", "-"):
            return None
        try:
            return float(txt)
        except Exception:
            return None

    def _load_lifetime_map_from_excel(self):
        """
        Zwraca mapę:
          belt_map[section_name] = (predicted_lifetime, lifetime)
        Jeśli w Excelu ta sama taśma występuje wiele razy, bierzemy MAX(lifetime),
        żeby nie nadpisywało np. 290 -> 29.
        """
        path = os.path.join(BASE_DIR, "b_info.xlsx")  # excel obok main.py
        if not os.path.exists(path):
            messagebox.showerror("Brak pliku", f"Nie znaleziono pliku:\n{path}\nDaj b_info.xlsx do folderu app.")
            return {}

        try:
            df = pd.read_excel(path)
            df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
        except Exception as e:
            messagebox.showerror("Błąd Excela", f"Nie mogę wczytać {path}:\n{e}")
            return {}

        belt_map = {}
        for _, row in df.iterrows():
            num = row.get("section_name")
            num = "" if pd.isna(num) else str(num).strip()
            if not num:
                continue

            pred = self._num_or_none(row.get("predicted_lifetime"))
            life = self._num_or_none(row.get("lifetime"))
            if pred is None or life is None:
                continue

            if num not in belt_map:
                belt_map[num] = (pred, life)
            else:
                old_pred, old_life = belt_map[num]
                # pred zwykle stałe, ale jakby się różniło to bierzemy max
                new_pred = max(float(old_pred), float(pred))
                new_life = max(float(old_life), float(life))  # KLUCZOWE
                belt_map[num] = (new_pred, new_life)

        return belt_map

    def _build_lifetime_report_rows(self, mode: str, threshold: float):
        """
        mode:
          - 'ending'   => 0 <= (pred - life) <= threshold
          - 'exceeded' => (life - pred) > 0
        """
        mine = self.mines_by_name.get(self.mine_var.get())
        belt_map = self._load_lifetime_map_from_excel()
        if not belt_map:
            return []

        qs = MontazTasmy.objects.select_related("tasma", "przenosnik")
        if mine:
            qs = qs.filter(przenosnik__kopalnia=mine)

        # bierzemy ostatni montaż dla każdej taśmy (żeby nie dublować)
        qs = qs.order_by("-data", "-id")
        latest_by_belt = {}
        for m in qs:
            if not m.tasma or not m.przenosnik:
                continue
            belt_num = (s(getattr(m.tasma, "numer", "")) or "").strip()
            if not belt_num:
                continue
            if belt_num not in latest_by_belt:
                latest_by_belt[belt_num] = m

        rows = []
        for belt_num, m in latest_by_belt.items():
            if belt_num not in belt_map:
                continue

            pred, life = belt_map[belt_num]
            pred = float(pred)
            life = float(life)

            if mode == "ending":
                remaining = pred - life
                ok = (remaining >= 0) and (remaining <= float(threshold))
                if not ok:
                    continue
                rows.append({
                    "belt": belt_num,
                    "pred": pred,
                    "life": life,
                    "val": remaining,  # "pozostało"
                    "conveyor": s(getattr(m.przenosnik, "nazwa", "")),
                    "mount_id": m.id,
                })

            else:  # exceeded
                exceeded = life - pred
                ok = exceeded > 0
                if not ok:
                    continue
                rows.append({
                    "belt": belt_num,
                    "pred": pred,
                    "life": life,
                    "val": exceeded,  # "przekroczono"
                    "conveyor": s(getattr(m.przenosnik, "nazwa", "")),
                    "mount_id": m.id,
                })

        # ending: najmniej zostało na górze; exceeded: największe przekroczenie na górze
        if mode == "ending":
            rows.sort(key=lambda r: r["val"])
        else:
            rows.sort(key=lambda r: r["val"], reverse=True)

        return rows

    def _save_report_html(self, title: str, rows, mode: str, threshold: float):
        if not rows:
            messagebox.showwarning("Brak danych", "Brak rekordów do zapisania.")
            return

        # nagłówek i kolumna zależnie od trybu
        if mode == "ending":
            extra_info = f"<b>Warunek:</b> 0 ≤ (predicted - lifetime) ≤ {threshold}"
            col_name = "pozostało"
            col_desc = "pozostało (pred - life)"
        else:
            extra_info = "<b>Warunek:</b> lifetime > predicted (pokazane wszystkie przekroczone)"
            col_name = "przekroczono"
            col_desc = "przekroczono (life - pred)"

        trs = ""
        for i, r in enumerate(rows, start=1):
            trs += (
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{r['belt']}</td>"
                f"<td>{r['pred']}</td>"
                f"<td>{r['life']}</td>"
                f"<td>{round(r['val'], 3)}</td>"
                f"<td>{r['conveyor']}</td>"
                f"<td>{r['mount_id']}</td>"
                "</tr>"
            )

        html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: Arial, sans-serif; }}
.wrap {{ width: 1100px; margin: 0 auto; }}
h2 {{ margin-bottom: 6px; }}
.meta {{ font-size: 13px; margin-bottom: 10px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #333; padding: 6px; }}
th {{ background: #eee; }}
@media print {{ button {{ display:none; }} .wrap {{ width: auto; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h2>{title}</h2>
  <div class="meta"><b>Kopalnia:</b> {s(self.mine_var.get())}</div>
  <div class="meta">{extra_info}</div>
  <div class="meta"><b>Wygenerowano:</b> {date.today().isoformat()}</div>

  <div style="margin: 10px 0;">
    <button onclick="window.print()">Drukuj / Zapisz jako PDF</button>
  </div>

  <table>
    <thead>
      <tr>
        <th>Lp</th>
        <th>Taśma</th>
        <th>predicted_lifetime</th>
        <th>lifetime</th>
        <th>{col_desc}</th>
        <th>Przenośnik</th>
        <th>Montaż ID</th>
      </tr>
    </thead>
    <tbody>
      {trs}
    </tbody>
  </table>
</div>
</body>
</html>
"""

        default_name = safe_filename(f"raport_zywotnosc_{date.today().isoformat()}.html")
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML", "*.html")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.status.config(text=f"Zapisano raport HTML: {path}")
            webbrowser.open(path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać raportu:\n{e}")

    def _open_report_window_ending(self):
        title = "Raport – kończąca się żywotność"
        mode = "ending"

        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("1050x520")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Próg (ile ma zostać):").pack(side=tk.LEFT)
        thr_var = tk.StringVar(value="3")
        thr_entry = ttk.Entry(top, textvariable=thr_var, width=8)
        thr_entry.pack(side=tk.LEFT, padx=8)

        info_lbl = ttk.Label(top, text="")
        info_lbl.pack(side=tk.LEFT, padx=12)

        cols = ("belt", "pred", "life", "val", "conveyor", "mount_id")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=18)
        tv.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        heads = {
            "belt": "Taśma",
            "pred": "predicted_lifetime",
            "life": "lifetime",
            "val": "pozostało",
            "conveyor": "Przenośnik",
            "mount_id": "Montaż ID",
        }
        widths = {"belt": 170, "pred": 140, "life": 120, "val": 120, "conveyor": 360, "mount_id": 100}
        for c in cols:
            tv.heading(c, text=heads[c])
            tv.column(c, width=widths[c], anchor="center" if c != "conveyor" else "w")

        rows_holder = {"rows": [], "thr": 3.0}

        def refresh():
            for it in tv.get_children():
                tv.delete(it)

            try:
                thr = float((thr_var.get() or "3").strip().replace(",", "."))
            except Exception:
                thr = 3.0

            rows = self._build_lifetime_report_rows(mode=mode, threshold=thr)
            rows_holder["rows"] = rows
            rows_holder["thr"] = thr

            for r in rows:
                tv.insert("", tk.END, values=(
                    r["belt"],
                    r["pred"],
                    r["life"],
                    round(r["val"], 3),
                    r["conveyor"],
                    r["mount_id"],
                ))

            info_lbl.config(text=f"Znaleziono: {len(rows)}")

        def save_html():
            self._save_report_html(
                title=title,
                rows=rows_holder["rows"],
                mode=mode,
                threshold=rows_holder["thr"],
            )

        btns = ttk.Frame(win, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)

        ttk.Button(btns, text="Odśwież", command=refresh).pack(side=tk.LEFT)
        ttk.Button(btns, text="Zapisz raport HTML", command=save_html).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Zamknij", command=win.destroy).pack(side=tk.RIGHT)

        # opcjonalnie: ENTER w polu odświeża
        thr_entry.bind("<Return>", lambda e: refresh())

        refresh()

    def _open_report_window_exceeded(self):
        title = "Raport – przekroczona żywotność"
        mode = "exceeded"

        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("1050x520")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)

        # zamiast progu — stały tekst
        info_lbl = ttk.Label(top, text="")
        info_lbl.pack(side=tk.LEFT)

        cols = ("belt", "pred", "life", "val", "conveyor", "mount_id")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=18)
        tv.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        heads = {
            "belt": "Taśma",
            "pred": "predicted_lifetime",
            "life": "lifetime",
            "val": "przekroczono",
            "conveyor": "Przenośnik",
            "mount_id": "Montaż ID",
        }
        widths = {"belt": 170, "pred": 140, "life": 120, "val": 120, "conveyor": 360, "mount_id": 100}
        for c in cols:
            tv.heading(c, text=heads[c])
            tv.column(c, width=widths[c], anchor="center" if c != "conveyor" else "w")

        rows_holder = {"rows": []}

        def refresh():
            for it in tv.get_children():
                tv.delete(it)

            rows = self._build_lifetime_report_rows(mode=mode, threshold=0)
            rows_holder["rows"] = rows

            for r in rows:
                tv.insert("", tk.END, values=(
                    r["belt"],
                    r["pred"],
                    r["life"],
                    round(r["val"], 3),
                    r["conveyor"],
                    r["mount_id"],
                ))

            info_lbl.config(text=f"Pokazywane są wszystkie taśmy z przekroczoną żywotnością.   Znaleziono: {len(rows)}")

        def save_html():
            self._save_report_html(
                title=title,
                rows=rows_holder["rows"],
                mode=mode,
                threshold=0,
            )

        btns = ttk.Frame(win, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)

        ttk.Button(btns, text="Odśwież", command=refresh).pack(side=tk.LEFT)
        ttk.Button(btns, text="Zapisz raport HTML", command=save_html).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Zamknij", command=win.destroy).pack(side=tk.RIGHT)

        refresh()

    def report_lifetime_ending(self):
        self._open_report_window_ending()

    def report_lifetime_exceeded(self):
        self._open_report_window_exceeded()

    #WYDRUK: TYLKO TABELA
    def print_table_only(self):
        conveyor = self.get_selected_conveyor()
        if not conveyor:
            messagebox.showwarning("Brak przenośnika", "Wybierz przenośnik.")
            return

        mounts = list(
            MontazTasmy.objects.select_related("tasma", "zlacze_przed", "zlacze_za")
            .filter(przenosnik_id=conveyor.id)
            .order_by("id")
        )
        if not mounts:
            messagebox.showwarning("Brak danych", "Brak montaży do wydruku.")
            return

        total_len = 0.0
        rows_html = ""
        for i, m in enumerate(mounts, start=1):
            t = m.tasma
            z1 = m.zlacze_przed
            z2 = m.zlacze_za
            if t and getattr(t, "dlugosc_m", None) is not None:
                try:
                    total_len += float(t.dlugosc_m)
                except Exception:
                    pass

            rows_html += (
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{s(m.data)}</td>"
                f"<td>{s(m.typ)}</td>"
                f"<td>{s(t.numer) if t else ''}</td>"
                f"<td>{s(t.dlugosc_m) if (t and getattr(t,'dlugosc_m',None) is not None) else ''}</td>"
                f"<td>{s(z1.numer) if z1 else ''}</td>"
                f"<td>{s(z2.numer) if z2 else ''}</td>"
                f"<td>{s(m.uwagi)}</td>"
                "</tr>"
            )

        html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Status przenośnika</title>
<style>
body {{ font-family: Arial, sans-serif; }}
.wrap {{ width: 1100px; margin: 0 auto; }}
h2 {{ margin-bottom: 6px; }}
.meta {{ font-size: 13px; margin-bottom: 10px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #333; padding: 6px; }}
th {{ background: #eee; }}
@media print {{ button {{ display:none; }} .wrap {{ width: auto; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h2>Status przenośnika – lista taśm i złączy</h2>
  <div class="meta"><b>Kopalnia:</b> {s(self.mine_var.get())}</div>
  <div class="meta"><b>Przenośnik:</b> {s(conveyor.nazwa)} &nbsp;&nbsp; <b>Oddział:</b> {s(getattr(conveyor, 'oddzial', ''))}</div>
  <div class="meta">
    <b>Długość przenośnika:</b> {s(getattr(conveyor,'dlugosc_m',''))} m &nbsp;&nbsp;
    <b>Prędkość:</b> {s(getattr(conveyor,'predkosc_tasmy_ms',''))} m/s &nbsp;&nbsp;
    <b>Materiał:</b> {s(getattr(conveyor,'transportowany_material',''))}
  </div>
  <div class="meta"><b>Liczba odcinków:</b> {len(mounts)} &nbsp;&nbsp; <b>Suma długości taśm:</b> {round(total_len, 2)} m</div>

  <div style="margin: 10px 0;">
    <button onclick="window.print()">Drukuj / Zapisz jako PDF</button>
  </div>

  <table>
    <thead>
      <tr>
        <th>Lp</th><th>Data</th><th>Typ</th><th>Taśma</th><th>Długość [m]</th><th>Złącze przed</th><th>Złącze za</th><th>Uwagi</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>
</body>
</html>
"""

        default_name = safe_filename(f"status_{conveyor.nazwa}_{date.today().isoformat()}.html")
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML", "*.html")]
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.status.config(text=f"Zapisano wydruk HTML: {path}")
            webbrowser.open(path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać wydruku:\n{e}")


if __name__ == "__main__":
    App().mainloop()



def apply_search_filter(self):
    zapytanie = self.search_var.get().strip().lower()
    wszystkie_przenosniki = self.all_conveyors

    if zapytanie == "":
        pasujace_przenosniki = wszystkie_przenosniki
    else:
        pasujace_przenosniki = []
        for przenosnik in wszystkie_przenosniki:
            nazwa = (przenosnik.nazwa or "").lower()
            oddzial = (getattr(przenosnik, "oddzial", "") or "").lower()

            if zapytanie in nazwa or zapytanie in oddzial:
                pasujace_przenosniki.append(przenosnik)

    self.conveyor_list.delete(0, tk.END)
    for przenosnik in pasujace_przenosniki:
        self.conveyor_list.insert(tk.END, przenosnik.nazwa)
