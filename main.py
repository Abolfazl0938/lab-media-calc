import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import flet as ft

DATA_FILE = Path(__file__).resolve().parent / "media_data.json"

USER_DATA_DIR = Path(
    os.getenv("FLET_APP_STORAGE_DATA") or (Path.home() / ".lab_media_calc")
)
CUSTOM_FILE = USER_DATA_DIR / "custom_media.json"
HISTORY_FILE = USER_DATA_DIR / "history.json"
NOTEBOOK_FILE = USER_DATA_DIR / "lab_notebook.json"
INVENTORY_FILE = USER_DATA_DIR / "inventory.json"


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy if gm > 2 else gy - 1
    days = (
        (365 * gy)
        + ((gy2 + 4) // 4)
        - ((gy2 + 100) // 100)
        + ((gy2 + 400) // 400)
        - 80
        + gd
        + g_d_m[gm - 1]
    )
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def jalali_to_gregorian(jy, jm, jd):
    jy -= 979
    jm -= 1
    jd -= 1
    j_day_no = 365 * jy + (jy // 33) * 8 + ((jy % 33 + 3) // 4)
    for i in range(jm):
        j_day_no += 31 if i < 6 else 30
    j_day_no += jd

    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no = g_day_no % 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no = g_day_no % 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no = g_day_no % 365

    g_d_m = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and g_day_no >= g_d_m[gm + 1]:
        gm += 1
        g_day_no -= g_d_m[gm]
    gm += 1
    gd = g_day_no + 1
    return date(gy, gm, gd)


def parse_jalali_date(date_str):
    if not date_str:
        return None
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    cleaned = date_str.strip().translate(trans)
    cleaned = cleaned.replace("-", "/").replace(".", "/")
    parts = cleaned.split("/")
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if y < 100:
            y += 1300 if y >= 50 else 1400
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        if m > 6 and d > 30:
            return None
        return jalali_to_gregorian(y, m, d)
    except Exception:
        return None


def get_current_jalali_date():
    now = datetime.now()
    return gregorian_to_jalali(now.year, now.month, now.day)


def load_media(path=DATA_FILE, missing_ok=False):
    if missing_ok and not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(f"ساختار فایل {path.name} باید یک لیست باشد.")

    media = []
    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"ردیف {row_number} در فایل {path.name} معتبر نیست.")

        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"نام محیط کشت در ردیف {row_number} معتبر نیست.")

        try:
            grams_per_liter = Decimal(str(record["base_weight_per_liter"]))
        except (KeyError, InvalidOperation):
            raise ValueError(f"مقدار گرم در لیتر در ردیف {row_number} معتبر نیست.")

        if not grams_per_liter.is_finite() or grams_per_liter <= 0:
            raise ValueError(f"مقدار گرم در لیتر در ردیف {row_number} باید مثبت باشد.")

        media.append(
            {
                "name": name.strip(),
                "grams_per_liter": grams_per_liter,
            }
        )

    return sorted(media, key=lambda item: item["name"].casefold())


def load_history():
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list):
        return []
    return records


def load_notebook():
    if not NOTEBOOK_FILE.exists():
        return []
    with NOTEBOOK_FILE.open("r", encoding="utf-8") as file:
        try:
            records = json.load(file)
            if isinstance(records, list):
                return records
        except Exception:
            return []
    return []


def load_inventory():
    default_data = {
        "batches": [],
        "min_stocks": {},
        "recipes": [],
        "movements": [],
    }
    if not INVENTORY_FILE.exists():
        return default_data
    with INVENTORY_FILE.open("r", encoding="utf-8") as file:
        try:
            data = json.load(file)
            if isinstance(data, dict):
                for k in default_data:
                    if k not in data:
                        data[k] = default_data[k]
                return data
        except Exception:
            return default_data
    return default_data


def save_json(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


def show_number(number):
    if isinstance(number, (int, float)):
        number = Decimal(str(number))
    return format(number.normalize(), "f")


def main(page: ft.Page):
    page.title = "دستیار آزمایشگاه کشت | Lab Assistant"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 12

    page.window.width = 410
    page.window.height = 800
    page.window.resizable = True

    try:
        media = load_media()
        custom_media = load_media(CUSTOM_FILE, missing_ok=True)
        history = load_history()
        notebook_entries = load_notebook()
        inv_data = load_inventory()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        page.add(
            ft.Text(
                f"خطا در خواندن داده‌های برنامه:\n{error}",
                color=ft.Colors.RED_700,
            )
        )
        return

    media.extend(custom_media)
    media.sort(key=lambda item: item["name"].casefold())

    # --- تب اول: محاسبه‌گر (دست‌نخورده) ---
    selected = {"item": None}

    selected_info = ft.Text(
        "برای شروع، یک محیط کشت را از فهرست انتخاب کن.",
        size=14,
    )

    result_text = ft.Text(
        "مقدار پودر: —",
        size=19,
        weight=ft.FontWeight.BOLD,
    )

    result_box = ft.Container(
        content=result_text,
        padding=14,
        bgcolor=ft.Colors.BLUE_50,
        border_radius=12,
    )

    status_text = ft.Text("", size=12)

    theme_btn = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        tooltip="تغییر تم (تیره / روشن)",
    )

    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            theme_btn.icon = ft.Icons.LIGHT_MODE
            result_box.bgcolor = ft.Colors.BLUE_GREY_900
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            theme_btn.icon = ft.Icons.DARK_MODE
            result_box.bgcolor = ft.Colors.BLUE_50
        page.update()

    theme_btn.on_click = toggle_theme

    def calculate(e=None):
        item = selected["item"]
        if item is None:
            return

        raw_volume = (volume_input.value or "").strip().replace("٫", ".")
        if not raw_volume:
            result_text.value = "مقدار پودر: —"
            page.update()
            return

        try:
            volume_ml = Decimal(raw_volume)
        except InvalidOperation:
            result_text.value = "لطفاً حجم را به‌صورت عدد وارد کن."
            page.update()
            return

        if not volume_ml.is_finite() or volume_ml <= 0:
            result_text.value = "حجم باید عددی بزرگ‌تر از صفر باشد."
            page.update()
            return

        powder_grams = item["grams_per_liter"] * volume_ml / Decimal("1000")
        result_text.value = f"مقدار پودر: {show_number(powder_grams)} گرم"
        page.update()

    volume_input = ft.TextField(
        label="حجم موردنیاز (میلی‌لیتر)",
        hint_text="مثلاً 90",
        keyboard_type=ft.KeyboardType.NUMBER,
        disabled=True,
        on_change=calculate,
    )

    def choose_media(item):
        selected["item"] = item
        selected_info.value = (
            f"محیط انتخابی: {item['name']}\n"
            f"مقدار درج‌شده: {show_number(item['grams_per_liter'])} گرم در ۱ لیتر"
        )
        volume_input.disabled = False
        volume_input.value = ""
        result_text.value = "مقدار پودر: —"
        page.update()

    media_list = ft.ListView(height=180, spacing=4)
    match_count = ft.Text(size=12)

    def filter_media(e=None):
        query = (search_input.value or "").strip().casefold()
        matches = [item for item in media if query in item["name"].casefold()]
        match_count.value = f"{len(matches)} محیط کشت پیدا شد"

        if matches:
            media_list.controls = [
                ft.ListTile(
                    title=ft.Text(item["name"]),
                    subtitle=ft.Text(f"{show_number(item['grams_per_liter'])} g/L"),
                    on_click=lambda e, chosen=item: choose_media(chosen),
                )
                for item in matches
            ]
        else:
            media_list.controls = [ft.Text("محیط کشتی با این نام پیدا نشد.")]
        page.update()

    search_input = ft.TextField(
        label="جست‌وجوی نام محیط کشت",
        hint_text="مثلاً EC یا Agar",
        on_change=filter_media,
    )

    new_name_input = ft.TextField(
        label="نام محیط کشت جدید",
        hint_text="ترجیحاً همراه با برند و کد محصول",
    )

    new_grams_input = ft.TextField(
        label="مقدار پودر برای ۱ لیتر (گرم)",
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    add_form = ft.Column(
        visible=False,
        spacing=8,
        controls=[
            new_name_input,
            new_grams_input,
        ],
    )

    def toggle_add_form(e):
        add_form.visible = not add_form.visible
        status_text.value = ""
        page.update()

    def add_custom_medium(e):
        name = (new_name_input.value or "").strip()
        raw_grams = (new_grams_input.value or "").strip().replace("٫", ".")

        if not name:
            status_text.value = "نام محیط کشت جدید را وارد کن."
            page.update()
            return

        if any(item["name"].casefold() == name.casefold() for item in media):
            status_text.value = "محیط کشتی با این نام از قبل وجود دارد."
            page.update()
            return

        try:
            grams_per_liter = Decimal(raw_grams)
        except InvalidOperation:
            status_text.value = "مقدار گرم در لیتر باید عدد باشد."
            page.update()
            return

        if not grams_per_liter.is_finite() or grams_per_liter <= 0:
            status_text.value = "مقدار گرم در لیتر باید بزرگ‌تر از صفر باشد."
            page.update()
            return

        new_record = {
            "name": name,
            "base_weight_per_liter": show_number(grams_per_liter),
        }
        updated_records = [
            {
                "name": item["name"],
                "base_weight_per_liter": show_number(item["grams_per_liter"]),
            }
            for item in custom_media
        ]
        updated_records.append(new_record)

        try:
            save_json(CUSTOM_FILE, updated_records)
        except OSError as error:
            status_text.value = f"ذخیرهٔ محیط کشت انجام نشد: {error}"
            page.update()
            return

        new_item = {
            "name": name,
            "grams_per_liter": grams_per_liter,
        }
        custom_media.append(new_item)
        media.append(new_item)
        media.sort(key=lambda item: item["name"].casefold())

        new_name_input.value = ""
        new_grams_input.value = ""
        add_form.visible = False
        search_input.value = name
        filter_media()
        choose_media(new_item)
        status_text.value = "محیط کشت جدید ذخیره شد."
        page.update()

    add_form.controls.append(
        ft.Row(
            controls=[
                ft.Text("ذخیرهٔ محیط جدید"),
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    tooltip="ذخیرهٔ محیط کشت جدید",
                    on_click=add_custom_medium,
                ),
            ]
        )
    )

    add_btn = ft.IconButton(
        icon=ft.Icons.ADD,
        tooltip="افزودن محیط کشت دلخواه",
        on_click=toggle_add_form,
    )

    history_list = ft.ListView(height=90, spacing=4)

    def refresh_history():
        recent = history[:10]
        if not recent:
            history_list.controls = [ft.Text("هنوز محاسبه‌ای ثبت نشده است.", size=12)]
        else:
            history_list.controls = [
                ft.Text(
                    f"{entry['name']} | {entry['volume_ml']} mL ← {entry['powder_grams']} g | {entry['time']}",
                    size=12,
                )
                for entry in recent
            ]
        page.update()

    def save_calculation(e):
        item = selected["item"]
        if item is None:
            status_text.value = "ابتدا یک محیط کشت انتخاب کن."
            page.update()
            return

        raw_volume = (volume_input.value or "").strip().replace("٫", ".")
        try:
            volume_ml = Decimal(raw_volume)
        except InvalidOperation:
            status_text.value = "برای ثبت، حجم معتبر وارد کن."
            page.update()
            return

        if not volume_ml.is_finite() or volume_ml <= 0:
            status_text.value = "برای ثبت، حجم باید بزرگ‌تر از صفر باشد."
            page.update()
            return

        powder_grams = item["grams_per_liter"] * volume_ml / Decimal("1000")
        new_entry = {
            "name": item["name"],
            "volume_ml": show_number(volume_ml),
            "powder_grams": show_number(powder_grams),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        updated_history = [new_entry] + history[:49]
        try:
            save_json(HISTORY_FILE, updated_history)
        except OSError as error:
            status_text.value = f"ثبت تاریخچه انجام نشد: {error}"
            page.update()
            return

        history[:] = updated_history
        refresh_history()
        status_text.value = "محاسبه در تاریخچه ثبت شد."
        page.update()

    filter_media()
    refresh_history()

    calc_view = ft.Column(
        spacing=10,
        controls=[
            add_form,
            status_text,
            search_input,
            match_count,
            media_list,
            selected_info,
            volume_input,
            result_box,
            ft.Row(
                controls=[
                    ft.Text("ثبت این محاسبه در تاریخچه"),
                    ft.IconButton(
                        icon=ft.Icons.SAVE,
                        tooltip="ثبت محاسبه",
                        on_click=save_calculation,
                    ),
                ]
            ),
            ft.Text("۱۰ محاسبهٔ اخیر", weight=ft.FontWeight.BOLD),
            history_list,
        ],
    )

    # --- تب دوم: دفترچه آزمایشگاه ---
    nb_status_text = ft.Text("", size=12)
    nb_media_name = ft.TextField(
        label="Product Name / نام محصول", hint_text="مثلاً: Nutrient Agar"
    )
    nb_amount = ft.TextField(
        label="مقدار و واحد / Amount & Unit", hint_text="مثلاً: 500 mL"
    )
    nb_date = ft.TextField(
        label="تاریخ ساخت / Prep Date", value=get_current_jalali_date()
    )
    nb_ph = ft.TextField(label="pH نهایی / Final pH", hint_text="مثلاً: 7.2")
    nb_prepared_by = ft.TextField(
        label="تهیه‌کننده / Prepared By", hint_text="نام فرد یا تیم"
    )
    nb_location = ft.TextField(
        label="محل نگهداری / Storage", hint_text="مثلاً: یخچال ۲"
    )
    nb_conditions = ft.TextField(label="شرایط نگهداری", hint_text="مثلاً: ۴ درجه")
    nb_batch = ft.TextField(label="کد بچ یا لات", hint_text="B2026-01")
    nb_notes = ft.TextField(
        label="توضیحات و یادداشت", hint_text="...", multiline=True, min_lines=2
    )

    notebook_list = ft.ListView(height=240, spacing=8)
    notebook_search = ft.TextField(
        label="جست‌وجو در سوابق دفترچه", hint_text="نام محیط، تاریخ، لات، تهیه‌کننده..."
    )

    def refresh_notebook_view(e=None):
        query = (notebook_search.value or "").strip().casefold()
        filtered_entries = [
            (idx, entry)
            for idx, entry in enumerate(notebook_entries)
            if not query or query in " ".join(str(v) for v in entry.values()).casefold()
        ]

        if not notebook_entries:
            notebook_list.controls = [ft.Text("هنوز رکوردی ثبت نشده است.", size=12)]
        elif not filtered_entries:
            notebook_list.controls = [ft.Text("رکوردی با این عبارت پیدا نشد.", size=12)]
        else:
            cards = []
            for idx, entry in filtered_entries:
                title = entry.get("media_name") or f"ثبت #{len(notebook_entries) - idx}"
                details = []
                for k, label in [
                    ("amount", "مقدار"),
                    ("date", "تاریخ"),
                    ("ph", "pH"),
                    ("prepared_by", "تهیه‌کننده"),
                    ("location", "محل"),
                    ("batch", "لات"),
                    ("notes", "یادداشت"),
                ]:
                    if entry.get(k):
                        details.append(f"{label}: {entry[k]}")

                cards.append(
                    ft.Card(
                        content=ft.Container(
                            padding=10,
                            content=ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(
                                                title,
                                                weight=ft.FontWeight.BOLD,
                                                size=13,
                                                expand=True,
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_400,
                                                tooltip="حذف این رکورد",
                                                on_click=lambda e, r_idx=idx: delete_notebook_entry(
                                                    r_idx
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        (
                                            " | ".join(details)
                                            if details
                                            else "بدون جزئیات"
                                        ),
                                        size=11,
                                    ),
                                ],
                            ),
                        )
                    )
                )
            notebook_list.controls = cards
        page.update()

    notebook_search.on_change = refresh_notebook_view

    def delete_notebook_entry(index):
        if index < 0 or index >= len(notebook_entries):
            return
        updated_entries = notebook_entries.copy()
        del updated_entries[index]
        try:
            save_json(NOTEBOOK_FILE, updated_entries)
        except OSError as err:
            nb_status_text.value = f"خطا در حذف: {err}"
            page.update()
            return
        notebook_entries[:] = updated_entries
        nb_status_text.value = "رکورد حذف شد."
        refresh_notebook_view()

    def save_notebook_entry(e):
        entry = {
            "media_name": (nb_media_name.value or "").strip(),
            "amount": (nb_amount.value or "").strip(),
            "date": (nb_date.value or "").strip(),
            "ph": (nb_ph.value or "").strip(),
            "prepared_by": (nb_prepared_by.value or "").strip(),
            "location": (nb_location.value or "").strip(),
            "conditions": (nb_conditions.value or "").strip(),
            "batch": (nb_batch.value or "").strip(),
            "notes": (nb_notes.value or "").strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        notebook_entries.insert(0, entry)
        try:
            save_json(NOTEBOOK_FILE, notebook_entries)
            nb_status_text.value = "با موفقیت ثبت شد."
            nb_media_name.value = ""
            nb_amount.value = ""
            nb_ph.value = ""
            nb_prepared_by.value = ""
            nb_location.value = ""
            nb_conditions.value = ""
            nb_batch.value = ""
            nb_notes.value = ""
            refresh_notebook_view()
        except OSError as err:
            nb_status_text.value = f"خطا: {err}"
            page.update()

    save_notebook_btn = ft.Container(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.BOOKMARK_ADD, color=ft.Colors.WHITE, size=18),
                ft.Text(
                    "ثبت در دفترچه", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.BLUE_600,
        border_radius=8,
        padding=10,
        on_click=save_notebook_entry,
    )

    inv_mat_name = ft.TextField(
        label="نام ماده (مثلاً مخمر، آگار، اتانول)", hint_text="Agar"
    )
    min_stock_mat = ft.TextField(label="نام ماده برای حداقل موجودی", hint_text="Agar")
    recipe_name_in = ft.TextField(
        label="نام دستور / محصول نهایی", hint_text="Nutrient Broth"
    )
    recipe_item_mat = ft.TextField(label="نام ماده اولیه", hint_text="Peptone")
    prod_recipe_name = ft.TextField(
        label="نام دستور انتخابی برای ساخت", hint_text="Nutrient Broth"
    )

    suggestion_lists = {}

    def name_suggestions():
        names = []
        for entry in notebook_entries:
            if isinstance(entry, dict):
                names.append(str(entry.get("media_name", "")).strip())

        for batch in inv_data.get("batches", []):
            if isinstance(batch, dict):
                names.append(str(batch.get("material", "")).strip())

        min_stocks = inv_data.get("min_stocks", {})
        if isinstance(min_stocks, dict):
            for val in min_stocks.values():
                if isinstance(val, dict):
                    names.append(str(val.get("name", "")).strip())
                elif isinstance(val, str):
                    names.append(val.strip())
        elif isinstance(min_stocks, list):
            for item in min_stocks:
                if isinstance(item, dict):
                    names.append(str(item.get("name", "")).strip())
                elif isinstance(item, str):
                    names.append(item.strip())

        for recipe in inv_data.get("recipes", []):
            if not isinstance(recipe, dict):
                continue
            names.append(str(recipe.get("name", "")).strip())
            for ingredient in recipe.get("ingredients", []):
                if isinstance(ingredient, dict):
                    names.append(str(ingredient.get("material", "")).strip())

        for item in media:
            if isinstance(item, dict):
                names.append(str(item.get("name", "")).strip())

        unique = []
        seen = set()
        for name in names:
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                unique.append(name)
        return unique

    def refresh_name_suggestions(field_key, field, suggestions_list):
        query = (field.value or "").strip().casefold()
        matches = [
            name
            for name in name_suggestions()
            if query and name.casefold().startswith(query)
        ][:6]
        suggestions_list.controls = [
            ft.ListTile(
                title=ft.Text(name),
                on_click=lambda e, selected=name: select_name_suggestion(
                    field_key, field, suggestions_list, selected
                ),
            )
            for name in matches
        ]
        suggestions_list.visible = bool(matches)

    def select_name_suggestion(field_key, field, suggestions_list, selected):
        field.value = selected
        suggestions_list.visible = False
        suggestions_list.controls.clear()
        page.update()

    for field_key, field in [
        ("nb_media_name", nb_media_name),
        ("inv_mat_name", inv_mat_name),
        ("min_stock_mat", min_stock_mat),
        ("recipe_name_in", recipe_name_in),
        ("recipe_item_mat", recipe_item_mat),
        ("prod_recipe_name", prod_recipe_name),
    ]:
        suggestions = ft.ListView(height=180, spacing=0, visible=False)
        suggestion_lists[field_key] = suggestions
        field.on_change = lambda e, key=field_key, target=field, listing=suggestions: refresh_name_suggestions(
            key, target, listing
        )

    notebook_view = ft.Column(
        visible=False,
        spacing=10,
        controls=[
            ft.Text("ثبت گزارش ساخت محیط کشت", weight=ft.FontWeight.BOLD, size=14),
            nb_status_text,
            nb_media_name,
            suggestion_lists["nb_media_name"],
            nb_amount,
            nb_date,
            nb_ph,
            nb_prepared_by,
            nb_location,
            nb_conditions,
            nb_batch,
            nb_notes,
            save_notebook_btn,
            ft.Divider(),
            ft.Text("سوابق دفترچه آزمایشگاه", weight=ft.FontWeight.BOLD, size=13),
            notebook_search,
            notebook_list,
        ],
    )

    refresh_notebook_view()

    # --- تب سوم: انبار و اعلانات (طراحی عمودی برای جلوگیری از به هم ریختگی) ---
    inv_status_text = ft.Text("", size=12)

    alerts_column = ft.Column(spacing=6)
    alerts_badge = ft.Text("۰ هشدار فعال", size=12, weight=ft.FontWeight.BOLD)

    batches_list = ft.ListView(height=180, spacing=6)
    purchase_list = ft.ListView(height=120, spacing=4)
    recipes_list = ft.ListView(height=140, spacing=6)

    # فیلدهای انبار (به صورت عمودی برای جلوگیری از تداخل در موبایل)
    inv_amount = ft.TextField(
        label="مقدار موجودی", hint_text="500", keyboard_type=ft.KeyboardType.NUMBER
    )
    inv_unit = ft.TextField(label="واحد شمارش (g, mL, kg, L, بسته)", hint_text="g")
    inv_expiry = ft.TextField(label="تاریخ انقضا (شمسی)", hint_text="1404/05/20")
    inv_batch_no = ft.TextField(label="کد بچ یا لات", hint_text="LOT-982")
    inv_supplier = ft.TextField(label="تأمین‌کننده یا برند", hint_text="مرک / کیولب")

    min_stock_val = ft.TextField(
        label="حداقل موجودی مجاز", hint_text="100", keyboard_type=ft.KeyboardType.NUMBER
    )
    min_stock_unit = ft.TextField(label="واحد", hint_text="g")

    recipe_item_amt = ft.TextField(
        label="مقدار مصرف در ۱ بار", hint_text="5", keyboard_type=ft.KeyboardType.NUMBER
    )
    recipe_item_unit = ft.TextField(label="واحد مصرف", hint_text="g")
    recipe_draft_items = []
    recipe_draft_display = ft.Text("اجزای دستور ثبت نشده‌اند.", size=12)

    prod_multiplier = ft.TextField(
        label="ضریب ساخت (چند برابر؟)", value="1", keyboard_type=ft.KeyboardType.NUMBER
    )
    prod_prepared_by = ft.TextField(
        label="تهیه‌کننده (ثبت در دفترچه)", hint_text="نام کارشناس"
    )
    prod_location = ft.TextField(label="محل نگهداری محصول نهایی", hint_text="یخچال")
    prod_batch_code = ft.TextField(label="کد لات محصول تولیدی", hint_text="B2026-01")

    def get_aggregated_stock():
        totals = {}
        for b in inv_data["batches"]:
            mat = b["material"].strip()
            unit = b.get("unit", "").strip().lower()
            key = (mat.casefold(), unit)
            try:
                amt = Decimal(str(b.get("amount", "0")))
            except InvalidOperation:
                amt = Decimal("0")
            if key not in totals:
                totals[key] = {"name": mat, "unit": unit, "amount": Decimal("0")}
            totals[key]["amount"] += amt
        return totals

    def update_notifications_and_views():
        today = date.today()
        alerts = []
        purchases = []

        for b in inv_data["batches"]:
            mat = b.get("material", "نامشخص")
            amt = b.get("amount", "0")
            unit = b.get("unit", "")
            exp_str = b.get("expiry", "").strip()
            batch_id = b.get("batch_no") or "بدون لات"

            if not exp_str:
                alerts.append(
                    {
                        "level": "info",
                        "title": f"بدون تاریخ انقضا: {mat}",
                        "desc": f"بچ {batch_id} تاریخ انقضا ندارد.",
                    }
                )
            else:
                exp_date = parse_jalali_date(exp_str)
                if exp_date is None:
                    alerts.append(
                        {
                            "level": "warning",
                            "title": f"فرمت تاریخ نامعتبر: {mat}",
                            "desc": f"تاریخ '{exp_str}' در بچ {batch_id} صحیح نیست.",
                        }
                    )
                else:
                    days_left = (exp_date - today).days
                    if days_left < 0:
                        alerts.append(
                            {
                                "level": "danger",
                                "title": f"⛔ منقضی شده: {mat}",
                                "desc": f"بچ {batch_id} منقضی شده و مصرف آن ممنوع است!",
                            }
                        )
                    elif days_left <= 2:
                        alerts.append(
                            {
                                "level": "danger",
                                "title": f"⚠️ هشدار انقضا: {mat}",
                                "desc": f"{days_left} روز تا انقضای بچ {batch_id} مانده.",
                            }
                        )
                    elif days_left <= 7:
                        alerts.append(
                            {
                                "level": "warning",
                                "title": f"نزدیک به انقضا: {mat}",
                                "desc": f"{days_left} روز تا انقضا باقی است.",
                            }
                        )

        totals = get_aggregated_stock()
        for min_key, min_info in inv_data.get("min_stocks", {}).items():
            mat_name = min_info.get("name", min_key)
            unit = min_info.get("unit", "").strip().lower()
            try:
                min_threshold = Decimal(str(min_info.get("amount", "0")))
            except InvalidOperation:
                min_threshold = Decimal("0")

            lookup_key = (mat_name.casefold(), unit)
            current_amt = totals.get(lookup_key, {}).get("amount", Decimal("0"))

            if current_amt <= min_threshold:
                deficit = (min_threshold - current_amt) + (
                    min_threshold * Decimal("0.2")
                )
                if deficit <= 0:
                    deficit = min_threshold
                alerts.append(
                    {
                        "level": "warning",
                        "title": f"کسری موجودی: {mat_name}",
                        "desc": f"موجودی فعلی ({show_number(current_amt)} {unit}) از حداقل مجاز کمتر است.",
                    }
                )
                purchases.append(
                    {
                        "name": mat_name,
                        "current": current_amt,
                        "min": min_threshold,
                        "suggested": deficit,
                        "unit": unit,
                    }
                )

        alerts_badge.value = f"{len(alerts)} اعلان و هشدار فعال"
        alerts_column.controls.clear()
        if not alerts:
            alerts_column.controls.append(
                ft.Text(
                    "هیچ هشدار فعالی وجود ندارد. انبار پایدار است.",
                    size=12,
                    color=ft.Colors.GREEN_700,
                )
            )
        else:
            for alert in alerts:
                is_dark = page.theme_mode == ft.ThemeMode.DARK
                if alert["level"] == "danger":
                    bg = "#3E1418" if is_dark else ft.Colors.RED_50
                    col = "#FF8A8A" if is_dark else ft.Colors.RED_600
                    text_col = "#FFDADA" if is_dark else None
                elif alert["level"] == "warning":
                    bg = "#3D2800" if is_dark else ft.Colors.AMBER_50
                    col = "#FFD166" if is_dark else ft.Colors.AMBER_700
                    text_col = "#FFECC0" if is_dark else None
                else:
                    bg = "#0D2B45" if is_dark else ft.Colors.BLUE_50
                    col = "#64B5F6" if is_dark else ft.Colors.BLUE_600
                    text_col = "#D1E8FF" if is_dark else None
                alerts_column.controls.append(
                    ft.Container(
                        padding=8,
                        border_radius=6,
                        bgcolor=bg,
                        content=ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Icon(
                                    (
                                        ft.Icons.WARNING_AMBER_ROUNDED
                                        if alert["level"] != "info"
                                        else ft.Icons.INFO_OUTLINE
                                    ),
                                    color=col,
                                    size=16,
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            alert["title"],
                                            weight=ft.FontWeight.BOLD,
                                            size=11,
                                            color=text_col,
                                        ),
                                        ft.Text(alert["desc"], size=10, color=text_col),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        purchase_list.controls.clear()
        if not purchases:
            purchase_list.controls.append(
                ft.Text("تمام اقلام در حد نصاب هستند.", size=11)
            )
        else:
            for p in purchases:
                purchase_list.controls.append(
                    ft.ListTile(
                        dense=True,
                        leading=ft.Icon(
                            ft.Icons.SHOPPING_CART_OUTLINED,
                            color=ft.Colors.AMBER_800,
                            size=16,
                        ),
                        title=ft.Text(
                            f"{p['name']} ({p['unit']})",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                        subtitle=ft.Text(
                            f"موجودی: {show_number(p['current'])} | حداقل: {show_number(p['min'])} | پیشنهاد خرید: {show_number(p['suggested'])}",
                            size=10,
                        ),
                    )
                )

        batches_list.controls.clear()
        if not inv_data["batches"]:
            batches_list.controls.append(ft.Text("هنوز بسته‌ای ثبت نشده است.", size=12))
        else:
            for idx, b in enumerate(inv_data["batches"]):
                batches_list.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                f"{b['material']} — {b['amount']} {b['unit']}",
                                                weight=ft.FontWeight.BOLD,
                                                size=12,
                                            ),
                                            ft.Text(
                                                f"انقضا: {b.get('expiry') or '—'} | لات: {b.get('batch_no') or '—'}",
                                                size=10,
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        tooltip="حذف",
                                        on_click=lambda e, b_idx=idx: delete_inventory_batch(
                                            b_idx
                                        ),
                                    ),
                                ],
                            ),
                        )
                    )
                )

        recipes_list.controls.clear()
        if not inv_data["recipes"]:
            recipes_list.controls.append(ft.Text("هنوز دستوری ثبت نشده است.", size=12))
        else:
            for r_idx, r in enumerate(inv_data["recipes"]):
                items_desc = " + ".join(
                    [
                        f"{i['amount']} {i['unit']} {i['material']}"
                        for i in r.get("ingredients", [])
                    ]
                )
                recipes_list.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                r["name"],
                                                weight=ft.FontWeight.BOLD,
                                                size=12,
                                            ),
                                            ft.Text(
                                                items_desc,
                                                size=10,
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        on_click=lambda e, idx=r_idx: delete_recipe(
                                            idx
                                        ),
                                    ),
                                ],
                            ),
                        )
                    )
                )
        page.update()

    def add_new_batch(e):
        mat = (inv_mat_name.value or "").strip()
        raw_amt = (inv_amount.value or "").strip().replace("٫", ".")
        unit = (inv_unit.value or "").strip()
        exp = (inv_expiry.value or "").strip()
        batch_no = (inv_batch_no.value or "").strip()
        supplier = (inv_supplier.value or "").strip()

        if not mat or not raw_amt or not unit:
            inv_status_text.value = "نام ماده، مقدار و واحد الزامی است."
            page.update()
            return

        try:
            amt_dec = Decimal(raw_amt)
            if amt_dec <= 0:
                raise InvalidOperation()
        except InvalidOperation:
            inv_status_text.value = "مقدار باید عددی مثبت باشد."
            page.update()
            return

        new_batch = {
            "material": mat,
            "amount": show_number(amt_dec),
            "unit": unit,
            "expiry": exp,
            "batch_no": batch_no,
            "supplier": supplier,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        inv_data["batches"].append(new_batch)
        inv_data["movements"].append(
            {
                "type": "IN",
                "material": mat,
                "amount": show_number(amt_dec),
                "unit": unit,
                "batch_no": batch_no,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        try:
            save_json(INVENTORY_FILE, inv_data)
            inv_status_text.value = f"ماده {mat} افزوده شد."
            inv_mat_name.value = ""
            inv_amount.value = ""
            inv_unit.value = ""
            inv_expiry.value = ""
            inv_batch_no.value = ""
            inv_supplier.value = ""
            update_notifications_and_views()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    def delete_inventory_batch(idx):
        if idx < 0 or idx >= len(inv_data["batches"]):
            return
        inv_data["batches"].pop(idx)
        try:
            save_json(INVENTORY_FILE, inv_data)
            inv_status_text.value = "بسته حذف شد."
            update_notifications_and_views()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    def set_min_stock(e):
        mat = (min_stock_mat.value or "").strip()
        raw_amt = (min_stock_val.value or "").strip().replace("٫", ".")
        unit = (min_stock_unit.value or "").strip()
        if not mat or not raw_amt:
            inv_status_text.value = "نام و حداقل موجودی الزامی است."
            page.update()
            return
        try:
            amt_dec = Decimal(raw_amt)
        except InvalidOperation:
            inv_status_text.value = "مقدار باید عدد باشد."
            page.update()
            return

        key = f"{mat.casefold()}_{unit.casefold()}"
        inv_data["min_stocks"][key] = {
            "name": mat,
            "amount": show_number(amt_dec),
            "unit": unit,
        }
        try:
            save_json(INVENTORY_FILE, inv_data)
            inv_status_text.value = "حداقل موجودی ذخیره شد."
            min_stock_mat.value = ""
            min_stock_val.value = ""
            min_stock_unit.value = ""
            update_notifications_and_views()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    def add_ingredient_to_draft(e):
        mat = (recipe_item_mat.value or "").strip()
        raw_amt = (recipe_item_amt.value or "").strip().replace("٫", ".")
        unit = (recipe_item_unit.value or "").strip()
        if not mat or not raw_amt or not unit:
            inv_status_text.value = "اطلاعات جزء فرمول کامل نیست."
            page.update()
            return
        try:
            amt_dec = Decimal(raw_amt)
        except InvalidOperation:
            inv_status_text.value = "مقدار مصرف باید عدد باشد."
            page.update()
            return

        recipe_draft_items.append(
            {"material": mat, "amount": show_number(amt_dec), "unit": unit}
        )
        recipe_item_mat.value = ""
        recipe_item_amt.value = ""
        recipe_item_unit.value = ""
        recipe_draft_display.value = "اجزا: " + " + ".join(
            [f"{i['amount']} {i['unit']} {i['material']}" for i in recipe_draft_items]
        )
        page.update()

    def save_recipe_definition(e):
        name = (recipe_name_in.value or "").strip()
        if not name or not recipe_draft_items:
            inv_status_text.value = "نام دستور و حداقل یک جزء الزامی است."
            page.update()
            return
        inv_data["recipes"].append(
            {"name": name, "ingredients": list(recipe_draft_items)}
        )
        try:
            save_json(INVENTORY_FILE, inv_data)
            inv_status_text.value = f"دستور '{name}' ذخیره شد."
            recipe_name_in.value = ""
            recipe_draft_items.clear()
            recipe_draft_display.value = "اجزا ثبت نشده‌اند."
            update_notifications_and_views()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    def delete_recipe(idx):
        if idx < 0 or idx >= len(inv_data["recipes"]):
            return
        inv_data["recipes"].pop(idx)
        try:
            save_json(INVENTORY_FILE, inv_data)
            inv_status_text.value = "دستور حذف شد."
            update_notifications_and_views()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    def execute_production(e):
        target_name = (prod_recipe_name.value or "").strip().casefold()
        raw_mult = (prod_multiplier.value or "").strip().replace("٫", ".")
        if not target_name:
            inv_status_text.value = "نام دستور را وارد کنید."
            page.update()
            return
        try:
            multiplier = Decimal(raw_mult)
            if multiplier <= 0:
                raise InvalidOperation()
        except InvalidOperation:
            inv_status_text.value = "ضریب ساخت نامعتبر است."
            page.update()
            return

        recipe = next(
            (
                r
                for r in inv_data["recipes"]
                if r["name"].strip().casefold() == target_name
            ),
            None,
        )
        if not recipe:
            inv_status_text.value = "دستوری با این نام پیدا نشد."
            page.update()
            return

        today = date.today()
        needed_items = [
            {
                "material": i["material"].strip(),
                "unit": i["unit"].strip().lower(),
                "amount": Decimal(str(i["amount"])) * multiplier,
            }
            for i in recipe.get("ingredients", [])
        ]

        valid_batches = []
        for idx, b in enumerate(inv_data["batches"]):
            exp_date = parse_jalali_date(b.get("expiry", ""))
            is_expired = bool(exp_date and exp_date < today)
            valid_batches.append(
                {
                    "idx": idx,
                    "material": b["material"].strip(),
                    "unit": b.get("unit", "").strip().lower(),
                    "amount": Decimal(str(b.get("amount", "0"))),
                    "exp_date": exp_date,
                    "is_expired": is_expired,
                }
            )

        valid_batches.sort(
            key=lambda x: (1 if x["exp_date"] is None else 0, x["exp_date"] or date.max)
        )

        planned_deductions = []
        for req in needed_items:
            req_name, req_unit, req_amt = req["material"], req["unit"], req["amount"]
            matching = [
                b
                for b in valid_batches
                if b["material"].casefold() == req_name.casefold()
                and b["unit"] == req_unit
            ]
            expired_present = any(b["is_expired"] for b in matching)
            usable = [b for b in matching if not b["is_expired"]]
            usable_total = sum(b["amount"] for b in usable)

            if usable_total < req_amt:
                err = f"کسری موجودی برای {req_name}! نیاز: {show_number(req_amt)} {req_unit} | قابل مصرف: {show_number(usable_total)}."
                if expired_present:
                    err += " (مواد منقضی‌شده قابل مصرف نیستند)"
                inv_status_text.value = err
                page.update()
                return

            rem = req_amt
            for b in usable:
                if rem <= 0:
                    break
                deduct = min(b["amount"], rem)
                b["amount"] -= deduct
                rem -= deduct
                planned_deductions.append(
                    {
                        "batch_idx": b["idx"],
                        "deduct": deduct,
                        "material": req_name,
                        "unit": req_unit,
                    }
                )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for ded in planned_deductions:
            orig = inv_data["batches"][ded["batch_idx"]]
            orig["amount"] = show_number(Decimal(str(orig["amount"])) - ded["deduct"])
            inv_data["movements"].append(
                {
                    "type": "OUT_RECIPE",
                    "material": ded["material"],
                    "amount": show_number(ded["deduct"]),
                    "unit": ded["unit"],
                    "time": now_str,
                }
            )

        inv_data["batches"] = [
            b for b in inv_data["batches"] if Decimal(str(b.get("amount", "0"))) > 0
        ]

        prod_lot = (
            prod_batch_code.value or ""
        ).strip() or f"PROD-{datetime.now().strftime('%m%d%H%M')}"
        new_log = {
            "media_name": f"تولید: {recipe['name']}",
            "amount": f"{show_number(multiplier)} سری",
            "date": get_current_jalali_date(),
            "ph": "—",
            "prepared_by": (prod_prepared_by.value or "").strip() or "اپراتور",
            "location": (prod_location.value or "").strip() or "انبار",
            "conditions": "—",
            "batch": prod_lot,
            "notes": f"کسر خودکار مواد با ضریب {multiplier}",
            "timestamp": now_str,
        }
        notebook_entries.insert(0, new_log)

        try:
            save_json(INVENTORY_FILE, inv_data)
            save_json(NOTEBOOK_FILE, notebook_entries)
            inv_status_text.value = "تولید با موفقیت انجام و از انبار کسر شد."
            prod_recipe_name.value = ""
            prod_multiplier.value = "1"
            prod_batch_code.value = ""
            update_notifications_and_views()
            refresh_notebook_view()
        except OSError as err:
            inv_status_text.value = f"خطا: {err}"
            page.update()

    inventory_view = ft.Column(
        visible=False,
        spacing=12,
        controls=[
            ft.Text(
                "مرکز اعلانات و هشدارهای انبار", weight=ft.FontWeight.BOLD, size=14
            ),
            alerts_badge,
            alerts_column,
            ft.Divider(),
            ft.Text("ثبت بسته جدید در انبار", weight=ft.FontWeight.BOLD, size=14),
            inv_status_text,
            inv_mat_name,
            suggestion_lists["inv_mat_name"],
            inv_amount,
            inv_unit,
            inv_expiry,
            inv_batch_no,
            inv_supplier,
            ft.Container(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ADD_BOX, color=ft.Colors.WHITE, size=18),
                        ft.Text(
                            "افزودن به انبار",
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.GREEN_700,
                border_radius=8,
                padding=10,
                on_click=add_new_batch,
            ),
            ft.Divider(),
            ft.Text("تنظیم حداقل موجودی", weight=ft.FontWeight.BOLD, size=14),
            min_stock_mat,
            suggestion_lists["min_stock_mat"],
            min_stock_val,
            min_stock_unit,
            ft.Container(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.NOTIFICATION_ADD, color=ft.Colors.WHITE, size=18
                        ),
                        ft.Text(
                            "ثبت آستانه هشدار",
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.BLUE_GREY_700,
                border_radius=8,
                padding=10,
                on_click=set_min_stock,
            ),
            ft.Divider(),
            ft.Text("فهرست خرید پیشنهادی", weight=ft.FontWeight.BOLD, size=14),
            purchase_list,
            ft.Divider(),
            ft.Text("بسته‌های موجود در انبار", weight=ft.FontWeight.BOLD, size=14),
            batches_list,
            ft.Divider(),
            ft.Text("تعریف دستور ساخت (فرمول)", weight=ft.FontWeight.BOLD, size=14),
            recipe_name_in,
            suggestion_lists["recipe_name_in"],
            recipe_item_mat,
            suggestion_lists["recipe_item_mat"],
            recipe_item_amt,
            recipe_item_unit,
            ft.Container(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE, size=18),
                        ft.Text(
                            "افزودن جزء به فرمول",
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.BLUE_600,
                border_radius=8,
                padding=8,
                on_click=add_ingredient_to_draft,
            ),
            recipe_draft_display,
            ft.Container(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.SAVE, color=ft.Colors.WHITE, size=18),
                        ft.Text(
                            "ذخیره دستور ساخت",
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.TEAL_700,
                border_radius=8,
                padding=10,
                on_click=save_recipe_definition,
            ),
            ft.Text("دستورهای ثبت‌شده:", weight=ft.FontWeight.BOLD, size=12),
            recipes_list,
            ft.Divider(),
            ft.Text("اجرای ساخت و کسر از انبار", weight=ft.FontWeight.BOLD, size=14),
            prod_recipe_name,
            suggestion_lists["prod_recipe_name"],
            prod_multiplier,
            prod_prepared_by,
            prod_location,
            prod_batch_code,
            ft.Container(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=18
                        ),
                        ft.Text(
                            "تأیید ساخت و کسر خودکار",
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.INDIGO_700,
                border_radius=8,
                padding=12,
                on_click=execute_production,
            ),
        ],
    )

    update_notifications_and_views()

    def on_nav_change(e):
        idx = e.control.selected_index
        calc_view.visible = idx == 0
        notebook_view.visible = idx == 1
        inventory_view.visible = idx == 2
        add_btn.visible = idx == 0
        if idx == 2:
            update_notifications_and_views()
        page.update()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.CALCULATE_OUTLINED,
                selected_icon=ft.Icons.CALCULATE,
                label="محاسبه‌گر",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.MENU_BOOK_OUTLINED,
                selected_icon=ft.Icons.MENU_BOOK,
                label="دفترچه",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                selected_icon=ft.Icons.INVENTORY_2,
                label="انبار",
            ),
        ],
    )

    page.navigation_bar = nav_bar
    page.add(
        ft.SafeArea(
            expand=True,
            rtl=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(
                                "دستیار آزمایشگاه کشت",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Row(controls=[add_btn, theme_btn], spacing=0),
                        ],
                    ),
                    calc_view,
                    notebook_view,
                    inventory_view,
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.SEND_ROUNDED,
                                size=16,
                                color=ft.Colors.BLUE_400,  # یا کد رنگ دلخواه: "#0088cc"
                            ),
                            ft.Text(
                                "Design & Development by @AbolfazlllMoradi",
                                size=12,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,  # فاصله ملایم بین آیکون و متن
                    ),
                ],
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
