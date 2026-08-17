from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(getattr(settings, "BASE_DIR")) / "static" / "fonts"


def _load_font(size=20, candidates=None):
    for font_path in candidates or []:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    raise RuntimeError(
        "Required invoice font could not be loaded. Ensure the bundled fonts in "
        f"{FONT_DIR} are included in the deployment."
    )


def _invoice_font(size=20, bold=False):
    return _load_font(
        size=size,
        candidates=[
            str(FONT_DIR / ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")),
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
        ],
    )


def _invoice_serif_font(size=20, bold=False):
    return _load_font(
        size=size,
        candidates=[
            str(FONT_DIR / ("NotoSerif-Bold.ttf" if bold else "NotoSerif-Regular.ttf")),
            "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        ],
    )


def _invoice_script_font(size=20):
    return _load_font(
        size=size,
        candidates=[
            str(FONT_DIR / "Pacifico-Regular.ttf"),
            "C:/Windows/Fonts/segoesc.ttf",
            "C:/Windows/Fonts/BRUSHSCI.TTF",
            "C:/Windows/Fonts/georgiai.ttf",
            "C:/Windows/Fonts/georgia.ttf",
        ],
    )


def _fa_solid_font(size=20):
    return _load_font(
        size=size,
        candidates=[str(FONT_DIR / "fa-solid-900.ttf")],
    )


def _wrap_text(draw, text, font, max_width):
    raw = str(text or "").strip()
    if not raw:
        return [""]

    def split_long_token(token):
        pieces = []
        current = ""
        for char in token:
            candidate = f"{current}{char}"
            if current and draw.textlength(candidate, font=font) > max_width:
                pieces.append(current)
                current = char
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces or [token]

    words = []
    for token in raw.split():
        if draw.textlength(token, font=font) <= max_width:
            words.append(token)
        else:
            words.extend(split_long_token(token))

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _format_money(value, currency):
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f} {currency}"


def _invoice_month_year(*date_values):
    """Return an English month/year from the first recognizable invoice date."""
    formats = (
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    )
    for value in date_values:
        text = str(value or "").strip()
        for date_format in formats:
            try:
                return datetime.strptime(text, date_format).strftime("%B %Y")
            except ValueError:
                continue
    return "the invoiced period"


def get_invoice_sender_details():
    def configured(name, default, legacy_values=()):
        value = str(getattr(settings, name, "") or "").strip()
        if not value or value == "-" or value in legacy_values:
            return default
        return value

    default_email = getattr(settings, "CONTACT_SUPPORT_EMAIL", "") or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    if "<" in default_email and ">" in default_email:
        default_email = default_email.split("<", 1)[1].split(">", 1)[0].strip()
    company_email = getattr(settings, "INVOICE_COMPANY_EMAIL", default_email or "-")
    if "<" in company_email and ">" in company_email:
        company_email = company_email.split("<", 1)[1].split(">", 1)[0].strip()

    return {
        "company_name": configured("INVOICE_COMPANY_NAME", "Hembla Experten"),
        "legal_entity": configured("INVOICE_COMPANY_LEGAL_ENTITY", "RWM Helservice AB"),
        "business_name": configured(
            "INVOICE_COMPANY_BUSINESS_NAME",
            "Hembla Experten",
            legacy_values=("Hembla Experten (RWM EL)",),
        ),
        "address": configured(
            "INVOICE_COMPANY_ADDRESS",
            "Kikarvägen 18, 175 46 Järfälla, Sweden",
            legacy_values=(
                "Kikarvagen 18, 175 46 Jarfalla, Stockholm",
                "Kikarvagen 18, 175 46 Jarfalla, Sweden",
            ),
        ),
        "organization_number": configured("INVOICE_COMPANY_ORG_NUMBER", "559545-1351"),
        "vat_number": configured("INVOICE_COMPANY_VAT_NUMBER", "SE559545135101"),
        "f_tax_status": getattr(settings, "INVOICE_COMPANY_F_TAX_STATUS", "Approved for F-tax"),
        "email": company_email,
        "phone": getattr(settings, "INVOICE_COMPANY_PHONE", "-"),
        "bank_details": getattr(settings, "INVOICE_COMPANY_BANK_DETAILS", "-"),
        "bank_name": configured("INVOICE_COMPANY_BANK_NAME", "Handelsbanken"),
        "account_holder": configured("INVOICE_COMPANY_ACCOUNT_HOLDER", "Hembla Experten"),
        "bankgiro": getattr(settings, "INVOICE_COMPANY_BANKGIRO", "-"),
        "account_number": configured("INVOICE_COMPANY_ACCOUNT_NUMBER", "755 995 651"),
        "iban": configured("INVOICE_COMPANY_IBAN", "SE43 6000 0000 0007 5599 5651"),
        "bic": configured("INVOICE_COMPANY_BIC", "HANDSESS"),
        "bank_branch": configured("INVOICE_COMPANY_BANK_BRANCH", "6184"),
    }


def _supersampled_icon(size, painter, scale=6):
    width, height = size
    hi_width = max(1, int(width * scale))
    hi_height = max(1, int(height * scale))
    canvas = Image.new("RGBA", (hi_width, hi_height), (0, 0, 0, 0))
    hi_draw = ImageDraw.Draw(canvas)
    painter(hi_draw, hi_width, hi_height)
    return canvas.resize((width, height), Image.Resampling.LANCZOS)


def _user_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        draw.ellipse((int(30 * s), int(16 * s), int(70 * s), int(56 * s)), outline=rgba, width=line)
        draw.arc((int(18 * s), int(48 * s), int(82 * s), int(96 * s)), start=200, end=340, fill=rgba, width=line)

    return _supersampled_icon(size, painter)


def _house_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        draw.line((int(18 * s), int(50 * s), int(50 * s), int(20 * s), int(82 * s), int(50 * s)), fill=rgba, width=line)
        draw.line((int(26 * s), int(46 * s), int(26 * s), int(82 * s)), fill=rgba, width=line)
        draw.line((int(74 * s), int(46 * s), int(74 * s), int(82 * s)), fill=rgba, width=line)
        draw.line((int(26 * s), int(82 * s), int(74 * s), int(82 * s)), fill=rgba, width=line)
        draw.rectangle((int(44 * s), int(58 * s), int(56 * s), int(82 * s)), outline=rgba, width=line)

    return _supersampled_icon(size, painter)


def _calendar_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        draw.rounded_rectangle((int(16 * s), int(20 * s), int(84 * s), int(84 * s)), radius=int(10 * s), outline=rgba, width=line)
        draw.line((int(16 * s), int(42 * s), int(84 * s), int(42 * s)), fill=rgba, width=line)
        draw.line((int(32 * s), int(12 * s), int(32 * s), int(32 * s)), fill=rgba, width=line)
        draw.line((int(68 * s), int(12 * s), int(68 * s), int(32 * s)), fill=rgba, width=line)
        for col in [32, 50, 68]:
            for row in [54, 68]:
                r = max(3, int(4 * s))
                draw.ellipse((int(col * s) - r, int(row * s) - r, int(col * s) + r, int(row * s) + r), fill=rgba)

    return _supersampled_icon(size, painter)


def _clock_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        draw.ellipse((int(18 * s), int(18 * s), int(82 * s), int(82 * s)), outline=rgba, width=line)
        draw.line((int(50 * s), int(50 * s), int(50 * s), int(32 * s)), fill=rgba, width=line)
        draw.line((int(50 * s), int(50 * s), int(66 * s), int(58 * s)), fill=rgba, width=line)

    return _supersampled_icon(size, painter)


def _group_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        draw.ellipse((int(18 * s), int(24 * s), int(46 * s), int(50 * s)), outline=rgba, width=line)
        draw.ellipse((int(54 * s), int(20 * s), int(82 * s), int(48 * s)), outline=rgba, width=line)
        draw.arc((int(8 * s), int(46 * s), int(56 * s), int(88 * s)), start=210, end=340, fill=rgba, width=line)
        draw.arc((int(42 * s), int(42 * s), int(92 * s), int(90 * s)), start=200, end=330, fill=rgba, width=line)

    return _supersampled_icon(size, painter)


def _percent_badge_icon(size, stroke="#b59b6a"):
    rgba = tuple(int(stroke[i : i + 2], 16) for i in (1, 3, 5)) + (255,)

    def painter(draw, width, height):
        s = min(width, height) / 100.0
        line = max(6, int(7 * s))
        inset = int(10 * s)
        draw.ellipse((inset, inset, width - inset, height - inset), outline=rgba, width=line)
        r = int(8 * s)
        draw.ellipse((int(30 * s) - r, int(34 * s) - r, int(30 * s) + r, int(34 * s) + r), outline=rgba, width=line)
        draw.ellipse((int(70 * s) - r, int(66 * s) - r, int(70 * s) + r, int(66 * s) + r), outline=rgba, width=line)
        draw.line((int(38 * s), int(72 * s), int(62 * s), int(28 * s)), fill=rgba, width=line)

    return _supersampled_icon(size, painter)


def _clean_money(value):
    return str(value or "-").replace(" SEK", "").strip()


def _safe_row_map(rows):
    return {str(label or "").strip().lower(): value for label, value in (rows or [])}


def _build_legacy_branded_invoice_pdf(document):
    scale = 2
    S = lambda value: int(round(value * scale))
    # Keep invoice text readable on phones and when printed.  The previous
    # scale produced body copy around 7pt once the full page was fitted.
    F = lambda value: max(1, int(round(value * 1.20)))

    page_width = S(1240)
    page_height = S(2600)
    frame_left = S(38)
    frame_right = page_width - S(38)
    frame_top = S(34)
    frame_bottom = page_height - S(34)
    frame_width = frame_right - frame_left

    colors = {
        "page": "#f7f5f2",
        "ink": "#161616",
        "muted": "#5e5a54",
        "gold": "#b59b6a",
        "soft_fill": "#f6f1ea",
        "line": "#e7dfd2",
        "line_strong": "#cfbfa5",
        "success": "#6f8758",
    }

    image = Image.new("RGB", (page_width, page_height), colors["page"])
    draw = ImageDraw.Draw(image)

    title_font = _invoice_font(F(S(60)), bold=True)
    brand_font = _invoice_font(F(S(50)), bold=False)
    tagline_font = _invoice_font(F(S(15)), bold=False)
    section_font = _invoice_font(F(S(19)), bold=True)
    body_font = _invoice_font(F(S(20)), bold=False)
    body_bold_font = _invoice_font(F(S(21)), bold=True)
    small_font = _invoice_font(F(S(16)), bold=False)
    small_bold_font = _invoice_font(F(S(16)), bold=True)
    meta_label_font = _invoice_font(F(S(14)), bold=True)
    table_header_font = _invoice_font(F(S(12)), bold=True)
    script_font = _invoice_script_font(F(S(48)))
    total_font = _invoice_font(F(S(27)), bold=True)
    fallback_logo_font = _invoice_serif_font(F(S(44)), bold=True)

    sender = _safe_row_map(document.get("sender_rows"))
    customer_rows = _safe_row_map(document.get("customer_rows"))
    invoice_info = _safe_row_map(document.get("invoice_rows"))
    company_details = dict(document.get("company_details") or {})
    customer_details = dict(document.get("customer_details") or {})
    property_details = dict(document.get("property_details") or {})
    service_details = dict(document.get("service_details") or {})
    line_items = list(document.get("line_items") or [])
    summary_rows = list(document.get("summary_rows") or [])
    notes = [str(line).strip() for line in (document.get("additional_notes") or []) if str(line).strip()]

    brand_name = document.get("brand_name") or sender.get("company name") or sender.get("company_name") or "Company"
    tagline = document.get("tagline") or ""
    document_title = (document.get("document_title") or "Invoice").upper()
    document_number = document.get("document_number") or invoice_info.get("invoice number") or "-"
    invoice_date = invoice_info.get("invoice date") or "-"
    due_date = invoice_info.get("due date") or "-"
    payment_terms = invoice_info.get("payment terms") or "-"
    reference_number = invoice_info.get("reference number") or document_number
    late_interest = invoice_info.get("interest on late payment") or "-"
    customer_number = customer_rows.get("customer number") or customer_details.get("customer_number") or "-"
    currency_code = str(document.get("currency") or "SEK").upper()

    customer_details.setdefault("name", customer_rows.get("customer name") or "-")
    customer_details.setdefault("customer_number", customer_number)
    customer_details.setdefault("address", customer_rows.get("address") or "-")
    customer_details.setdefault("postal_city", customer_rows.get("postal code and city") or "-")
    customer_details.setdefault("country", customer_rows.get("country") or "Sweden")
    customer_details.setdefault("email", customer_rows.get("email") or "-")
    customer_details.setdefault("phone", customer_rows.get("phone") or "-")

    property_details.setdefault("address", customer_details.get("address") or "-")
    property_details.setdefault("postal_city", customer_details.get("postal_city") or "-")
    property_details.setdefault("country", customer_details.get("country") or "Sweden")
    property_details.setdefault("property_number", document_number)

    company_details.setdefault("name", brand_name)
    company_details.setdefault("legal_entity", sender.get("legal entity") or sender.get("legal_entity") or "-")
    company_details.setdefault("business_name", sender.get("business name") or sender.get("business_name") or brand_name)
    company_details.setdefault("organization_number", sender.get("organization number (org.nr)") or sender.get("organization_number") or "-")
    company_details.setdefault("vat_number", sender.get("vat number") or sender.get("vat_number") or "-")
    company_details.setdefault("f_tax_status", sender.get("f-tax status") or sender.get("f_tax_status") or "-")
    company_details.setdefault("address", sender.get("address") or "-")
    company_details.setdefault("email", sender.get("email") or "-")
    company_details.setdefault("phone", sender.get("phone number") or sender.get("phone") or "-")
    company_details.setdefault("bank_details", sender.get("bank details") or sender.get("bank_details") or "-")
    company_details.setdefault("bank_name", sender.get("bank name") or sender.get("bank_name") or company_details["bank_details"])
    company_details.setdefault("account_holder", sender.get("account holder") or sender.get("account_holder") or "-")
    company_details.setdefault("bankgiro", sender.get("bankgiro") or "-")
    company_details.setdefault("account_number", sender.get("account number") or sender.get("account_number") or "-")
    company_details.setdefault("iban", sender.get("iban") or "-")
    company_details.setdefault("bic", sender.get("bic") or "-")
    company_details.setdefault("bank_branch", sender.get("bank branch") or sender.get("bank_branch") or "-")

    if not service_details:
        service_details = {
            "title": line_items[0].get("description", "Booked Service") if line_items else "Booked Service",
            "category": "Service",
            "description": notes[1] if len(notes) > 1 else "Invoice for booked services.",
            "date": invoice_date,
            "start_time": "-",
            "end_time": "-",
            "total_hours": line_items[0].get("quantity", "-") if line_items else "-",
            "assigned_staff": "-",
            "performed_by": f"{brand_name} Team",
        }

    def wrap(text, font, width):
        return _wrap_text(draw, text or "-", font, width)

    def draw_text_block(x, y, lines, font, fill, line_height):
        cur = y
        for line in lines:
            draw.text((x, cur), line, font=font, fill=fill)
            cur += line_height
        return cur

    def draw_right_aligned_block(right_x, top_y, text, font, fill, max_width, line_height):
        lines = wrap(text, font, max_width)
        cur = top_y
        for line in lines:
            line_w = draw.textlength(line, font=font)
            draw.text((right_x - line_w, cur), line, font=font, fill=fill)
            cur += line_height
        return lines, cur

    def fit_font_for_width(text, preferred_font, fallback_fonts, max_width):
        if draw.textlength(str(text), font=preferred_font) <= max_width:
            return preferred_font
        for candidate in fallback_fonts:
            if draw.textlength(str(text), font=candidate) <= max_width:
                return candidate
        return fallback_fonts[-1] if fallback_fonts else preferred_font

    def block_height(lines, line_height):
        return max(0, len(lines)) * line_height

    def centered_text(left, width, top, text, font, fill):
        text_width = draw.textlength(text, font=font)
        draw.text((left + int((width - text_width) / 2), top), text, font=font, fill=fill)

    def centered_text_block(left, width, top, lines, font, fill, line_height):
        cur = top
        for line in lines:
            line_width = draw.textlength(line, font=font)
            draw.text((left + int((width - line_width) / 2), cur), line, font=font, fill=fill)
            cur += line_height
        return cur

    def section_title(x, y, icon, title):
        image.paste(icon, (x, y - S(4)), icon)
        draw.text((x + S(40), y), title, font=section_font, fill=colors["gold"])

    def card_box(left, top, width, height):
        draw.rounded_rectangle((left, top, left + width, top + height), radius=S(6), outline=colors["line"], width=S(1), fill=colors["page"])

    def paste_logo(left, top):
        logo_path = document.get("logo_path")
        if logo_path:
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((S(300), S(210)), Image.Resampling.LANCZOS)
                image.paste(logo, (left, top), logo)
                return logo.size
            except Exception:
                pass
        draw.text((left, top + S(26)), brand_name, font=fallback_logo_font, fill=colors["gold"])
        return (S(280), S(120))

    header_h = S(400)
    left_logo_w = S(520)
    top_divider_x = frame_left + left_logo_w + S(24)
    top_right_left = top_divider_x + S(30)

    logo_size = paste_logo(frame_left + S(10), frame_top + S(28))
    fitted_brand_font = fit_font_for_width(
        brand_name.upper(),
        _invoice_font(F(S(32)), bold=False),
        [
            _invoice_font(F(S(28)), bold=False),
            _invoice_font(F(S(24)), bold=False),
            _invoice_font(F(S(20)), bold=False),
        ],
        left_logo_w - S(28),
    )
    centered_text(
        frame_left,
        left_logo_w,
        frame_top + logo_size[1] + S(20),
        brand_name.upper(),
        fitted_brand_font,
        colors["ink"],
    )
    if tagline:
        centered_text(frame_left, left_logo_w, frame_top + logo_size[1] + S(72), tagline.upper(), tagline_font, colors["gold"])

    draw.line([(top_divider_x, frame_top + S(4)), (top_divider_x, frame_top + header_h - S(8))], fill=colors["line"], width=S(1))
    draw.text((top_right_left, frame_top), document_title, font=title_font, fill=colors["ink"])

    due_badge_w = S(168)
    due_badge_h = S(124)
    due_badge_left = frame_right - due_badge_w
    draw.rounded_rectangle(
        (due_badge_left, frame_top - S(4), due_badge_left + due_badge_w, frame_top - S(4) + due_badge_h),
        radius=S(12),
        outline=colors["line_strong"],
        width=S(1),
        fill=colors["soft_fill"],
    )
    due_icon = _calendar_icon((S(28), S(28)), stroke=colors["gold"])
    image.paste(due_icon, (due_badge_left + int((due_badge_w - due_icon.size[0]) / 2), frame_top + S(18)), due_icon)
    due_label = "PAYMENT DUE BY"
    due_label_font = fit_font_for_width(
        due_label,
        small_bold_font,
        [_invoice_font(F(S(14)), bold=True), _invoice_font(F(S(12)), bold=True)],
        due_badge_w - S(24),
    )
    due_date_font = fit_font_for_width(
        str(due_date),
        body_bold_font,
        [_invoice_font(F(S(19)), bold=True), _invoice_font(F(S(17)), bold=True)],
        due_badge_w - S(24),
    )
    centered_text(due_badge_left, due_badge_w, frame_top + S(55), due_label, due_label_font, colors["ink"])
    centered_text(due_badge_left, due_badge_w, frame_top + S(80), str(due_date), due_date_font, colors["ink"])

    meta_rows = [
        ("INVOICE NO.", document_number),
        ("BOOKING / REFERENCE ID", reference_number),
        ("CUSTOMER NO.", customer_number),
        ("INVOICE DATE", invoice_date),
        ("DUE DATE", due_date),
        ("PAYMENT TERMS", payment_terms),
        ("LATE PAYMENT INTEREST", late_interest),
    ]
    meta_y = frame_top + S(102)
    meta_value_x = top_right_left + S(270)
    meta_label_x = top_right_left
    meta_value_width = due_badge_left - meta_value_x - S(28)
    for index, (label, value) in enumerate(meta_rows):
        if index:
            draw.line(
                [(meta_label_x, meta_y - S(10)), (due_badge_left - S(24), meta_y - S(10))],
                fill=colors["line"],
                width=S(1),
            )
        draw.text((meta_label_x, meta_y), label, font=meta_label_font, fill=colors["ink"])
        value_lines = wrap(str(value), body_font, meta_value_width)
        draw_text_block(meta_value_x, meta_y - S(2), value_lines[:2], body_font, colors["ink"], S(24))
        meta_y += S(43) if len(value_lines) == 1 else S(59)

    cards_top = frame_top + header_h + S(26)
    card_gap = S(16)
    card_w = int((frame_width - (card_gap * 2)) / 3)

    customer_card_left = frame_left
    property_card_left = customer_card_left + card_w + card_gap
    thank_card_left = property_card_left + card_w + card_gap

    customer_card_lines = []
    customer_name_lines = wrap(
        str(customer_details.get("name", "-")),
        body_bold_font,
        card_w - S(36),
    )[:2]
    for line in [
        f"Customer No.:  {customer_details.get('customer_number', '-')}",
        customer_details.get("address", "-"),
        customer_details.get("postal_city", "-"),
        customer_details.get("country", "-"),
        customer_details.get("email", "-"),
        customer_details.get("phone", "-"),
    ]:
        customer_card_lines.append(wrap(str(line), body_font, card_w - S(36)))

    property_address_lines = [
        wrap(str(property_details.get("address", "-")), body_font, card_w - S(36)),
        wrap(str(property_details.get("postal_city", "-")), body_font, card_w - S(36)),
        wrap(str(property_details.get("country", "-")), body_font, card_w - S(36)),
    ]
    property_number_lines = wrap(str(property_details.get("property_number", "-")), body_bold_font, card_w - S(36))
    property_note_lines = wrap("(Property designations as registered)", small_font, card_w - S(36))

    thank_text = wrap(
        notes[0] if notes else "Thank you for choosing Hembla. We truly appreciate your trust and the opportunity to help keep your home beautiful.",
        body_font,
        card_w - S(96),
    )

    customer_line_h = S(30)
    customer_card_h = (
        S(60)
        + block_height(customer_name_lines, customer_line_h)
        + S(12)
        + sum(block_height(lines[:3], customer_line_h) + S(9) for lines in customer_card_lines)
        + S(16)
        + S(20)
    )
    property_card_h = (
        S(62) + S(30)
        + sum(block_height(lines[:3], S(30)) + S(9) for lines in property_address_lines)
        + S(14) + S(28) + block_height(property_number_lines[:2], S(30))
        + S(10) + block_height(property_note_lines[:2], S(22)) + S(24)
    )
    thank_card_h = S(34) + S(64) + block_height(thank_text[:6], S(32)) + S(36)
    card_h = max(S(248), customer_card_h, property_card_h, thank_card_h)

    for left in [customer_card_left, property_card_left, thank_card_left]:
        card_box(left, cards_top, card_w, card_h)

    section_title(customer_card_left + S(18), cards_top + S(14), _user_icon((S(24), S(24)), stroke=colors["gold"]), "CUSTOMER INFORMATION")
    cy = cards_top + S(60)
    draw_text_block(customer_card_left + S(18), cy, customer_name_lines, body_bold_font, colors["ink"], customer_line_h)
    cy += block_height(customer_name_lines, customer_line_h) + S(12)
    for index, wrapped in enumerate(customer_card_lines):
        visible_lines = wrapped[:3]
        draw_text_block(customer_card_left + S(18), cy, visible_lines, body_font, colors["ink"], customer_line_h)
        cy += block_height(visible_lines, customer_line_h) + S(9)
        if index == 3:
            cy += S(16)

    section_title(property_card_left + S(18), cards_top + S(14), _house_icon((S(24), S(24)), stroke=colors["gold"]), "PROPERTY INFORMATION")
    py = cards_top + S(62)
    draw.text((property_card_left + S(18), py), "Property Address", font=small_bold_font, fill=colors["ink"])
    py += S(28)
    for wrapped in property_address_lines:
        visible_lines = wrapped[:3]
        draw_text_block(property_card_left + S(18), py, visible_lines, body_font, colors["ink"], S(30))
        py += block_height(visible_lines, S(30)) + S(9)
    divider_y = py + S(8)
    draw.line([(property_card_left + S(18), divider_y), (property_card_left + card_w - S(18), divider_y)], fill=colors["line"], width=S(1))
    draw.text((property_card_left + S(18), divider_y + S(20)), "Property Number", font=small_bold_font, fill=colors["ink"])
    property_number_top = divider_y + S(50)
    draw_text_block(property_card_left + S(18), property_number_top, property_number_lines[:2], body_bold_font, colors["ink"], S(30))
    property_note_top = property_number_top + block_height(property_number_lines[:2], S(30)) + S(10)
    draw_text_block(property_card_left + S(18), property_note_top, property_note_lines[:2], small_font, colors["muted"], S(22))

    thank_title = "Thank you!"
    fitted_thank_font = fit_font_for_width(
        thank_title,
        script_font,
        [
            _invoice_script_font(F(S(40))),
            _invoice_script_font(F(S(34))),
            _invoice_script_font(F(S(30))),
        ],
        card_w - S(36),
    )
    centered_text(thank_card_left, card_w, cards_top + S(24), thank_title, fitted_thank_font, colors["gold"])
    draw_text_block(thank_card_left + S(24), cards_top + S(140), thank_text[:6], body_font, colors["ink"], S(32))

    service_top = cards_top + card_h + S(24)
    service_title_lines = wrap(str(service_details.get("title", "-")), body_bold_font, S(330))
    service_category_lines = wrap(str(service_details.get("category", "-")), body_font, S(330))
    service_description_lines = wrap(str(service_details.get("description", "-")), body_font, S(330))
    mid_metric_lines = [wrap(str(value), body_font, S(170)) for _, _, value in [
        (_calendar_icon((S(20), S(20)), stroke=colors["gold"]), "SERVICE DATE", service_details.get("date", "-")),
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "START TIME", service_details.get("start_time", "-")),
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "END TIME", service_details.get("end_time", "-")),
    ]]
    right_metric_lines = [wrap(str(value), body_font, S(166)) for _, _, value in [
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "TOTAL HOURS", service_details.get("total_hours", "-")),
        (_user_icon((S(20), S(20)), stroke=colors["gold"]), "ASSIGNED STAFF", service_details.get("assigned_staff", "-")),
        (_group_icon((S(20), S(20)), stroke=colors["gold"]), "PERFORMED BY", service_details.get("performed_by", "-")),
    ]]
    left_service_h = S(50) + S(26) + block_height(service_title_lines[:3], S(26)) + S(16) + S(26) + block_height(service_category_lines[:3], S(26)) + S(16) + S(26) + block_height(service_description_lines[:6], S(22)) + S(22)
    mid_service_h = S(50) + sum((S(54) if len(lines) == 1 else S(66)) for lines in mid_metric_lines) + S(16)
    right_service_h = S(50) + sum((S(54) if len(lines) == 1 else S(66)) for lines in right_metric_lines) + S(16)
    service_h = max(S(208), left_service_h, mid_service_h, right_service_h)
    card_box(frame_left, service_top, frame_width, service_h)
    section_title(frame_left + S(18), service_top + S(14), _calendar_icon((S(24), S(24)), stroke=colors["gold"]), "SERVICE DETAILS")

    service_col1_x = frame_left + S(24)
    service_col2_x = frame_left + int(frame_width / 2) - S(48)
    service_col3_x = frame_left + int(frame_width * 0.72)

    def draw_labeled_block(x, y, label, value, width, value_font=None, line_height=None):
        draw.text((x, y), label, font=small_bold_font, fill=colors["ink"])
        lines = wrap(str(value), value_font or body_font, width)
        draw_text_block(x, y + S(26), lines[:4], value_font or body_font, colors["ink"], line_height or S(26))

    service_left_y = service_top + S(54)
    draw_labeled_block(service_col1_x, service_left_y, "EXACT BOOKED SERVICE", service_details.get("title", "-"), S(330), body_bold_font, S(30))
    service_left_y += S(26) + block_height(service_title_lines[:3], S(26)) + S(16)
    draw_labeled_block(service_col1_x, service_left_y, "SERVICE CATEGORY", service_details.get("category", "-"), S(330), body_font, S(30))
    service_left_y += S(26) + block_height(service_category_lines[:3], S(26)) + S(16)
    draw_labeled_block(service_col1_x, service_left_y, "SERVICE DESCRIPTION", service_details.get("description", "-"), S(330), body_font, S(22))

    icon_x = service_col2_x
    icon_label_x = icon_x + S(34)
    metric_y = service_top + S(54)
    mid_metrics = [
        (_calendar_icon((S(20), S(20)), stroke=colors["gold"]), "SERVICE DATE", service_details.get("date", "-")),
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "START TIME", service_details.get("start_time", "-")),
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "END TIME", service_details.get("end_time", "-")),
    ]
    for idx, (icon, label, value) in enumerate(mid_metrics):
        image.paste(icon, (icon_x, metric_y + S(2)), icon)
        draw.text((icon_label_x, metric_y), label, font=small_bold_font, fill=colors["ink"])
        wrapped = mid_metric_lines[idx]
        draw_text_block(icon_label_x, metric_y + S(26), wrapped[:2], body_font, colors["ink"], S(22))
        metric_y += S(54) if len(wrapped) == 1 else S(66)

    metric_y = service_top + S(54)
    right_metrics = [
        (_clock_icon((S(20), S(20)), stroke=colors["gold"]), "TOTAL HOURS", service_details.get("total_hours", "-")),
        (_user_icon((S(20), S(20)), stroke=colors["gold"]), "ASSIGNED STAFF", service_details.get("assigned_staff", "-")),
        (_group_icon((S(20), S(20)), stroke=colors["gold"]), "PERFORMED BY", service_details.get("performed_by", "-")),
    ]
    for idx, (icon, label, value) in enumerate(right_metrics):
        image.paste(icon, (service_col3_x, metric_y + S(2)), icon)
        draw.text((service_col3_x + S(34), metric_y), label, font=small_bold_font, fill=colors["ink"])
        wrapped = right_metric_lines[idx]
        draw_text_block(service_col3_x + S(34), metric_y + S(26), wrapped[:2], body_font, colors["ink"], S(22))
        metric_y += S(54) if len(wrapped) == 1 else S(66)

    main_top = service_top + service_h + S(24)
    breakdown_gap = S(16)
    breakdown_w = S(300)
    table_w = frame_width - breakdown_w - breakdown_gap
    table_left = frame_left
    breakdown_left = table_left + table_w + breakdown_gap

    table_header_h = S(58)
    table_inner_left = table_left + S(18)
    table_inner_right = table_left + table_w - S(18)
    table_inner_w = table_inner_right - table_inner_left
    column_gap = S(14)
    desc_w = S(255)
    date_w = S(105)
    qty_w = S(70)
    unit_w = S(100)
    vat_w = S(72)
    amount_w = table_inner_w - desc_w - date_w - qty_w - unit_w - vat_w - (column_gap * 5)
    desc_x = table_inner_left
    date_x = desc_x + desc_w + column_gap
    qty_x = date_x + date_w + column_gap
    unit_x = qty_x + qty_w + column_gap
    vat_x = unit_x + unit_w + column_gap
    amount_x = vat_x + vat_w + column_gap
    amount_right_x = table_inner_right

    row_specs = []
    for row in line_items:
        description = str(row.get("description") or "-").strip()
        title_lines = []
        detail_lines = []
        if "\n" in description:
            split_lines = [part.strip() for part in description.splitlines() if part.strip()]
            if split_lines:
                title_lines = wrap(split_lines[0], body_bold_font, desc_w)
                if len(split_lines) > 1:
                    detail_lines = wrap(" ".join(split_lines[1:]), body_font, desc_w)
        else:
            title_lines = wrap(description, body_bold_font, desc_w)
        date_text = str(row.get("date") or invoice_date)
        date_font = fit_font_for_width(
            date_text,
            small_font,
            [_invoice_font(F(S(14))), _invoice_font(F(S(12)))],
            date_w,
        )
        date_lines = [date_text]
        qty_lines = wrap(str(row.get("quantity", "-")), small_font, qty_w)
        unit_value = _clean_money(row.get("unit_price", "-")).replace(f" {currency_code}", "")
        amount_value = _clean_money(row.get("line_total", "-")).replace(f" {currency_code}", "")
        unit_lines = wrap(unit_value, small_font, unit_w)
        vat_lines = wrap(str(row.get("vat_percent") or "-"), small_font, vat_w)
        amount_lines = wrap(amount_value, small_font, amount_w)
        row_h = max(
            S(70),
            len(title_lines) * S(26) + len(detail_lines) * S(22) + S(22),
            len(date_lines) * S(24) + S(20),
            len(qty_lines) * S(24) + S(20),
            len(unit_lines) * S(24) + S(20),
            len(vat_lines) * S(24) + S(20),
            len(amount_lines) * S(24) + S(20),
        )
        row_specs.append((row, title_lines, detail_lines, date_lines, qty_lines, unit_lines, vat_lines, amount_lines, row_h, date_font))

    if not row_specs:
        fallback_date_font = fit_font_for_width(
            str(invoice_date),
            small_font,
            [_invoice_font(F(S(14))), _invoice_font(F(S(12)))],
            date_w,
        )
        row_specs.append(({"quantity": "-", "unit_price": "-", "vat_percent": "-", "line_total": "-", "date": invoice_date}, ["Service"], [], [invoice_date], ["-"], ["-"], ["-"], ["-"], S(70), fallback_date_font))

    table_h = table_header_h + sum(spec[8] for spec in row_specs)
    card_box(table_left, main_top, table_w, table_h)
    draw.rectangle((table_left, main_top, table_left + table_w, main_top + table_header_h), fill=colors["soft_fill"], outline=colors["line"])
    draw.text((desc_x, main_top + S(18)), "DESCRIPTION", font=table_header_font, fill=colors["ink"])
    centered_text(date_x, date_w, main_top + S(18), "DATE", table_header_font, colors["ink"])
    centered_text(qty_x, qty_w, main_top + S(8), "HOURS /", table_header_font, colors["ink"])
    centered_text(qty_x, qty_w, main_top + S(30), "QTY", table_header_font, colors["ink"])
    centered_text(unit_x, unit_w, main_top + S(8), "UNIT", table_header_font, colors["ink"])
    centered_text(unit_x, unit_w, main_top + S(30), "PRICE", table_header_font, colors["ink"])
    centered_text(vat_x, vat_w, main_top + S(8), "VAT", table_header_font, colors["ink"])
    centered_text(vat_x, vat_w, main_top + S(30), "%", table_header_font, colors["ink"])
    amount_label = f"AMOUNT ({str(document.get('currency') or 'SEK').upper()})"
    amount_label_w = draw.textlength(amount_label, font=table_header_font)
    draw.text((amount_right_x - amount_label_w, main_top + S(18)), amount_label, font=table_header_font, fill=colors["ink"])

    row_y = main_top + table_header_h
    for index, (row, title_lines, detail_lines, date_lines, qty_lines, unit_lines, vat_lines, amount_lines, row_h, date_font) in enumerate(row_specs):
        if index:
            draw.line([(table_left + S(16), row_y), (table_left + table_w - S(16), row_y)], fill=colors["line"], width=S(1))
        text_y = row_y + S(16)
        for i, line in enumerate(title_lines):
            draw.text((desc_x, text_y + (i * S(26))), line, font=small_bold_font if i == 0 else small_font, fill=colors["ink"])
        detail_y = text_y + len(title_lines) * S(26)
        for i, line in enumerate(detail_lines[:3]):
            draw.text((desc_x, detail_y + (i * S(22))), line, font=body_font, fill=colors["ink"])
        for i, line in enumerate(date_lines[:2]):
            centered_text(date_x, date_w, text_y + (i * S(24)), line, date_font, colors["ink"])
        centered_text_block(qty_x, qty_w, text_y, qty_lines[:2], small_font, colors["ink"], S(24))
        centered_text_block(unit_x, unit_w, text_y, unit_lines[:2], small_font, colors["ink"], S(24))
        centered_text_block(vat_x, vat_w, text_y, vat_lines[:2], small_font, colors["ink"], S(24))
        draw_right_aligned_block(amount_right_x, text_y, "\n".join(amount_lines[:2]).replace("\n", " "), small_font, colors["ink"], amount_w, S(24))
        row_y += row_h

    total_row = None
    breakdown_specs = []
    for label, value, is_total in summary_rows:
        if is_total:
            total_row = (label, value)
            continue
        label_text = str(label)
        if label_text.strip().upper() == "ROT/RUT (INCL. VAT)":
            continue
        value_text = str(value)
        fill = colors["success"] if any(word in label_text.upper() for word in ["RUT", "ROT", "DISCOUNT", "REWARD"]) or str(value_text).strip().startswith("-") else colors["ink"]
        clean_value = _clean_money(value_text)
        label_lines = wrap(label_text, small_font, breakdown_w - S(136))[:3]
        value_lines = wrap(clean_value, small_font, S(100))[:2]
        breakdown_specs.append((label_lines, value_lines, fill))

    total_label, total_value = total_row or ("TOTAL TO PAY", "-")
    total_label_lines = wrap(str(total_label).upper(), small_bold_font, breakdown_w - S(32))
    total_clean = _clean_money(total_value)
    fitted_total_font = fit_font_for_width(
        total_clean,
        total_font,
        [_invoice_font(F(S(25)), bold=True), _invoice_font(F(S(23)), bold=True), _invoice_font(F(S(21)), bold=True)],
        breakdown_w - S(36),
    )
    breakdown_content_h = S(18)
    for label_lines, value_lines, _fill in breakdown_specs:
        breakdown_content_h += max(block_height(label_lines, S(24)), block_height(value_lines, S(24))) + S(12)
    total_box_h = max(S(142), S(24) + block_height(total_label_lines[:2], S(24)) + S(58) + S(34))
    breakdown_h = table_header_h + breakdown_content_h + S(16) + total_box_h
    card_box(breakdown_left, main_top, breakdown_w, breakdown_h)
    draw.rectangle((breakdown_left, main_top, breakdown_left + breakdown_w, main_top + table_header_h), fill=colors["soft_fill"], outline=colors["line"])
    draw.text((breakdown_left + S(16), main_top + S(12)), "PRICE BREAKDOWN (INCL. VAT)", font=small_bold_font, fill=colors["ink"])

    bd_y = main_top + table_header_h + S(18)
    for label_lines, value_lines, fill in breakdown_specs:
        line_h = max(block_height(label_lines, S(24)), block_height(value_lines, S(24)))
        draw_text_block(breakdown_left + S(16), bd_y, label_lines, small_font, fill, S(24))
        draw_right_aligned_block(
            breakdown_left + breakdown_w - S(16),
            bd_y,
            "\n".join(value_lines),
            small_font,
            fill,
            S(100),
            S(24),
        )
        bd_y += line_h + S(12)

    draw.line([(breakdown_left + S(16), bd_y + S(6)), (breakdown_left + breakdown_w - S(16), bd_y + S(6))], fill=colors["line_strong"], width=S(1))
    total_box_top = main_top + breakdown_h - total_box_h
    draw.rectangle((breakdown_left, total_box_top, breakdown_left + breakdown_w, main_top + breakdown_h), fill=colors["soft_fill"], outline=colors["line"])
    draw_text_block(breakdown_left + S(16), total_box_top + S(16), total_label_lines[:2], small_bold_font, colors["ink"], S(24))
    total_w = draw.textlength(total_clean, font=fitted_total_font)
    draw.text((breakdown_left + breakdown_w - S(18) - total_w, total_box_top + S(48)), total_clean, font=fitted_total_font, fill=colors["gold"])
    draw.text((breakdown_left + S(16), total_box_top + total_box_h - S(28)), "Amount to be paid by due date.", font=small_font, fill=colors["ink"])

    rut_top = main_top + table_h + S(22)
    eligible_label = next((str(value) for label, value, _ in summary_rows if "ELIGIBLE" in str(label).upper()), "-")
    deduction_label = next((
        str(value) for label, value, _ in summary_rows
        if "RUT DEDUCTION" in str(label).upper()
        or "ROT DEDUCTION" in str(label).upper()
        or "ROT/RUT" in str(label).upper()
    ), "-")
    final_label = total_row[1] if total_row else "-"
    try:
        deduction_number = Decimal(
            deduction_label.upper().replace(currency_code, "").replace(" ", "").replace("-", "") or "0"
        )
    except Exception:
        deduction_number = Decimal("0.00")
    rut_applied = deduction_number > 0
    rut_note = wrap(notes[2] if len(notes) > 2 else "Hembla applies for the deduction from the Swedish Tax Agency on behalf of the customer.", small_font, table_w - S(44))
    rut_h = S(194)
    card_box(table_left, rut_top, table_w, rut_h)
    fa_heading = _fa_solid_font(S(19))
    fa_metric = _fa_solid_font(S(18))
    draw.text((table_left + S(18), rut_top + S(16)), "\uf058", font=fa_heading, fill=colors["gold"])
    draw.text((table_left + S(48), rut_top + S(17)), "RUT DEDUCTION", font=section_font, fill=colors["gold"])

    badge_text = "APPLIED" if rut_applied else "NOT APPLIED"
    badge_w = S(92 if rut_applied else 118)
    badge_left = table_left + table_w - badge_w - S(18)
    draw.rounded_rectangle(
        (badge_left, rut_top + S(12), badge_left + badge_w, rut_top + S(42)),
        radius=S(15), fill="#edf5eb" if rut_applied else colors["soft_fill"],
    )
    centered_text(badge_left, badge_w, rut_top + S(19), badge_text, small_bold_font, colors["success"] if rut_applied else colors["muted"])

    metric_top = rut_top + S(62)
    metric_gap = S(14)
    metric_w = int((table_w - S(36) - (metric_gap * 2)) / 3)
    metrics = [
        ("\uf0b1", "ELIGIBLE LABOR", _clean_money(eligible_label)),
        ("%", "RUT DEDUCTION", _clean_money(deduction_label)),
        ("\uf555", "CUSTOMER PAYS", _clean_money(final_label)),
    ]
    for index, (icon_char, label, value) in enumerate(metrics):
        metric_left = table_left + S(18) + (index * (metric_w + metric_gap))
        draw.rounded_rectangle(
            (metric_left, metric_top, metric_left + metric_w, metric_top + S(76)),
            radius=S(7), fill=colors["soft_fill"], outline=colors["line"], width=S(1),
        )
        draw.text((metric_left + S(13), metric_top + S(13)), icon_char, font=fa_metric, fill=colors["gold"])
        draw.text((metric_left + S(43), metric_top + S(13)), label, font=small_bold_font, fill=colors["muted"])
        value_text = str(value)
        value_font = body_bold_font if index == 2 else body_font
        value_w = draw.textlength(value_text, font=value_font)
        draw.text((metric_left + metric_w - S(13) - value_w, metric_top + S(42)), value_text, font=value_font, fill=colors["ink"])

    draw_text_block(table_left + S(20), rut_top + S(151), rut_note[:2], small_font, colors["muted"], S(18))

    footer_top = max(rut_top + rut_h, main_top + breakdown_h) + S(34)
    footer_col_gap = S(16)
    footer_col_w = int((frame_width - (footer_col_gap * 2)) / 3)
    footer_positions = [
        frame_left,
        frame_left + footer_col_w + footer_col_gap,
        frame_left + (footer_col_w * 2) + (footer_col_gap * 2),
    ]
    footer_titles = ["PAYMENT INFORMATION", "COMPANY INFORMATION", "IMPORTANT INFORMATION"]
    footer_icons = [
        _calendar_icon((S(22), S(22)), stroke=colors["gold"]),
        _house_icon((S(22), S(22)), stroke=colors["gold"]),
        _user_icon((S(22), S(22)), stroke=colors["gold"]),
    ]

    payment_rows = [
        ("Bank:", company_details.get("bank_name") or company_details.get("bank_details", "-")),
        ("Holder:", company_details.get("account_holder", "-")),
        ("Account no.:", company_details.get("account_number", "-")),
        ("IBAN:", company_details.get("iban", "-")),
        ("BIC/SWIFT:", company_details.get("bic", "-")),
        ("Clearing no.:", company_details.get("bank_branch", "-")),
        ("Reference:", reference_number),
    ]
    payment_label_w = max(
        int(draw.textlength(label, font=small_bold_font))
        for label, _value in payment_rows
    ) + S(16)
    payment_value_lines = [wrap(str(value), small_font, footer_col_w - payment_label_w - S(32))[:2] for _, value in payment_rows]
    company_rows = [
        ("Legal entity:", company_details.get("legal_entity", "-")),
        ("Business name:", company_details.get("business_name", brand_name)),
        ("Organization no.:", company_details.get("organization_number", "-")),
        ("VAT No:", company_details.get("vat_number", "-")),
        ("Address:", company_details.get("address", "-")),
        ("F-tax:", company_details.get("f_tax_status", "-")),
        ("Email:", company_details.get("email", "-")),
    ]
    company_label_w = max(
        int(draw.textlength(label, font=small_bold_font))
        for label, _value in company_rows
    ) + S(12)
    company_value_w = max(S(90), footer_col_w - S(32) - company_label_w)
    company_row_specs = []
    for label, value in company_rows:
        value_lines = wrap(str(value), small_font, company_value_w)[:3]
        company_row_specs.append((label, value_lines))
    service_period = _invoice_month_year(service_details.get("date"), invoice_date)
    company_short_name = str(company_details.get("name") or brand_name).removesuffix(" AB")
    if rut_applied:
        important_paragraphs = [
            f"This invoice covers home cleaning services performed during {service_period} "
            f"and includes a preliminary RUT deduction of {_format_money(deduction_number, currency_code)}.",
            f"After the customer's payment is registered, {company_short_name} will apply "
            "to the Swedish Tax Agency for the same amount.",
            "If the deduction is wholly or partially denied, the customer must pay the outstanding amount.",
        ]
    else:
        important_paragraphs = [
            "This invoice covers the services detailed above.",
            "Please use the invoice/reference number when making payment.",
            "If you have any questions regarding the service, charges or invoice, "
            "please contact Hembla Experten before the due date.",
        ]
    important_wrapped_paragraphs = [
        wrap(paragraph, small_font, footer_col_w - S(32))
        for paragraph in important_paragraphs
    ]
    # Keep this in sync with the row advances used while drawing below. Payment
    # details can contain several rows, so a fixed estimate would cause the
    # reference and terms to overlap in production PDFs.
    payment_row_heights = [S(32) if len(lines) == 1 else S(52) for lines in payment_value_lines]
    payment_h = S(58) + sum(payment_row_heights) + S(44)
    company_line_height = S(24)
    company_row_gap = S(6)
    company_h = (
        S(54)
        + sum(max(1, len(lines)) * company_line_height for _label, lines in company_row_specs)
        + ((len(company_row_specs) - 1) * company_row_gap)
        + S(26)
    )
    important_line_height = S(27)
    important_paragraph_gap = S(16)
    important_line_count = sum(len(lines) for lines in important_wrapped_paragraphs)
    important_h = (
        S(54)
        + (important_line_count * important_line_height)
        + ((len(important_wrapped_paragraphs) - 1) * important_paragraph_gap)
        + S(24)
    )
    footer_h = max(S(210), payment_h, company_h, important_h)

    for left, title, icon in zip(footer_positions, footer_titles, footer_icons):
        card_box(left, footer_top, footer_col_w, footer_h)
        image.paste(icon, (left + S(16), footer_top + S(12)), icon)
        draw.text((left + S(48), footer_top + S(14)), title, font=small_bold_font, fill=colors["gold"])

    left = footer_positions[0] + S(16)
    fy = footer_top + S(58)
    for idx, (label, value) in enumerate(payment_rows):
        draw.text((left, fy), label, font=small_bold_font, fill=colors["ink"])
        value_lines = payment_value_lines[idx]
        draw_text_block(left + payment_label_w, fy, value_lines[:2], small_font, colors["ink"], S(20))
        fy += payment_row_heights[idx]
    draw.text((left, fy + S(6)), f"Payment terms: {payment_terms}.", font=small_font, fill=colors["muted"])

    left = footer_positions[1] + S(16)
    fy = footer_top + S(58)
    for label, value_lines in company_row_specs:
        draw.text((left, fy), label, font=small_bold_font, fill=colors["ink"])
        draw_text_block(left + company_label_w, fy, value_lines, small_font, colors["ink"], company_line_height)
        fy += (max(1, len(value_lines)) * company_line_height) + company_row_gap

    left = footer_positions[2] + S(16)
    fy = footer_top + S(58)
    for paragraph_lines in important_wrapped_paragraphs:
        draw_text_block(left, fy, paragraph_lines, small_font, colors["ink"], important_line_height)
        fy += (len(paragraph_lines) * important_line_height) + important_paragraph_gap

    bottom_y = footer_top + footer_h + S(52)
    draw.line([(frame_left, bottom_y - S(34)), (frame_right, bottom_y - S(34))], fill=colors["line"], width=S(1))
    footer_text = document.get("footer_text") or " | ".join(
        value for value in [company_details.get("address"), company_details.get("phone"), company_details.get("email")] if value and value != "-"
    )
    footer_lines = wrap(str(footer_text), body_font, frame_width - S(40))
    footer_block_h = block_height(footer_lines[:2], S(24))
    centered_text_block(frame_left, frame_width, bottom_y - S(14), footer_lines[:2], body_font, colors["gold"], S(24))

    final_height = min(page_height, bottom_y + footer_block_h + S(24))
    image = image.crop((0, 0, page_width, final_height))

    pdf_buffer = BytesIO()
    image.save(pdf_buffer, format="PDF", resolution=300.0)
    return pdf_buffer.getvalue()


