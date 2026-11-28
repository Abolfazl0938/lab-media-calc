"""Persian process planner and one-shot step timer for Flet 1.0.1.

Integrate with: ft.Tab(text="فرایندها", content=build_process_tab(page))
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import flet as ft

DATA_DIR = Path(os.getenv("FLET_APP_STORAGE_DATA") or (Path.home() / ".lab_media_calc"))
DATA_FILE = DATA_DIR / "process_tab_data.json"
UNITS = {"ثانیه": 1, "دقیقه": 60, "ساعت": 3600}


def _read_data():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                "templates": (
                    data.get("templates", [])
                    if isinstance(data.get("templates"), list)
                    else []
                ),
                "history": (
                    data.get("history", [])
                    if isinstance(data.get("history"), list)
                    else []
                ),
            }
    except (OSError, json.JSONDecodeError):
        pass
    return {"templates": [], "history": []}


def _write_data(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DATA_FILE)


def _dropdown_option(label, value):
    option_type = getattr(getattr(ft, "dropdown", None), "Option", None) or getattr(
        ft, "DropdownOption", None
    )
    return option_type(key=value, text=label) if option_type else value


def _seconds(step):
    value = int(step.get("duration", step.get("minutes", 1)))
    return max(1, value) * UNITS.get(step.get("unit", "دقیقه"), 60)


def _format_time(total_seconds):
    hours, remainder = divmod(max(0, int(total_seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _icon(name, fallback="CHECK"):
    icons = getattr(ft, "Icons", getattr(ft, "icons", None))
    return getattr(icons, name, getattr(icons, fallback, None)) if icons else None


def build_process_tab(page):
    store = _read_data()
    steps = []
    state = {
        "running": False,
        "deadline": None,
        "index": 0,
        "template_id": None,
        "expired": False,
        "generation": 0,
        "history_saved": False,
    }

    # Robust Dark / Light mode detection & safe colors
    def get_colors():
        mode = getattr(page, "theme_mode", None)
        is_dark = (
            mode == ft.ThemeMode.DARK
            or str(mode).lower().endswith("dark")
            or getattr(page, "brightness", None) == ft.Brightness.DARK
        )
        if is_dark:
            return {
                "primary": "#9BB5FF",
                "ink": "#F1F4FA",
                "muted": "#ADB7C8",
                "line": "#343C4A",
                "soft": "#1A222D",
                "card": "#131A24",
                "page": "#0D1117",
                "green": "#66D6A2",
                "red": "#FF8982",
                "alert": "#38272A",
                "active": "#1F2D42",
                "input": "#161D28",
            }, True
        else:
            return {
                "primary": "#3157D5",
                "ink": "#18233A",
                "muted": "#667085",
                "line": "#E5EAF2",
                "soft": "#F3F6FB",
                "card": "#FFFFFF",
                "page": "#F5F7FB",
                "green": "#16865B",
                "red": "#C2413B",
                "alert": "#FFF1F0",
                "active": "#EEF3FF",
                "input": "#FFFFFF",
            }, False

    colors, dark_mode = get_colors()

    def _set_supported(control, property_name, value):
        try:
            if hasattr(control, property_name):
                setattr(control, property_name, value)
        except (AttributeError, TypeError, ValueError):
            pass

    def _style_input(control, dropdown=False):
        c, _ = get_colors()
        _set_supported(control, "bgcolor", c["input"])
        _set_supported(control, "fill_color", c["input"])
        _set_supported(control, "border_color", c["line"])
        _set_supported(control, "focused_border_color", c["primary"])
        _set_supported(control, "text_style", ft.TextStyle(color=c["ink"]))
        _set_supported(control, "label_style", ft.TextStyle(color=c["muted"]))
        _set_supported(control, "hint_style", ft.TextStyle(color=c["muted"]))
        _set_supported(control, "cursor_color", c["primary"])
        _set_supported(control, "selection_color", c["active"])
        if dropdown:
            _set_supported(control, "color", c["ink"])

    status = ft.Text("آماده‌ی برنامه‌ریزی باشید.", size=13, color=colors["muted"])
    title_input = ft.TextField(label="عنوان مرحله", hint_text="مثلاً: آماده‌سازی نمونه")
    description_input = ft.TextField(
        label="توضیحات",
        hint_text="جزئیات یا یادداشت مرحله",
        multiline=True,
        min_lines=1,
        max_lines=3,
    )
    duration_input = ft.TextField(
        label="مدت", value="1", width=120, keyboard_type=ft.KeyboardType.NUMBER
    )
    unit_input = ft.Dropdown(
        label="واحد زمان",
        value="دقیقه",
        width=145,
        options=[_dropdown_option(x, x) for x in UNITS],
    )
    person_input = ft.TextField(label="مسئول", hint_text="اختیاری", width=180)
    process_name = ft.TextField(label="نام فرایند", hint_text="نامی برای این فرایند")
    for _input in (
        title_input,
        description_input,
        duration_input,
        person_input,
        process_name,
    ):
        _style_input(_input)
    _style_input(unit_input, dropdown=True)

    timer_text = ft.Text(
        "00:00:00", size=38, weight=ft.FontWeight.BOLD, color=colors["primary"]
    )
    timer_caption = ft.Text("ساعت : دقیقه : ثانیه", size=12, color=colors["muted"])
    step_label = ft.Text(
        "برای شروع، مراحل فرایند را اضافه کنید.", size=14, color=colors["ink"]
    )
    expired_alert = ft.Container(
        visible=False,
        padding=12,
        border_radius=12,
        bgcolor=colors["alert"],
        content=ft.Row(
            wrap=True,
            spacing=8,
            controls=[
                ft.Icon(
                    _icon("NOTIFICATIONS_ACTIVE_OUTLINED", "NOTIFICATIONS"),
                    color=colors["red"],
                    size=20,
                ),
                ft.Text(
                    "زمان برای انجام این مرحله تمام شد",
                    color=colors["red"],
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        ),
    )
    steps_view, templates_view, history_view = (
        ft.Column(spacing=8),
        ft.Column(spacing=8),
        ft.Column(spacing=8),
    )
    active_check = ft.Checkbox(label="مرحله انجام شد", value=False, disabled=True)
    current_step_card = ft.Container(
        padding=18,
        border_radius=16,
        bgcolor=colors["card"],
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    wrap=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(
                            "تایمر مرحله",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=colors["ink"],
                        ),
                        ft.Icon(
                            _icon("TIMER_OUTLINED", "ACCESS_TIME"),
                            color=colors["primary"],
                        ),
                    ],
                ),
                timer_text,
                timer_caption,
                step_label,
                expired_alert,
                ft.Row(controls=[active_check]),
            ],
        ),
    )

    def persist():
        _write_data(store)

    def _safe_update():
        nonlocal colors, dark_mode
        colors, dark_mode = get_colors()
        try:
            page.update()
        except (AttributeError, RuntimeError):
            pass

    def _beep():
        if os.name == "nt":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except (ImportError, RuntimeError):
                pass

    def _set_status(message, color=None):
        status.value, status.color = message, color or colors["muted"]

    def refresh_steps():
        c, dm = get_colors()
        steps_view.controls.clear()
        if not steps:
            steps_view.controls.append(
                ft.Container(
                    padding=14,
                    border_radius=12,
                    bgcolor=c["soft"],
                    content=ft.Text(
                        "هنوز مرحله‌ای اضافه نشده است.", color=c["muted"], size=13
                    ),
                )
            )
            return
        for index, step in enumerate(steps):
            is_active = state["running"] and index == state["index"]
            done = bool(step.get("completed"))
            details = f"{step.get('duration', step.get('minutes', 1))} {step.get('unit', 'دقیقه')}"
            if step.get("person"):
                details += f"  ·  مسئول: {step['person']}"
            controls = [
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=15,
                    bgcolor=(
                        c["active"]
                        if is_active
                        else (
                            "#1A382B"
                            if dm and done
                            else ("#E7F7EF" if done else c["soft"])
                        )
                    ),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "✓" if done else str(index + 1),
                                size=13,
                                color=c["green"] if done else c["primary"],
                                weight=ft.FontWeight.BOLD,
                            )
                        ],
                    ),
                ),
                ft.Column(
                    spacing=3,
                    controls=[
                        ft.Text(
                            step.get("title") or "بدون عنوان",
                            weight=ft.FontWeight.BOLD,
                            color=c["ink"],
                        ),
                        ft.Text(details, size=12, color=c["muted"]),
                        (
                            ft.Text(
                                step.get("description", ""),
                                size=12,
                                color=c["muted"],
                            )
                            if step.get("description")
                            else ft.Container()
                        ),
                    ],
                ),
            ]
            if not state["running"]:
                controls.append(
                    ft.IconButton(
                        icon=_icon("DELETE_OUTLINE", "DELETE"),
                        tooltip="حذف مرحله",
                        on_click=lambda e, i=index: remove_step(i),
                    )
                )
            steps_view.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=13,
                    bgcolor=c["active"] if is_active else c["card"],
                    content=ft.Row(
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=controls,
                    ),
                )
            )

    def remove_step(index):
        if not state["running"]:
            del steps[index]
            refresh_steps()
            _safe_update()

    def add_step(e=None):
        c, _ = get_colors()
        try:
            duration, unit = (
                int((duration_input.value or "").strip()),
                unit_input.value or "دقیقه",
            )
            if duration <= 0 or unit not in UNITS:
                raise ValueError
        except (ValueError, TypeError):
            _set_status(
                "مدت باید عدد صحیح بزرگ‌تر از صفر و واحد زمان معتبر باشد.", c["red"]
            )
            _safe_update()
            return
        steps.append(
            {
                "title": (title_input.value or "").strip(),
                "description": (description_input.value or "").strip(),
                "duration": duration,
                "unit": unit,
                "person": (person_input.value or "").strip(),
                "completed": False,
            }
        )
        title_input.value = description_input.value = person_input.value = ""
        _set_status("مرحله اضافه شد.", c["green"])
        refresh_steps()
        _safe_update()

    def save_template(e=None):
        c, _ = get_colors()
        name = (process_name.value or "").strip()
        if not name or not steps:
            _set_status(
                "برای ذخیره‌ی الگو، نام فرایند و دست‌کم یک مرحله لازم است.",
                c["red"],
            )
            _safe_update()
            return
        existing = next(
            (t for t in store["templates"] if t.get("id") == state["template_id"]), None
        )
        record = {
            "id": state["template_id"] or uuid.uuid4().hex,
            "name": name,
            "steps": [dict(s) for s in steps],
        }
        if existing:
            existing.update(record)
        else:
            store["templates"].append(record)
        state["template_id"] = record["id"]
        persist()
        _set_status("الگو ذخیره شد.", c["green"])
        refresh_templates()
        _safe_update()

    def use_template(template):
        c, _ = get_colors()
        if state["running"]:
            _set_status("هنگام اجرای فرایند نمی‌توان الگو را عوض کرد.", c["red"])
            _safe_update()
            return
        steps.clear()
        for item in template.get("steps", []):
            if isinstance(item, dict):
                step = dict(item)
                if "duration" not in step:
                    step["duration"] = step.pop("minutes", 1)
                step.setdefault("unit", "دقیقه")
                step["completed"] = False
                steps.append(step)
        process_name.value = template.get("name", "")
        state["template_id"] = template.get("id")
        timer_text.value = "00:00:00"
        active_check.value, active_check.disabled, expired_alert.visible = (
            False,
            True,
            False,
        )
        _set_status(
            "الگو بارگذاری شد؛ تغییرات را با «ذخیره / به‌روزرسانی الگو» ثبت کنید."
        )
        refresh_steps()
        _safe_update()

    def delete_template(template_id):
        store["templates"][:] = [
            t for t in store["templates"] if t.get("id") != template_id
        ]
        if state["template_id"] == template_id:
            state["template_id"] = None
        persist()
        refresh_templates()
        _safe_update()

    def refresh_templates():
        c, _ = get_colors()
        templates_view.controls.clear()
        for item in store["templates"]:
            templates_view.controls.append(
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=c["soft"],
                    content=ft.Row(
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.Text(
                                item.get("name", "الگوی بدون نام"),
                                weight=ft.FontWeight.W_500,
                                color=c["ink"],
                            ),
                            ft.Button(
                                "استفاده / ویرایش",
                                on_click=lambda e, t=item: use_template(t),
                            ),
                            ft.IconButton(
                                icon=_icon("DELETE_OUTLINE", "DELETE"),
                                tooltip="حذف الگو",
                                on_click=lambda e, tid=item.get("id"): delete_template(
                                    tid
                                ),
                            ),
                        ],
                    ),
                )
            )
        if not templates_view.controls:
            templates_view.controls.append(
                ft.Text("الگویی ذخیره نشده است.", size=12, color=c["muted"])
            )

    def refresh_history():
        c, _ = get_colors()
        history_view.controls.clear()
        for item in reversed(store["history"][-30:]):
            history_view.controls.append(
                ft.Container(
                    padding=11,
                    border_radius=12,
                    bgcolor=c["soft"],
                    content=ft.Row(
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.Icon(
                                _icon("CHECK_CIRCLE_OUTLINE", "CHECK_CIRCLE"),
                                color=c["green"],
                                size=18,
                            ),
                            ft.Text(
                                f"{item.get('name', 'فرایند')}  ·  {item.get('completed_at', '')}  ·  {len(item.get('steps', []))} مرحله",
                                size=12,
                                color=c["ink"],
                            ),
                        ],
                    ),
                )
            )
        if not history_view.controls:
            history_view.controls.append(
                ft.Text("تاریخچه‌ای وجود ندارد.", size=12, color=c["muted"])
            )

    def _finish_process():
        c, _ = get_colors()
        if state["history_saved"]:
            return
        store["history"].append(
            {
                "name": process_name.value or "فرایند بدون نام",
                "completed_at": datetime.now().isoformat(timespec="minutes"),
                "steps": [dict(s) for s in steps],
            }
        )
        state["history_saved"] = True
        persist()
        state["index"] = 0
        timer_text.value = "00:00:00"
        step_label.value = "همه‌ی مراحل با موفقیت انجام شدند."
        expired_alert.visible = False
        active_check.value, active_check.disabled = False, True
        _set_status("فرایند کامل شد و در تاریخچه ثبت شد.", c["green"])
        refresh_steps()
        refresh_history()
        _safe_update()

    def _start_current_step():
        c, _ = get_colors()
        if state["index"] >= len(steps):
            _finish_process()
            return
        step = steps[state["index"]]
        step["completed"] = False
        state["expired"], state["running"] = False, True
        state["deadline"] = time.time() + _seconds(step)
        state["generation"] += 1
        generation = state["generation"]
        active_check.value, active_check.disabled = False, True
        expired_alert.visible = False
        step_label.value = f"مرحله {state['index'] + 1} از {len(steps)}: {step.get('title') or 'بدون عنوان'}"
        if step.get("description"):
            step_label.value += f"\n{step['description']}"
        if step.get("person"):
            step_label.value += f"\nمسئول: {step['person']}"
        _set_status("تایمر در حال اجراست.", c["primary"])
        refresh_steps()
        _safe_update()
        page.run_task(run_timer, generation)

    async def run_timer(generation):
        c, _ = get_colors()
        while state["running"] and generation == state["generation"]:
            remaining = max(0, int(state["deadline"] - time.time() + 0.999))
            timer_text.value = _format_time(remaining)
            _safe_update()
            if remaining == 0:
                state["running"], state["expired"] = False, True
                active_check.disabled = False
                expired_alert.visible = True
                _set_status(
                    "زمان مرحله تمام شد؛ پس از انجام کار، تیک مرحله را بزنید.",
                    c["red"],
                )
                _beep()
                refresh_steps()
                _safe_update()
                return
            await asyncio.sleep(min(1, remaining))

    def start_process(e=None):
        c, _ = get_colors()
        if state["running"]:
            return
        if not steps:
            _set_status("ابتدا دست‌کم یک مرحله اضافه کنید.", c["red"])
            _safe_update()
            return
        if state["index"] >= len(steps):
            state["index"] = 0
        state["history_saved"] = False
        for step in steps:
            step["completed"] = False
        _start_current_step()

    def complete_step(e):
        if not active_check.value or not state["expired"]:
            return
        state["expired"] = False
        steps[state["index"]]["completed"] = True
        state["index"] += 1
        if state["index"] >= len(steps):
            _finish_process()
        else:
            _start_current_step()

    def stop_process(e=None):
        state["running"], state["expired"] = False, False
        state["generation"] += 1
        timer_text.value = "00:00:00"
        step_label.value = (
            "اجرای فرایند متوقف شد؛ تاریخچه فقط پس از تکمیل همه‌ی مراحل ثبت می‌شود."
        )
        expired_alert.visible = False
        active_check.value, active_check.disabled = False, True
        _set_status("فرایند متوقف شد.")
        refresh_steps()
        _safe_update()

    active_check.on_change = complete_step

    def section_title(label, icon):
        c, _ = get_colors()
        return ft.Row(
            wrap=True,
            spacing=9,
            controls=[
                ft.Icon(icon, color=c["primary"], size=20),
                ft.Text(label, size=17, weight=ft.FontWeight.BOLD, color=c["ink"]),
            ],
        )

    def panel(content, padding=18):
        c, _ = get_colors()
        return ft.Container(
            padding=padding, border_radius=16, bgcolor=c["card"], content=content
        )

    refresh_steps()
    refresh_templates()
    refresh_history()
    outlined = getattr(ft, "OutlinedButton", ft.Button)

    def build_view():
        c, _ = get_colors()
        return ft.Container(
            expand=True,
            padding=16,
            bgcolor=c["page"],
            border_radius=12,  # هماهنگ کردن لبه‌ها با حاشیه صفحه
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
                controls=[
                    ft.Container(
                        padding=8,
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "مدیریت فرایند",
                                    size=26,
                                    weight=ft.FontWeight.BOLD,
                                    color=c["ink"],
                                ),
                                ft.Text(
                                    "مراحل را طراحی کنید، زمان هر مرحله را تنظیم کنید و پیشرفت را دنبال کنید.",
                                    size=13,
                                    color=c["muted"],
                                ),
                            ],
                        ),
                    ),
                    panel(
                        ft.Column(
                            spacing=13,
                            controls=[
                                section_title(
                                    "تعریف فرایند", _icon("EDIT_NOTE_OUTLINED", "EDIT")
                                ),
                                process_name,
                                ft.Row(
                                    wrap=True,
                                    spacing=10,
                                    run_spacing=8,
                                    controls=[title_input, duration_input, unit_input],
                                ),
                                description_input,
                                ft.Row(
                                    wrap=True,
                                    spacing=10,
                                    run_spacing=8,
                                    controls=[
                                        person_input,
                                        ft.Button(
                                            "افزودن مرحله",
                                            icon=_icon("ADD"),
                                            on_click=add_step,
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ),
                    panel(
                        ft.Column(
                            spacing=12,
                            controls=[
                                section_title(
                                    "مراحل فرایند",
                                    _icon("FORMAT_LIST_NUMBERED", "LIST"),
                                ),
                                steps_view,
                                ft.Row(
                                    wrap=True,
                                    spacing=8,
                                    run_spacing=8,
                                    controls=[
                                        ft.Button(
                                            "ذخیره / به‌روزرسانی الگو",
                                            icon=_icon(
                                                "BOOKMARK_ADD_OUTLINED", "BOOKMARK"
                                            ),
                                            on_click=save_template,
                                        ),
                                        ft.Button(
                                            "شروع / شروع دوباره",
                                            icon=_icon("PLAY_ARROW"),
                                            on_click=start_process,
                                        ),
                                        outlined(
                                            "توقف",
                                            icon=_icon("STOP_CIRCLE_OUTLINED", "STOP"),
                                            on_click=stop_process,
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ),
                    current_step_card,
                    ft.Container(padding=4, content=status),
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title(
                                    "الگوهای ذخیره‌شده",
                                    _icon("BOOKMARK_OUTLINE", "BOOKMARK"),
                                ),
                                templates_view,
                            ],
                        )
                    ),
                    panel(
                        ft.Column(
                            spacing=10,
                            controls=[
                                section_title(
                                    "تاریخچه‌ی فرایندهای تکمیل‌شده",
                                    _icon("HISTORY", "HISTORY"),
                                ),
                                history_view,
                            ],
                        )
                    ),
                ],
            ),
        )

    return build_view()


def build_tab(page):
    return build_process_tab(page)
