from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont


def _load_font(size=20, candidates=None):
    for font_path in candidates or []:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _invoice_font(size=20, bold=False):
    return _load_font(
        size=size,
        candidates=[
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
            "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        ],
    )


def _invoice_script_font(size=20):
    return _load_font(
        size=size,
        candidates=[
            "C:/Windows/Fonts/segoesc.ttf",
            "C:/Windows/Fonts/BRUSHSCI.TTF",
            "C:/Windows/Fonts/georgiai.ttf",
            "C:/Windows/Fonts/georgia.ttf",
        ],
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


def get_invoice_sender_details():
    default_email = getattr(settings, "CONTACT_SUPPORT_EMAIL", "") or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    if "<" in default_email and ">" in default_email:
        default_email = default_email.split("<", 1)[1].split(">", 1)[0].strip()

    return {
        "company_name": getattr(settings, "INVOICE_COMPANY_NAME", "Hembla Experten AB"),
        "address": getattr(settings, "INVOICE_COMPANY_ADDRESS", "Kikarvagen 18, 175 46 Jarfalla, Stockholm"),
        "organization_number": getattr(settings, "INVOICE_COMPANY_ORG_NUMBER", "-"),
        "vat_number": getattr(settings, "INVOICE_COMPANY_VAT_NUMBER", "-"),
        "f_tax_status": getattr(settings, "INVOICE_COMPANY_F_TAX_STATUS", "Approved for F-tax"),
        "email": getattr(settings, "INVOICE_COMPANY_EMAIL", default_email or "-"),
        "phone": getattr(settings, "INVOICE_COMPANY_PHONE", "-"),
        "bank_details": getattr(settings, "INVOICE_COMPANY_BANK_DETAILS", "-"),
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


def build_branded_invoice_pdf(document):
    scale = 2
    S = lambda value: int(round(value * scale))
    F = lambda value: max(1, int(round(value * 0.88)))

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
    tagline_font = _invoice_font(F(S(12)), bold=False)
    section_font = _invoice_font(F(S(16)), bold=True)
    body_font = _invoice_font(F(S(17)), bold=False)
    body_bold_font = _invoice_font(F(S(18)), bold=True)
    small_font = _invoice_font(F(S(13)), bold=False)
    small_bold_font = _invoice_font(F(S(13)), bold=True)
    script_font = _invoice_script_font(F(S(48)))
    total_font = _invoice_font(F(S(34)), bold=True)
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
    company_details.setdefault("organization_number", sender.get("organization number (org.nr)") or sender.get("organization_number") or "-")
    company_details.setdefault("vat_number", sender.get("vat number") or sender.get("vat_number") or "-")
    company_details.setdefault("f_tax_status", sender.get("f-tax status") or sender.get("f_tax_status") or "-")
    company_details.setdefault("address", sender.get("address") or "-")
    company_details.setdefault("email", sender.get("email") or "-")
    company_details.setdefault("phone", sender.get("phone number") or sender.get("phone") or "-")
    company_details.setdefault("bank_details", sender.get("bank details") or sender.get("bank_details") or "-")

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

    header_h = S(332)
    left_logo_w = S(520)
    top_divider_x = frame_left + left_logo_w + S(24)
    top_right_left = top_divider_x + S(30)

    logo_size = paste_logo(frame_left + S(10), frame_top + S(8))
    centered_text(frame_left, left_logo_w, frame_top + logo_size[1] + S(20), brand_name.upper(), brand_font, colors["ink"])
    if tagline:
        centered_text(frame_left, left_logo_w, frame_top + logo_size[1] + S(92), tagline.upper(), tagline_font, colors["gold"])

    draw.line([(top_divider_x, frame_top + S(4)), (top_divider_x, frame_top + header_h - S(8))], fill=colors["line"], width=S(1))
    draw.text((top_right_left, frame_top), document_title, font=title_font, fill=colors["ink"])

    due_badge_w = S(132)
    due_badge_h = S(118)
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
    centered_text(due_badge_left, due_badge_w, frame_top + S(54), "PAYMENT DUE BY", small_bold_font, colors["ink"])
    centered_text(due_badge_left, due_badge_w, frame_top + S(76), str(due_date), body_bold_font, colors["ink"])

    meta_rows = [
        ("INVOICE NO.", document_number),
        ("BOOKING / REFERENCE ID", reference_number),
        ("CUSTOMER NO.", customer_number),
        ("INVOICE DATE", invoice_date),
        ("DUE DATE", due_date),
        ("PAYMENT TERMS", payment_terms),
        ("LATE PAYMENT INTEREST", late_interest),
    ]
    meta_y = frame_top + S(92)
    meta_value_x = top_right_left + S(226)
    meta_label_x = top_right_left
    meta_value_width = due_badge_left - meta_value_x - S(28)
    for label, value in meta_rows:
        draw.text((meta_label_x, meta_y), label, font=small_bold_font, fill=colors["ink"])
        value_lines = wrap(str(value), body_font, meta_value_width)
        draw_text_block(meta_value_x, meta_y - S(2), value_lines[:2], body_font, colors["ink"], S(24))
        meta_y += S(38) if len(value_lines) == 1 else S(54)

    cards_top = frame_top + header_h + S(26)
    card_gap = S(16)
    card_w = int((frame_width - (card_gap * 2)) / 3)

    customer_card_left = frame_left
    property_card_left = customer_card_left + card_w + card_gap
    thank_card_left = property_card_left + card_w + card_gap

    customer_card_lines = []
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

    customer_card_h = (
        S(24) + S(24) + S(24) + S(42)
        + sum(S(28) if len(lines) == 1 else S(44) for lines in customer_card_lines[:-2])
        + S(20)
        + sum(S(28) if len(lines) == 1 else S(44) for lines in customer_card_lines[-2:])
        + S(24)
    )
    property_card_h = (
        S(24) + S(24) + S(24) + S(32)
        + sum(S(28) if len(lines) == 1 else S(44) for lines in property_address_lines)
        + S(18) + S(30) + S(32) + block_height(property_note_lines, S(18)) + S(22)
    )
    thank_card_h = S(34) + S(64) + block_height(thank_text[:6], S(32)) + S(36)
    card_h = max(S(248), customer_card_h, property_card_h, thank_card_h)

    for left in [customer_card_left, property_card_left, thank_card_left]:
        card_box(left, cards_top, card_w, card_h)

    section_title(customer_card_left + S(18), cards_top + S(14), _user_icon((S(24), S(24)), stroke=colors["gold"]), "CUSTOMER INFORMATION")
    cy = cards_top + S(60)
    draw.text((customer_card_left + S(18), cy), str(customer_details.get("name", "-")), font=body_bold_font, fill=colors["ink"])
    cy += S(36)
    for index, wrapped in enumerate(customer_card_lines):
        draw_text_block(customer_card_left + S(18), cy, wrapped[:3], body_font, colors["ink"], S(24))
        cy += S(28) if len(wrapped) == 1 else S(44)
        if index == 3:
            cy += S(16)

    section_title(property_card_left + S(18), cards_top + S(14), _house_icon((S(24), S(24)), stroke=colors["gold"]), "PROPERTY INFORMATION")
    py = cards_top + S(62)
    draw.text((property_card_left + S(18), py), "Property Address", font=small_bold_font, fill=colors["ink"])
    py += S(28)
    for wrapped in property_address_lines:
        draw_text_block(property_card_left + S(18), py, wrapped[:2], body_font, colors["ink"], S(24))
        py += S(28) if len(wrapped) == 1 else S(44)
    divider_y = py + S(8)
    draw.line([(property_card_left + S(18), divider_y), (property_card_left + card_w - S(18), divider_y)], fill=colors["line"], width=S(1))
    draw.text((property_card_left + S(18), divider_y + S(20)), "Property Number", font=small_bold_font, fill=colors["ink"])
    draw_text_block(property_card_left + S(18), divider_y + S(50), property_number_lines[:2], body_bold_font, colors["ink"], S(26))
    draw_text_block(property_card_left + S(18), divider_y + S(84), property_note_lines[:2], small_font, colors["muted"], S(18))

    draw.text((thank_card_left + S(44), cards_top + S(26)), "Thank you!", font=script_font, fill=colors["gold"])
    draw_text_block(thank_card_left + S(44), cards_top + S(118), thank_text[:6], body_font, colors["ink"], S(32))

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

    table_header_h = S(44)
    table_inner_left = table_left + S(18)
    table_inner_right = table_left + table_w - S(18)
    table_inner_w = table_inner_right - table_inner_left
    column_gap = S(18)
    desc_w = S(320)
    date_w = S(108)
    qty_w = S(80)
    unit_w = S(92)
    amount_w = table_inner_w - desc_w - date_w - qty_w - unit_w - (column_gap * 4)
    desc_x = table_inner_left
    date_x = desc_x + desc_w + column_gap
    qty_x = date_x + date_w + column_gap
    unit_x = qty_x + qty_w + column_gap
    amount_x = unit_x + unit_w + column_gap
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
        date_lines = wrap(row.get("date") or invoice_date, body_font, date_w)
        qty_lines = wrap(str(row.get("quantity", "-")), body_font, qty_w)
        unit_lines = wrap(_clean_money(row.get("unit_price", "-")), body_font, unit_w)
        amount_lines = wrap(_clean_money(row.get("line_total", "-")), body_font, amount_w)
        row_h = max(
            S(70),
            len(title_lines) * S(26) + len(detail_lines) * S(22) + S(22),
            len(date_lines) * S(24) + S(20),
            len(qty_lines) * S(24) + S(20),
            len(unit_lines) * S(24) + S(20),
            len(amount_lines) * S(24) + S(20),
        )
        row_specs.append((row, title_lines, detail_lines, date_lines, qty_lines, unit_lines, amount_lines, row_h))

    if not row_specs:
        row_specs.append(({"quantity": "-", "unit_price": "-", "line_total": "-", "date": invoice_date}, ["Service"], [], [invoice_date], ["-"], ["-"], ["-"], S(70)))

    table_h = table_header_h + sum(spec[7] for spec in row_specs)
    card_box(table_left, main_top, table_w, table_h)
    draw.rectangle((table_left, main_top, table_left + table_w, main_top + table_header_h), fill=colors["soft_fill"], outline=colors["line"])
    draw.text((desc_x, main_top + S(12)), "DESCRIPTION", font=small_bold_font, fill=colors["ink"])
    draw.text((date_x, main_top + S(12)), "DATE", font=small_bold_font, fill=colors["ink"])
    draw.text((qty_x, main_top + S(12)), "HOURS / QTY", font=small_bold_font, fill=colors["ink"])
    draw.text((unit_x, main_top + S(12)), "UNIT PRICE", font=small_bold_font, fill=colors["ink"])
    amount_label = "AMOUNT (SEK)"
    amount_label_w = draw.textlength(amount_label, font=small_bold_font)
    draw.text((amount_right_x - amount_label_w, main_top + S(12)), amount_label, font=small_bold_font, fill=colors["ink"])

    row_y = main_top + table_header_h
    for index, (row, title_lines, detail_lines, date_lines, qty_lines, unit_lines, amount_lines, row_h) in enumerate(row_specs):
        if index:
            draw.line([(table_left + S(16), row_y), (table_left + table_w - S(16), row_y)], fill=colors["line"], width=S(1))
        text_y = row_y + S(16)
        for i, line in enumerate(title_lines):
            draw.text((desc_x, text_y + (i * S(26))), line, font=body_bold_font if i == 0 else body_font, fill=colors["ink"])
        detail_y = text_y + len(title_lines) * S(26)
        for i, line in enumerate(detail_lines[:3]):
            draw.text((desc_x, detail_y + (i * S(22))), line, font=body_font, fill=colors["ink"])
        for i, line in enumerate(date_lines[:2]):
            draw.text((date_x, text_y + (i * S(24))), line, font=body_font, fill=colors["ink"])
        draw_text_block(qty_x + S(6), text_y, qty_lines[:2], body_font, colors["ink"], S(24))
        draw_text_block(unit_x + S(6), text_y, unit_lines[:2], body_font, colors["ink"], S(24))
        draw_right_aligned_block(amount_right_x, text_y, "\n".join(amount_lines[:2]).replace("\n", " "), body_font, colors["ink"], amount_w, S(24))
        row_y += row_h

    total_row = None
    breakdown_specs = []
    for label, value, is_total in summary_rows:
        if is_total:
            total_row = (label, value)
            continue
        label_text = str(label)
        value_text = str(value)
        fill = colors["success"] if any(word in label_text.upper() for word in ["RUT", "ROT", "DISCOUNT", "REWARD"]) or str(value_text).strip().startswith("-") else colors["ink"]
        clean_value = _clean_money(value_text)
        label_lines = wrap(label_text, body_font, breakdown_w - S(136))[:3]
        value_lines = wrap(clean_value, body_font, S(100))[:2]
        breakdown_specs.append((label_lines, value_lines, fill))

    total_label, total_value = total_row or ("TOTAL TO PAY", "-")
    total_label_lines = wrap(str(total_label).upper(), body_bold_font, breakdown_w - S(170))
    total_clean = _clean_money(total_value)
    fitted_total_font = fit_font_for_width(
        total_clean,
        total_font,
        [_invoice_font(F(S(32)), bold=True), _invoice_font(F(S(30)), bold=True), _invoice_font(F(S(28)), bold=True)],
        S(140),
    )
    breakdown_content_h = S(18)
    for label_lines, value_lines, _fill in breakdown_specs:
        breakdown_content_h += max(block_height(label_lines, S(24)), block_height(value_lines, S(24))) + S(12)
    total_box_h = max(S(116), S(26) + block_height(total_label_lines[:2], S(24)) + S(46) + S(30))
    breakdown_h = table_header_h + breakdown_content_h + S(16) + total_box_h
    card_box(breakdown_left, main_top, breakdown_w, breakdown_h)
    draw.rectangle((breakdown_left, main_top, breakdown_left + breakdown_w, main_top + table_header_h), fill=colors["soft_fill"], outline=colors["line"])
    draw.text((breakdown_left + S(16), main_top + S(12)), "PRICE BREAKDOWN (INCL. VAT)", font=small_bold_font, fill=colors["ink"])

    bd_y = main_top + table_header_h + S(18)
    for label_lines, value_lines, fill in breakdown_specs:
        line_h = max(block_height(label_lines, S(24)), block_height(value_lines, S(24)))
        draw_text_block(breakdown_left + S(16), bd_y, label_lines, body_font, fill, S(24))
        draw_right_aligned_block(
            breakdown_left + breakdown_w - S(16),
            bd_y,
            "\n".join(value_lines),
            body_font,
            fill,
            S(100),
            S(24),
        )
        bd_y += line_h + S(12)

    draw.line([(breakdown_left + S(16), bd_y + S(6)), (breakdown_left + breakdown_w - S(16), bd_y + S(6))], fill=colors["line_strong"], width=S(1))
    total_box_top = main_top + breakdown_h - total_box_h
    draw.rectangle((breakdown_left, total_box_top, breakdown_left + breakdown_w, main_top + breakdown_h), fill=colors["soft_fill"], outline=colors["line"])
    draw_text_block(breakdown_left + S(16), total_box_top + S(20), total_label_lines[:2], body_bold_font, colors["ink"], S(24))
    total_w = draw.textlength(total_clean, font=fitted_total_font)
    draw.text((breakdown_left + breakdown_w - S(18) - total_w, total_box_top + S(28)), total_clean, font=fitted_total_font, fill=colors["gold"])
    draw.text((breakdown_left + S(16), total_box_top + total_box_h - S(30)), "Amount to be paid by due date.", font=small_font, fill=colors["ink"])

    rut_top = main_top + table_h + S(22)
    rut_detail_x = table_left + S(108)
    rut_lines = [
        ("RUT Deduction Applied:", "YES" if any("RUT" in str(label).upper() for label, _, _ in summary_rows) else "NO"),
    ]
    eligible_label = next((str(value) for label, value, _ in summary_rows if "ELIGIBLE" in str(label).upper()), "-")
    deduction_label = next((str(value) for label, value, _ in summary_rows if "RUT DEDUCTION" in str(label).upper() or "ROT DEDUCTION" in str(label).upper()), "-")
    final_label = total_row[1] if total_row else "-"
    rut_lines.extend([
        ("Eligible Labor Amount:", _clean_money(eligible_label)),
        ("RUT Deduction Amount:", _clean_money(deduction_label)),
        ("Customer Pays After RUT:", _clean_money(final_label)),
    ])
    rut_note = wrap(notes[2] if len(notes) > 2 else "Hembla will apply for the deduction from the Swedish Tax Agency on behalf of the customer.", small_font, table_w - S(160))
    rut_h = max(S(140), S(40) + len(rut_lines) * S(26) + S(14) + block_height(rut_note[:3], S(20)) + S(24))
    card_box(table_left, rut_top, table_w, rut_h)
    section_title(table_left + S(18), rut_top + S(10), _percent_badge_icon((S(24), S(24)), stroke=colors["gold"]), "RUT DEDUCTION INFORMATION")
    rut_icon = _percent_badge_icon((S(62), S(62)), stroke=colors["gold"])
    image.paste(rut_icon, (table_left + S(24), rut_top + S(52)), rut_icon)
    ry = rut_top + S(42)
    for label, value in rut_lines:
        draw.text((rut_detail_x, ry), label, font=body_font, fill=colors["ink"])
        draw.text((rut_detail_x + S(264), ry), str(value), font=body_bold_font if "After RUT" in label else body_font, fill=colors["ink"])
        ry += S(26)
    draw.line([(rut_detail_x, ry - S(2)), (rut_detail_x + S(430), ry - S(2))], fill=colors["line_strong"], width=S(1))
    draw_text_block(rut_detail_x, ry + S(8), rut_note[:3], small_font, colors["muted"], S(20))

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

    payment_value_lines = [wrap(str(value), small_font, footer_col_w - S(124))[:2] for _, value in [
        ("Bank:", company_details.get("bank_details", "-")),
        ("IBAN:", company_details.get("organization_number", "-")),
        ("BIC:", company_details.get("vat_number", "-")),
        ("Reference:", reference_number),
    ]]
    company_wrapped_lines = []
    for line in [
        company_details.get("name", brand_name),
        f"Org.nr: {company_details.get('organization_number', '-')}",
        f"VAT No: {company_details.get('vat_number', '-')}",
        f"F-tax: {company_details.get('f_tax_status', '-')}",
        company_details.get("email", "-"),
        company_details.get("phone", "-"),
    ]:
        font = small_font if ":" in str(line) or "@" in str(line) else small_bold_font
        company_wrapped_lines.append((wrap(str(line), font, footer_col_w - S(32))[:2], font))
    important_wrapped_lines = [wrap(line, small_font, footer_col_w - S(32))[:2] for line in [
        "This invoice is issued in accordance",
        "with the Swedish VAT Act.",
        "Services are eligible for RUT",
        "deduction when applicable.",
        "Keep this invoice for your records.",
    ]]
    payment_h = S(54) + sum(S(26) if len(lines) == 1 else S(40) for lines in payment_value_lines) + S(28)
    company_h = S(54) + sum(S(24) if len(lines) == 1 else S(36) for lines, _font in company_wrapped_lines) + S(26)
    important_h = S(54) + sum(S(22) if len(lines) == 1 else S(34) for lines in important_wrapped_lines) + S(24)
    footer_h = max(S(210), payment_h, company_h, important_h)

    for left, title, icon in zip(footer_positions, footer_titles, footer_icons):
        card_box(left, footer_top, footer_col_w, footer_h)
        image.paste(icon, (left + S(16), footer_top + S(12)), icon)
        draw.text((left + S(48), footer_top + S(14)), title, font=small_bold_font, fill=colors["gold"])

    left = footer_positions[0] + S(16)
    fy = footer_top + S(58)
    payment_lines = [("Bank:", company_details.get("bank_details", "-")), ("IBAN:", company_details.get("organization_number", "-")), ("BIC:", company_details.get("vat_number", "-")), ("Reference:", reference_number)]
    for idx, (label, value) in enumerate(payment_lines):
        draw.text((left, fy), label, font=small_bold_font, fill=colors["ink"])
        value_lines = payment_value_lines[idx]
        draw_text_block(left + S(88), fy, value_lines[:2], small_font, colors["ink"], S(20))
        fy += S(30) if len(value_lines) == 1 else S(46)
    draw.text((left, footer_top + footer_h - S(36)), "Payment is due within 14 days.", font=small_font, fill=colors["muted"])

    left = footer_positions[1] + S(16)
    fy = footer_top + S(58)
    for wrapped, font in company_wrapped_lines:
        draw_text_block(left, fy, wrapped[:2], font, colors["ink"], S(20))
        fy += S(28) if len(wrapped) == 1 else S(42)

    left = footer_positions[2] + S(16)
    fy = footer_top + S(58)
    for wrapped in important_wrapped_lines:
        draw_text_block(left, fy, wrapped[:2], small_font, colors["ink"], S(20))
        fy += S(26) if len(wrapped) == 1 else S(40)

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


def default_logo_path():
    base_dir = Path(getattr(settings, "BASE_DIR"))
    logo_tight = base_dir / "static" / "images" / "logo-tight.png"
    if logo_tight.exists():
        return str(logo_tight)
    return str(base_dir / "static" / "images" / "logo.png")
