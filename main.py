import json
import os
from datetime import datetime
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
        raise ValueError("ساختار فایل history.json باید یک لیست باشد.")

    required = {"name", "volume_ml", "powder_grams", "time"}

    for record in records:
        if not isinstance(record, dict) or not required.issubset(record):
            raise ValueError("یکی از رکوردهای history.json معتبر نیست.")

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


def save_json(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)

    temporary_path.replace(path)


def show_number(number):
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

    # --- بخش محاسبه‌گر (دست‌نخورده و بدون تغییر) ---
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
            f"مقدار درج‌شده: "
            f"{show_number(item['grams_per_liter'])} گرم در ۱ لیتر"
        )

        volume_input.disabled = False
        volume_input.value = ""
        result_text.value = "مقدار پودر: —"
        page.update()

    media_list = ft.ListView(height=200, spacing=4)
    match_count = ft.Text(size=12, color=ft.Colors.GREY_700)

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

    history_list = ft.ListView(height=100, spacing=4)

    def refresh_history():
        recent = history[:10]

        if not recent:
            history_list.controls = [ft.Text("هنوز محاسبه‌ای ثبت نشده است.", size=12)]
        else:
            history_list.controls = [
                ft.Text(
                    f"{entry['name']} | {entry['volume_ml']} mL"
                    f" ← {entry['powder_grams']} g"
                    f" | {entry['time']}",
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
        spacing=12,
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
            ft.Text(
                "۱۰ محاسبهٔ اخیر",
                weight=ft.FontWeight.BOLD,
            ),
            history_list,
        ],
    )

    # --- تب دوم: دفترچه آزمایشگاه (با جست‌وجو و امکان حذف سوابق) ---
    nb_status_text = ft.Text("", size=12)

    nb_media_name = ft.TextField(
        label="نام محیط کشت / Medium Name",
        hint_text="مثلاً: Nutrient Agar",
    )
    nb_amount = ft.TextField(
        label="مقدار و واحد / Amount & Unit",
        hint_text="مثلاً: 500 mL",
    )
    nb_date = ft.TextField(
        label="تاریخ ساخت / Prep Date",
        value=get_current_jalali_date(),
    )
    nb_ph = ft.TextField(
        label="pH نهایی / Final pH",
        hint_text="مثلاً: 7.2",
    )
    nb_prepared_by = ft.TextField(
        label="تهیه‌کننده / Prepared By",
        hint_text="نام فرد یا تیم آزمایشگاه",
    )
    nb_location = ft.TextField(
        label="محل نگهداری / Storage Location",
        hint_text="مثلاً: یخچال شماره ۲",
    )
    nb_conditions = ft.TextField(
        label="شرایط نگهداری / Conditions",
        hint_text="مثلاً: ۴ درجه سلسیوس",
    )
    nb_batch = ft.TextField(
        label="کد بچ یا لات / Batch / Lot No",
        hint_text="مثلاً: B2026-01",
    )
    nb_notes = ft.TextField(
        label="توضیحات و یادداشت / Notes",
        hint_text="توضیحات تکمیلی...",
        multiline=True,
        min_lines=2,
    )

    notebook_list = ft.ListView(height=260, spacing=10)

    notebook_search = ft.TextField(
        label="جست‌وجو در سوابق / Search saved records",
        hint_text="نام محیط، تاریخ، pH، تهیه‌کننده، لات، یادداشت...",
    )

    def refresh_notebook_view(e=None):
        query = (notebook_search.value or "").strip().casefold()

        # جست‌وجو در تمام فیلدهای ذخیره‌شدهٔ هر رکورد
        filtered_entries = [
            (idx, entry)
            for idx, entry in enumerate(notebook_entries)
            if not query
            or query in " ".join(str(value) for value in entry.values()).casefold()
        ]

        if not notebook_entries:
            notebook_list.controls = [
                ft.Text(
                    "هنوز رکوردی در دفترچه ثبت نشده است.\nNo records saved yet.",
                    size=12,
                    color=ft.Colors.GREY_600,
                )
            ]
        elif not filtered_entries:
            notebook_list.controls = [ft.Text("رکوردی با این عبارت پیدا نشد.", size=12)]
        else:
            cards = []
            for idx, entry in filtered_entries:
                title = entry.get("media_name") or f"ثبت #{len(notebook_entries) - idx}"
                details = []
                if entry.get("amount"):
                    details.append(f"مقدار: {entry['amount']}")
                if entry.get("date"):
                    details.append(f"تاریخ: {entry['date']}")
                if entry.get("ph"):
                    details.append(f"pH: {entry['ph']}")
                if entry.get("prepared_by"):
                    details.append(f"تهیه‌کننده: {entry['prepared_by']}")
                if entry.get("location"):
                    details.append(f"محل: {entry['location']}")
                if entry.get("batch"):
                    details.append(f"لات: {entry['batch']}")
                if entry.get("conditions"):
                    details.append(f"شرایط: {entry['conditions']}")
                if entry.get("notes"):
                    details.append(f"یادداشت: {entry['notes']}")

                cards.append(
                    ft.Card(
                        content=ft.Container(
                            padding=12,
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(
                                                title,
                                                weight=ft.FontWeight.BOLD,
                                                size=14,
                                                expand=True,
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE,
                                                tooltip="حذف این رکورد",
                                                icon_color=ft.Colors.RED_400,
                                                on_click=lambda e, record_index=idx: delete_notebook_entry(
                                                    record_index
                                                ),
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        (
                                            " | ".join(details)
                                            if details
                                            else "بدون جزئیات ثبت‌شده"
                                        ),
                                        size=12,
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
            nb_status_text.value = f"خطا در حذف رکورد: {err}"
            page.update()
            return

        notebook_entries[:] = updated_entries
        nb_status_text.value = "رکورد با موفقیت حذف شد."
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
            nb_status_text.value = "گزارش با موفقیت در دفترچه ثبت شد / Saved!"
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
            nb_status_text.value = f"خطا در ذخیره دفترچه: {err}"
            page.update()

    save_notebook_btn = ft.Container(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.BOOKMARK_ADD, color=ft.Colors.WHITE, size=18),
                ft.Text(
                    "ثبت در دفترچه / Save to Notebook",
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.BLUE_600,
        border_radius=8,
        padding=12,
        on_click=save_notebook_entry,
    )

    notebook_view = ft.Column(
        visible=False,
        spacing=12,
        controls=[
            ft.Text(
                "ثبت گزارش ساخت محیط کشت / Lab Log Entry",
                weight=ft.FontWeight.BOLD,
                size=15,
            ),
            nb_status_text,
            nb_media_name,
            nb_amount,
            ft.Row(
                controls=[
                    ft.Container(expand=1, content=nb_date),
                    ft.Container(expand=1, content=nb_ph),
                ],
                spacing=10,
            ),
            nb_prepared_by,
            nb_location,
            nb_conditions,
            nb_batch,
            nb_notes,
            ft.Container(height=4),
            save_notebook_btn,
            ft.Divider(),
            ft.Text(
                "سوابق دفترچه آزمایشگاه / Saved Records",
                weight=ft.FontWeight.BOLD,
                size=14,
            ),
            notebook_search,
            notebook_list,
        ],
    )

    refresh_notebook_view()

    def on_nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            calc_view.visible = True
            notebook_view.visible = False
            add_btn.visible = True
        else:
            calc_view.visible = False
            notebook_view.visible = True
            add_btn.visible = False
        page.update()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.CALCULATE_OUTLINED,
                selected_icon=ft.Icons.CALCULATE,
                label="محاسبه‌گر / Calculator",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.MENU_BOOK_OUTLINED,
                selected_icon=ft.Icons.MENU_BOOK,
                label="دفترچه / Lab Log",
            ),
        ],
    )

    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                "دستیار آزمایشگاه کشت",
                size=19,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Row(controls=[add_btn, theme_btn], spacing=0),
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
                    header_row,
                    calc_view,
                    notebook_view,
                    ft.Container(height=10),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=5,
                        controls=[
                            ft.Icon(
                                ft.Icons.SEND_ROUNDED,
                                size=15,
                                color=ft.Colors.BLUE_400,
                            ),
                            ft.Text(
                                "Design & Development by @AbolfazlllMoradi",
                                size=11,
                                color=ft.Colors.GREY_600,
                            ),
                        ],
                    ),
                ],
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