def _build_modern_branded_invoice_pdf(document):
    """Build a compact, print-ready A4 invoice with a conventional global layout."""
    scale = 2
    S = lambda value: int(round(value * scale))
    page_w, page_h = S(1240), S(1754)
    margin = S(62)
    content_w = page_w - (margin * 2)

    colors = {
        "page": "#ffffff",
        "ink": "#152b3a",
        "muted": "#62727d",
        "accent": "#b5965a",
        "accent_soft": "#f6f1e8",
        "navy_soft": "#edf3f6",
        "line": "#dce4e8",
        "success": "#557a58",
    }
    image = Image.new("RGB", (page_w, page_h), colors["page"])
    draw = ImageDraw.Draw(image)

    title_font = _invoice_font(S(38), bold=True)
    invoice_no_font = _invoice_font(S(19), bold=True)
    heading_font = _invoice_font(S(12), bold=True)
    body_font = _invoice_font(S(13), bold=False)
    body_bold = _invoice_font(S(13), bold=True)
    small_font = _invoice_font(S(10), bold=False)
    small_bold = _invoice_font(S(10), bold=True)
    total_font = _invoice_font(S(23), bold=True)

    sender = _safe_row_map(document.get("sender_rows"))
    customer = _safe_row_map(document.get("customer_rows"))
    info = _safe_row_map(document.get("invoice_rows"))
    customer_details = dict(document.get("customer_details") or {})
    property_details = dict(document.get("property_details") or {})
    service = dict(document.get("service_details") or {})
    company = dict(document.get("company_details") or {})
    lines = list(document.get("line_items") or [])
    summary = list(document.get("summary_rows") or [])
    notes = [str(value).strip() for value in (document.get("additional_notes") or []) if str(value).strip()]

    brand = document.get("brand_name") or company.get("name") or "Hembla Experten AB"
    number = document.get("document_number") or info.get("invoice number") or "-"
    invoice_date = info.get("invoice date") or "-"
    due_date = info.get("due date") or "-"
    payment_terms = info.get("payment terms") or "-"
    reference = info.get("reference number") or number
    currency = str(document.get("currency") or "SEK").upper()
    customer_number = customer.get("customer number") or customer_details.get("customer_number") or "-"

    def text_width(text, font):
        return draw.textlength(str(text), font=font)

    def right_text(right, y, text, font, fill=None):
        draw.text((right - text_width(text, font), y), str(text), font=font, fill=fill or colors["ink"])

    def wrap(text, font, width, limit=None):
        wrapped = _wrap_text(draw, str(text or "-"), font, width)
        return wrapped[:limit] if limit else wrapped

    def draw_lines(x, y, values, font=body_font, fill=None, line_h=None):
        step = line_h or S(20)
        for value in values:
            draw.text((x, y), str(value), font=font, fill=fill or colors["ink"])
            y += step
        return y

    def card(x, y, w, h, fill="#ffffff"):
        draw.rounded_rectangle(
            (x, y, x + w, y + h), radius=S(10), fill=fill,
            outline=colors["line"], width=S(1),
        )

    def section_label(x, y, label):
        draw.text((x, y), label.upper(), font=heading_font, fill=colors["accent"])

    def label_value(x, y, label, value, value_x, max_width, value_font=body_font):
        draw.text((x, y), label.upper(), font=small_bold, fill=colors["muted"])
        value_lines = wrap(value, value_font, max_width, 2)
        draw_lines(value_x, y - S(2), value_lines, value_font, colors["ink"], S(18))

    # Header: one strong brand area and one compact invoice identity area.
    logo_path = document.get("logo_path")
    logo_bottom = S(58)
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((S(250), S(115)), Image.Resampling.LANCZOS)
            logo_x = margin
            logo_y = S(48)
            image.paste(logo, (logo_x, logo_y), logo)
            logo_bottom = logo_y + logo.height
        except Exception:
            draw.text((margin, S(58)), brand, font=invoice_no_font, fill=colors["ink"])
            logo_bottom = S(96)
    else:
        draw.text((margin, S(58)), brand, font=invoice_no_font, fill=colors["ink"])
        logo_bottom = S(96)

    tagline = document.get("tagline") or ""
    if tagline:
        draw.text((margin, logo_bottom + S(8)), tagline.upper(), font=small_font, fill=colors["accent"])

    right = page_w - margin
    draw.text((S(760), S(48)), "INVOICE", font=title_font, fill=colors["ink"])
    right_text(right, S(58), number, invoice_no_font, colors["accent"])
    draw.text((S(760), S(113)), "ISSUE DATE", font=small_bold, fill=colors["muted"])
    draw.text((S(870), S(111)), invoice_date, font=body_font, fill=colors["ink"])
    draw.text((S(1000), S(113)), "DUE DATE", font=small_bold, fill=colors["muted"])
    right_text(right, S(111), due_date, body_bold, colors["ink"])
    draw.line((margin, S(190), right, S(190)), fill=colors["accent"], width=S(3))

    # Customer and invoice details.
    gap = S(18)
    card_y = S(216)
    card_h = S(238)
    card_w = int((content_w - gap) / 2)
    card(margin, card_y, card_w, card_h, colors["navy_soft"])
    card(margin + card_w + gap, card_y, card_w, card_h)

    pad = S(22)
    section_label(margin + pad, card_y + S(18), "Bill to")
    customer_name = customer_details.get("name") or customer.get("customer name") or "-"
    draw.text((margin + pad, card_y + S(50)), str(customer_name), font=invoice_no_font, fill=colors["ink"])
    customer_address = [
        customer_details.get("address") or customer.get("address") or "-",
        customer_details.get("postal_city") or customer.get("postal code and city") or "-",
        customer_details.get("country") or customer.get("country") or "Sweden",
    ]
    cy = card_y + S(84)
    for value in customer_address:
        cy = draw_lines(margin + pad, cy, wrap(value, body_font, card_w - S(44), 2), body_font, colors["ink"], S(20))
    contact_line = "  |  ".join(
        value for value in [customer_details.get("email"), customer_details.get("phone")] if value and value != "-"
    ) or "-"
    draw_lines(margin + pad, card_y + card_h - S(48), wrap(contact_line, small_font, card_w - S(44), 2), small_font, colors["muted"], S(16))

    details_x = margin + card_w + gap + pad
    details_value_x = details_x + S(190)
    details_width = card_w - S(234)
    section_label(details_x, card_y + S(18), "Invoice details")
    detail_rows = [
        ("Invoice number", number),
        ("Customer number", customer_number),
        ("Reference", reference),
        ("Payment terms", payment_terms),
        ("Late interest", info.get("interest on late payment") or "-"),
    ]
    dy = card_y + S(54)
    for label, value in detail_rows:
        label_value(details_x, dy, label, value, details_value_x, details_width, body_bold if label == "Invoice number" else body_font)
        dy += S(34)

    # Compact service/property band.
    service_y = card_y + card_h + S(18)
    service_h = S(174)
    card(margin, service_y, content_w, service_h)
    section_label(margin + pad, service_y + S(17), "Service summary")
    col_w = int((content_w - S(44)) / 3)
    columns = [
        (
            "SERVICE",
            service.get("title") or (lines[0].get("description") if lines else "-"),
            service.get("category") or "Service",
        ),
        (
            "LOCATION",
            property_details.get("address") or customer_details.get("address") or "-",
            property_details.get("postal_city") or customer_details.get("postal_city") or "-",
        ),
        (
            "SCHEDULE",
            service.get("date") or invoice_date,
            " · ".join(value for value in [service.get("start_time"), service.get("end_time")] if value and value != "-") or "Time not specified",
        ),
    ]
    for index, (label, primary, secondary) in enumerate(columns):
        x = margin + pad + (col_w * index)
        if index:
            draw.line((x - S(15), service_y + S(54), x - S(15), service_y + service_h - S(20)), fill=colors["line"], width=S(1))
        draw.text((x, service_y + S(55)), label, font=small_bold, fill=colors["muted"])
        draw_lines(x, service_y + S(82), wrap(primary, body_bold, col_w - S(28), 2), body_bold, colors["ink"], S(19))
        draw_lines(x, service_y + S(124), wrap(secondary, small_font, col_w - S(28), 2), small_font, colors["muted"], S(17))

    # Full-width line-item table with unambiguous columns.
    table_y = service_y + service_h + S(18)
    table_x = margin
    table_w = content_w
    header_h = S(48)
    desc_w = S(420)
    date_w = S(150)
    qty_w = S(120)
    unit_w = S(190)
    amount_w = table_w - desc_w - date_w - qty_w - unit_w
    column_x = [table_x, table_x + desc_w, table_x + desc_w + date_w, table_x + desc_w + date_w + qty_w, table_x + desc_w + date_w + qty_w + unit_w]
    draw.rounded_rectangle((table_x, table_y, table_x + table_w, table_y + header_h), radius=S(8), fill=colors["ink"])
    headers = ["DESCRIPTION", "DATE", "QTY", "UNIT PRICE", f"AMOUNT ({currency})"]
    widths = [desc_w, date_w, qty_w, unit_w, amount_w]
    for index, label in enumerate(headers):
        x = column_x[index] + S(14)
        if index >= 2:
            right_text(column_x[index] + widths[index] - S(14), table_y + S(15), label, small_bold, "#ffffff")
        else:
            draw.text((x, table_y + S(15)), label, font=small_bold, fill="#ffffff")

    row_y = table_y + header_h
    source_lines = lines or [{"description": "Service", "date": invoice_date, "quantity": "-", "unit_price": "-", "line_total": "-"}]
    row_height = S(62 if len(source_lines) <= 6 else 50)
    for index, row in enumerate(source_lines):
        if index % 2:
            draw.rectangle((table_x, row_y, table_x + table_w, row_y + row_height), fill="#f8fafb")
        draw.line((table_x, row_y + row_height, table_x + table_w, row_y + row_height), fill=colors["line"], width=S(1))
        description_lines = wrap(row.get("description") or "-", body_bold, desc_w - S(28), 2)
        draw_lines(table_x + S(14), row_y + S(15), description_lines, body_bold, colors["ink"], S(18))
        draw.text((column_x[1] + S(14), row_y + S(16)), str(row.get("date") or invoice_date), font=body_font, fill=colors["ink"])
        right_text(column_x[3] - S(14), row_y + S(16), row.get("quantity", "-"), body_font)
        right_text(column_x[4] - S(14), row_y + S(16), _clean_money(row.get("unit_price", "-")), body_font)
        right_text(table_x + table_w - S(14), row_y + S(16), _clean_money(row.get("line_total", "-")), body_bold)
        row_y += row_height

    # Notes/RUT on the left, financial summary on the right.
    summary_y = row_y + S(18)
    summary_w = S(390)
    notes_w = content_w - summary_w - gap
    non_total = [(str(label), str(value)) for label, value, is_total in summary if not is_total]
    total_row = next(((str(label), str(value)) for label, value, is_total in summary if is_total), ("TOTAL", "-"))
    summary_h = max(S(214), S(78) + (len(non_total) * S(31)))
    card(table_x, summary_y, notes_w, summary_h, colors["accent_soft"])
    card(table_x + notes_w + gap, summary_y, summary_w, summary_h)

    section_label(table_x + pad, summary_y + S(18), "Payment & deduction notes")
    rut_applied = any("RUT" in label.upper() and _clean_money(value) not in {"0", "0.00", "-"} for label, value in non_total)
    note_title = "RUT/ROT deduction included" if rut_applied else "No RUT/ROT deduction applied"
    draw.text((table_x + pad, summary_y + S(52)), note_title, font=body_bold, fill=colors["success"] if rut_applied else colors["ink"])
    note_text = next((note for note in notes if len(note) > 24), "Please use the invoice number as the payment reference.")
    draw_lines(table_x + pad, summary_y + S(82), wrap(note_text, body_font, notes_w - S(44), 5), body_font, colors["muted"], S(20))

    sx = table_x + notes_w + gap + pad
    section_label(sx, summary_y + S(18), "Summary")
    sy = summary_y + S(52)
    for label, value in non_total:
        fill = colors["success"] if any(word in label.upper() for word in ["DISCOUNT", "RUT", "ROT", "REWARD"]) else colors["ink"]
        draw.text((sx, sy), label.upper(), font=small_font, fill=fill)
        right_text(table_x + table_w - pad, sy - S(2), _clean_money(value), body_font, fill)
        sy += S(31)
    total_top = summary_y + summary_h - S(68)
    draw.line((sx, total_top, table_x + table_w - pad, total_top), fill=colors["accent"], width=S(2))
    draw.text((sx, total_top + S(17)), total_row[0].upper(), font=heading_font, fill=colors["ink"])
    right_text(table_x + table_w - pad, total_top + S(9), _clean_money(total_row[1]), total_font, colors["accent"])

    # Compact payment/company footer with no decorative dead space.
    footer_y = summary_y + summary_h + S(18)
    footer_h = min(S(205), page_h - footer_y - S(72))
    card(margin, footer_y, content_w, footer_h, colors["navy_soft"])
    footer_col_w = int(content_w / 3)
    footer_data = [
        (
            "Payment",
            [
                f"Reference: {reference}",
                f"Terms: {payment_terms}",
                f"Bank: {company.get('bank_details') or '-'}",
            ],
        ),
        (
            "Company",
            [
                company.get("name") or brand,
                f"Org.nr: {company.get('organization_number') or '-'}",
                f"VAT: {company.get('vat_number') or '-'}",
            ],
        ),
        (
            "Contact",
            [
                company.get("email") or "-",
                company.get("phone") or "-",
                company.get("address") or "-",
            ],
        ),
    ]
    for index, (label, values) in enumerate(footer_data):
        x = margin + pad + (footer_col_w * index)
        if index:
            draw.line((x - S(15), footer_y + S(20), x - S(15), footer_y + footer_h - S(20)), fill=colors["line"], width=S(1))
        section_label(x, footer_y + S(18), label)
        fy = footer_y + S(53)
        for value in values:
            fy = draw_lines(x, fy, wrap(value, small_font, footer_col_w - S(46), 2), small_font, colors["ink"], S(17)) + S(5)

    footer_text = document.get("footer_text") or "Thank you for choosing Hembla Experten AB."
    footer_text = str(footer_text)
    footer_text_w = text_width(footer_text, small_font)
    draw.text(((page_w - footer_text_w) / 2, page_h - S(42)), footer_text, font=small_font, fill=colors["accent"])

    pdf_buffer = BytesIO()
    image.save(pdf_buffer, format="PDF", resolution=300.0)
    return pdf_buffer.getvalue()


def build_branded_invoice_pdf(document):
    """Use the established Hembla invoice design, with readability fixes."""
    return _build_legacy_branded_invoice_pdf(document)


def default_logo_path():
    base_dir = Path(getattr(settings, "BASE_DIR"))
    logo_tight = base_dir / "static" / "images" / "logo-tight.png"
    if logo_tight.exists():
        return str(logo_tight)
    return str(base_dir / "static" / "images" / "logo.png")
