import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import flet as ft

DATA_FILE = Path(__file__).resolve().parent / "media_data.json"

# در اجرای Flet از فضای دائمی خود برنامه استفاده می‌شود.
# مسیر دوم برای اجرای مستقیم با python main.py روی کامپیوتر است.
USER_DATA_DIR = Path(
    os.getenv("FLET_APP_STORAGE_DATA") or (Path.home() / ".lab_media_calc")
)
CUSTOM_FILE = USER_DATA_DIR / "custom_media.json"
HISTORY_FILE = USER_DATA_DIR / "history.json"


def load_media(path=DATA_FILE, missing_ok=False):
    """Read and validate culture media from a JSON file."""
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
    """Read previously saved calculations."""
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


def save_json(path, records):
    """Save JSON without writing to the bundled media database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)

    temporary_path.replace(path)


def show_number(number):
    """Display a Decimal without unnecessary trailing zeros."""
    return format(number.normalize(), "f")


def main(page: ft.Page):
    page.title = "محاسبه‌گر محیط کشت"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 14

    # Desktop preview
    page.window.width = 390
    page.window.height = 780
    page.window.resizable = True

    try:
        media = load_media()
        custom_media = load_media(CUSTOM_FILE, missing_ok=True)
        history = load_history()
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

    # دکمه و تابع تغییر تم؛ مطابق کد فعلی تو
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

    theme_btn.on_click = toggle_theme

    def calculate(e=None):
        item = selected["item"]
        if item is None:
            return

        raw_volume = (volume_input.value or "").strip().replace("٫", ".")

        if not raw_volume:
            result_text.value = "مقدار پودر: —"
            return

        try:
            volume_ml = Decimal(raw_volume)
        except InvalidOperation:
            result_text.value = "لطفاً حجم را به‌صورت عدد وارد کن."
            return

        if not volume_ml.is_finite() or volume_ml <= 0:
            result_text.value = "حجم باید عددی بزرگ‌تر از صفر باشد."
            return

        powder_grams = item["grams_per_liter"] * volume_ml / Decimal("1000")
        result_text.value = f"مقدار پودر: {show_number(powder_grams)} گرم"

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

    # ارتفاع ثابت باعث می‌شود هم فهرست و هم کل صفحه قابل پیمایش باشند.
    media_list = ft.ListView(height=220, spacing=4)
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

    search_input = ft.TextField(
        label="جست‌وجوی نام محیط کشت",
        hint_text="مثلاً EC یا Agar",
        on_change=filter_media,
    )

    # --- قابلیت جدید: افزودن محیط کشت دلخواه ---

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
        spacing=5,
        controls=[
            new_name_input,
            new_grams_input,
        ],
    )

    def toggle_add_form(e):
        add_form.visible = not add_form.visible
        status_text.value = ""

    def add_custom_medium(e):
        name = (new_name_input.value or "").strip()
        raw_grams = (new_grams_input.value or "").strip().replace("٫", ".")

        if not name:
            status_text.value = "نام محیط کشت جدید را وارد کن."
            return

        if any(item["name"].casefold() == name.casefold() for item in media):
            status_text.value = "محیط کشتی با این نام از قبل وجود دارد."
            return

        try:
            grams_per_liter = Decimal(raw_grams)
        except InvalidOperation:
            status_text.value = "مقدار گرم در لیتر باید عدد باشد."
            return

        if not grams_per_liter.is_finite() or grams_per_liter <= 0:
            status_text.value = "مقدار گرم در لیتر باید بزرگ‌تر از صفر باشد."
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

    # --- قابلیت جدید: تاریخچهٔ محاسبات ---

    history_list = ft.ListView(height=110, spacing=4)

    def refresh_history():
        recent = history[:10]

        if not recent:
            history_list.controls = [ft.Text("هنوز محاسبه‌ای ثبت نشده است.", size=12)]
            return

        history_list.controls = [
            ft.Text(
                f"{entry['name']} | {entry['volume_ml']} mL"
                f" ← {entry['powder_grams']} g"
                f" | {entry['time']}",
                size=12,
            )
            for entry in recent
        ]

    def save_calculation(e):
        item = selected["item"]

        if item is None:
            status_text.value = "ابتدا یک محیط کشت انتخاب کن."
            return

        raw_volume = (volume_input.value or "").strip().replace("٫", ".")

        try:
            volume_ml = Decimal(raw_volume)
        except InvalidOperation:
            status_text.value = "برای ثبت، حجم معتبر وارد کن."
            return

        if not volume_ml.is_finite() or volume_ml <= 0:
            status_text.value = "برای ثبت، حجم باید بزرگ‌تر از صفر باشد."
            return

        powder_grams = item["grams_per_liter"] * volume_ml / Decimal("1000")

        new_entry = {
            "name": item["name"],
            "volume_ml": show_number(volume_ml),
            "powder_grams": show_number(powder_grams),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # فقط ۵۰ محاسبهٔ آخر در فایل نگهداری می‌شود.
        updated_history = [new_entry] + history[:49]

        try:
            save_json(HISTORY_FILE, updated_history)
        except OSError as error:
            status_text.value = f"ثبت تاریخچه انجام نشد: {error}"
            return

        history[:] = updated_history
        refresh_history()
        status_text.value = "محاسبه در تاریخچه ثبت شد."

    filter_media()
    refresh_history()

    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                "محاسبه‌گر محیط کشت",
                size=20,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Row(controls=[add_btn, theme_btn], spacing=0),
        ],
    )

    page.add(
        ft.SafeArea(
            expand=True,
            rtl=True,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                controls=[
                    header_row,
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
            ),
        )
    )


if __name__ == "__main__":
    ft.run(main)
