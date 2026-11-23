#!/usr/bin/env python3
"""Build the SYNTHETIC pointing corpus in evals/pointing/ (deterministic; rerun to regenerate).

Six made-up apps x English and Arabic, 25 cases each (300). The element names come from common
desktop UI vocabulary, and the cases are the awkward shapes real trees have: names that drift
("Export" vs "Export…"), a name that is a prefix of another ("Save" and "Save As…"), spelling
variants in Arabic, the same name twice, and a target that is not on screen at all.
This is NOT a recording of real apps: it proves the harness and the resolver on constructed
cases. Replace or add `"source": "recorded"` snapshots from real apps (ADR-0007) for the real gate.
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "evals" / "pointing"

# (English, Arabic)
VOCAB = [
    ("Open", "فتح"),
    ("Save", "حفظ"),
    ("Save As…", "حفظ باسم…"),
    ("Close", "إغلاق"),
    ("Cancel", "إلغاء"),
    ("Apply", "تطبيق"),
    ("OK", "موافق"),
    ("Copy", "نسخ"),
    ("Paste", "لصق"),
    ("Cut", "قص"),
    ("Undo", "تراجع"),
    ("Redo", "إعادة"),
    ("Find", "بحث"),
    ("Replace", "استبدال"),
    ("Zoom In", "تكبير"),
    ("Zoom Out", "تصغير"),
    ("Preferences", "التفضيلات"),
    ("Settings", "الإعدادات"),
    ("Help", "مساعدة"),
    ("Print", "طباعة"),
    ("Export…", "تصدير…"),
    ("Import…", "استيراد…"),
    ("Rename", "إعادة تسمية"),
    ("Select All", "تحديد الكل"),
    ("Bold", "غامق"),
    ("Italic", "مائل"),
    ("Underline", "تسطير"),
    ("Align Left", "محاذاة لليسار"),
    ("Align Right", "محاذاة لليمين"),
    ("Center", "توسيط"),
    ("New", "جديد"),
    ("Edit", "تحرير"),
    ("View", "عرض"),
    ("Insert", "إدراج"),
    ("Tools", "أدوات"),
    ("Window", "نافذة"),
    ("Sort", "ترتيب"),
    ("Filter", "تصفية"),
    ("Refresh", "تحديث"),
    ("Run", "تشغيل"),
    ("Stop", "إيقاف"),
    ("Start", "بدء"),
    ("Connect", "اتصال"),
    ("Add", "إضافة"),
    ("Create", "إنشاء"),
    ("Show", "إظهار"),
    ("Hide", "إخفاء"),
    ("Mute", "كتم"),
    ("Volume", "الصوت"),
    ("Language", "اللغة"),
    ("Network", "الشبكة"),
    ("Bluetooth", "بلوتوث"),
    ("Display", "الشاشة"),
    ("Keyboard", "لوحة المفاتيح"),
    ("Mouse", "الفأرة"),
    ("Sound", "الصوت العام"),
    ("Power", "الطاقة"),
    ("About", "حول"),
    ("Layers", "الطبقات"),
    ("Brush", "فرشاة"),
    ("Fill", "تعبئة"),
    ("Stroke", "حد"),
    ("Crop", "اقتصاص"),
    ("Rotate", "تدوير"),
    ("Resize", "تغيير الحجم"),
    ("Merge", "دمج"),
]
APPS = ["editor", "painter", "sheet", "settings", "browser", "terminal"]
ROLES = ["button", "menu item", "check box", "page tab"]
VARIANTS_AR = {
    "إعادة": "اعادة",
    "إغلاق": "اغلاق",
    "إلغاء": "الغاء",
    "إضافة": "اضافة",
    "إظهار": "اظهار",
}


def build(app: str, locale: str, rng: random.Random) -> dict:
    col = 0 if locale == "en" else 1
    pool = rng.sample(VOCAB, 36)
    elements = []
    for i, entry in enumerate(pool):
        elements.append(
            {
                "id": f"e{i}",
                "role": ROLES[i % len(ROLES)],
                "name": entry[col],
                "rect": [10 + (i % 6) * 120, 40 + (i // 6) * 48, 110, 36],
            }
        )
    by_name = {e["name"]: e for e in elements}
    cases: list[dict] = []

    def add(kind, role, name, truth):
        cases.append(
            {"id": f"c{len(cases)}", "kind": kind, "role": role, "name": name, "truth": truth}
        )

    uniq = [e for e in elements if sum(x["name"] == e["name"] for x in elements) == 1]
    for e in rng.sample(uniq, 14):
        add("exact", e["role"], e["name"], e["id"])
    for e in rng.sample(uniq, 3):  # case and spacing, Arabic spelling variants
        name = e["name"]
        variant = VARIANTS_AR.get(name)
        add("spelling", e["role"], variant or f"  {name.upper()}  ", e["id"])
    for e in [x for x in uniq if x["name"].endswith("…")][:2]:  # the plan forgot the ellipsis
        add("drift", e["role"], e["name"].rstrip("…"), e["id"])
    names = {e["name"] for e in elements}
    for e in rng.sample(uniq, 3):  # one word of the name is missing
        words = e["name"].split()
        short = words[0] if len(words) > 1 else e["name"][:-1]
        if short not in names and len([c for c in cases if c["kind"] == "drift"]) < 4:
            add(
                "drift", e["role"], short, e["id"]
            )  # (a short name that IS another element's would mislabel)
    # the same name twice in one role: nothing but position tells them apart
    twin = rng.choice(uniq)
    clone = {**twin, "id": "twin", "rect": [10, 500, 110, 36]}
    elements.append(clone)
    add("duplicate", twin["role"], twin["name"], rng.choice([twin["id"], "twin"]))
    # a name that is not on screen, asked for among close neighbours
    absent = [v for v in VOCAB if v[col] not in by_name]
    for entry in rng.sample(absent, 3):
        add("missing", "button", entry[col], None)
    while len(cases) < 25:  # a right name under the wrong role is also "not here"
        e = rng.choice(uniq)
        other = next(
            r
            for r in ROLES
            if r != e["role"]
            and not any(x["role"] == r and x["name"] == e["name"] for x in elements)
        )
        add("wrong-role", other, e["name"], None)
    rng.shuffle(cases)
    for i, c in enumerate(cases):
        c["id"] = f"c{i}"
    return {
        "app": app,
        "locale": locale,
        "source": "synthetic",
        "elements": elements,
        "cases": cases,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("synthetic-*.json"):
        old.unlink()
    for n, app in enumerate(APPS):
        for locale in ("en", "ar"):
            rng = random.Random(19 * 100 + n * 2 + (locale == "ar"))
            data = build(app, locale, rng)
            path = OUT / f"synthetic-{app}-{locale}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
