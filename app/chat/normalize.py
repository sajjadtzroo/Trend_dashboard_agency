"""The single shared Persian text normalizer (plan §5.1).

Query-time now; index-time in P2 — ONE function so index and query never drift.
Zero-dep char/digit folding covers the high-value cases (Arabic vs Persian ک/ی,
Persian/Arabic-Indic digits, ZWNJ, tatweel, diacritics). hazm/parsivar can be
swapped in later behind this same signature if stemming is ever needed — the SQL
branch matches dim names, so folding is enough for now.
"""

_TRANSLATE: dict[int, int | None] = {}

# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII
for _base in (0x06F0, 0x0660):
    for _i in range(10):
        _TRANSLATE[_base + _i] = ord("0") + _i

# Arabic letters -> Persian equivalents
_TRANSLATE.update({
    0x064A: 0x06CC,  # ي -> ی
    0x0649: 0x06CC,  # ى -> ی
    0x0643: 0x06A9,  # ك -> ک
    0x0629: 0x0647,  # ة -> ه
})

# Remove: tatweel, ZWNJ, Arabic diacritics/tashkeel
for _cp in [0x0640, 0x200C, *range(0x064B, 0x0653)]:
    _TRANSLATE[_cp] = None


def normalize(text: str) -> str:
    """Fold to canonical Persian form and collapse whitespace. Idempotent."""
    if not text:
        return text
    return " ".join(text.translate(_TRANSLATE).split())


if __name__ == "__main__":
    assert normalize("۱۴۰۴") == "1404", normalize("۱۴۰۴")
    assert normalize("٠١٢") == "012"
    assert normalize("كيان") == "کیان"          # Arabic kaf/yeh -> Persian
    assert normalize("نیم‌فاصله") == "نیمفاصله"  # ZWNJ removed
    assert normalize(normalize("سه‌ماهه اول ۱۴۰۴")) == normalize("سه‌ماهه اول ۱۴۰۴")  # idempotent
    print("normalize OK")
