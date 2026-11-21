"""Render the sample documents in this folder from invoice_extractor.samples.SAMPLES.

    pip install reportlab pypdfium2 pillow
    python samples/make_samples.py

Also writes previews/<file>.png, which the app shows next to the extracted fields.
"""

import random
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from invoice_extractor.samples import SAMPLES  # noqa: E402

PREVIEWS = ROOT / "previews"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

STYLE = {
    "northwind": dict(accent="#1f4e79", lang="en", symbol="£"),
    "druckerei": dict(accent="#8a1c1c", lang="de", symbol="€"),
    "stratus": dict(accent="#3b2f8f", lang="en", symbol="$"),
    "brightclean": dict(accent="#0f766e", lang="en", symbol="£"),
}
LABELS = {
    "en": dict(title="INVOICE", number="Invoice no.", date="Invoice date", due="Due date", to="Bill to",
               desc="Description", qty="Qty", unit="Unit price", vat="VAT", amount="Amount", sub="Subtotal",
               tax="VAT", total="Total due", vatno="VAT no.", terms="Terms"),
    "de": dict(title="RECHNUNG", number="Rechnungsnr.", date="Rechnungsdatum", due="Fällig am", to="Rechnung an",
               desc="Beschreibung", qty="Menge", unit="Einzelpreis", vat="USt.", amount="Betrag", sub="Nettobetrag",
               tax="Umsatzsteuer", total="Gesamtbetrag", vatno="USt-IdNr.", terms="Zahlungsbedingungen"),
}


def money(x: float, lang: str, symbol: str) -> str:
    s = f"{x:,.2f}"
    if lang == "de":
        return s.replace(",", "_").replace(".", ",").replace("_", ".") + f" {symbol}"
    return f"{symbol}{s}"


def fmt_date(d: str, lang: str) -> str:
    y, m, day = d.split("-")
    return f"{day}.{m}.{y}" if lang == "de" else f"{int(day)} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(m)-1]} {y}"


def qty(q: float, lang: str) -> str:
    s = f"{q:g}" if q < 1000 else f"{q:,.0f}"
    return s.replace(".", ",") if lang == "de" else s


def unit_price(p: float, lang: str, symbol: str) -> str:
    if p < 1 and round(p, 2) != p:
        s = f"{symbol}{p:.3f}"
        return s.replace(".", ",") if lang == "de" else s
    return money(p, lang, symbol)


def render_pdf(path: Path, inv, style: dict) -> None:
    L, lang, sym = LABELS[style["lang"]], style["lang"], style["symbol"]
    accent = colors.HexColor(style["accent"])
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"{inv.vendor_name} {inv.invoice_number}")
    w, h = A4
    c.setFillColor(accent)
    c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(18 * mm, h - 20 * mm, inv.vendor_name)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, h - 27 * mm, inv.vendor_address)
    c.drawString(18 * mm, h - 32 * mm, f"{L['vatno']} {inv.vendor_tax_id}")
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(w - 18 * mm, h - 22 * mm, L["title"])

    c.setFillColor(colors.HexColor("#222222"))
    y = h - 54 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, y, L["to"].upper())
    c.setFont("Helvetica", 10)
    c.drawString(18 * mm, y - 6 * mm, inv.customer_name or "")
    c.drawString(18 * mm, y - 11 * mm, "22 Canal Wharf, London N1 9RT" if lang == "en" else "22 Canal Wharf, London N1 9RT, UK")
    meta = [(L["number"], inv.invoice_number), (L["date"], fmt_date(inv.invoice_date, lang))]
    if inv.due_date:
        meta.append((L["due"], fmt_date(inv.due_date, lang)))
    for i, (k, v) in enumerate(meta):
        c.setFont("Helvetica", 9)
        c.drawRightString(w - 55 * mm, y - i * 6 * mm, k)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(w - 18 * mm, y - i * 6 * mm, v)

    y = h - 82 * mm
    cols = [18 * mm, 112 * mm, 135 * mm, 160 * mm, w - 18 * mm]
    c.setFillColor(colors.HexColor("#f1f3f6"))
    c.rect(15 * mm, y - 2.5 * mm, w - 30 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols[0], y, L["desc"])
    c.drawRightString(cols[1] + 14 * mm, y, L["qty"])
    c.drawRightString(cols[2] + 20 * mm, y, L["unit"])
    c.drawRightString(cols[3] + 8 * mm, y, L["vat"])
    c.drawRightString(cols[4], y, L["amount"])
    c.setFont("Helvetica", 9.5)
    for li in inv.line_items:
        y -= 9 * mm
        c.drawString(cols[0], y, li.description)
        c.drawRightString(cols[1] + 14 * mm, y, qty(li.quantity, lang))
        c.drawRightString(cols[2] + 20 * mm, y, unit_price(li.unit_price, lang, sym))
        c.drawRightString(cols[3] + 8 * mm, y, f"{li.vat_rate:g}%")
        c.drawRightString(cols[4], y, money(li.amount, lang, sym))
        c.setStrokeColor(colors.HexColor("#e3e6eb"))
        c.line(15 * mm, y - 3.5 * mm, w - 15 * mm, y - 3.5 * mm)

    y -= 16 * mm
    rows = [(L["sub"], inv.subtotal), (L["tax"], inv.vat_total)]
    if lang == "de":
        rows = [(L["sub"], inv.subtotal), ("USt. 19 %", 90.92), ("USt. 7 %", 82.95)]
    for k, v in rows:
        c.setFont("Helvetica", 10)
        c.drawRightString(w - 55 * mm, y, k)
        c.drawRightString(w - 18 * mm, y, money(v, lang, sym))
        y -= 7 * mm
    c.setFillColor(accent)
    c.rect(w - 100 * mm, y - 4 * mm, 85 * mm, 10 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 55 * mm, y - 0.5 * mm, L["total"])
    c.drawRightString(w - 18 * mm, y - 0.5 * mm, money(inv.total, lang, sym))

    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, 40 * mm, f"{L['terms']}: {inv.payment_terms}")
    if inv.vat_total == 0:
        c.drawString(18 * mm, 34 * mm, "Reverse charge: VAT to be accounted for by the recipient (Art. 196 EU VAT Directive).")
    c.drawString(18 * mm, 28 * mm, "Fictional sample document generated for the Invoice Extractor demo.")
    c.save()


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def render_receipt(path: Path, inv) -> Image.Image:
    W = 560
    img = Image.new("RGB", (W, 1180), "#fbf8f1")
    d = ImageDraw.Draw(img)
    mono, bold = font("DejaVuSansMono.ttf", 22), font("DejaVuSansMono-Bold.ttf", 30)
    y = 40

    def center(text, f=mono, gap=34):
        nonlocal y
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, fill="#2a2a2a", font=f)
        y += gap

    def row(left, right, f=mono):
        nonlocal y
        d.text((40, y), left, fill="#2a2a2a", font=f)
        d.text((W - 40 - d.textlength(right, font=f), y), right, fill="#2a2a2a", font=f)
        y += 34

    center("CAFFÈ ROMA", bold, 44)
    center("di L. Bianchi")
    center("Via dei Coronari 41")
    center("00186 Roma")
    center("P.IVA 04417230585", gap=50)
    center("DOCUMENTO COMMERCIALE")
    center("di vendita o prestazione", gap=46)
    row("DESCRIZIONE", "IVA  PREZZO(€)")
    prices = {"Cappuccino": 1.80, "Cornetto integrale": 1.50, "Tramezzino": 4.20, "Acqua frizzante 0,5": 1.50}
    for li in inv.line_items:
        gross = prices[li.description] * li.quantity
        label = f"{li.quantity:g} x {li.description}"[:24]
        row(label, f"10%  {gross:.2f}".replace(".", ","))
    y += 10
    d.line((40, y, W - 40, y), fill="#2a2a2a", width=2)
    y += 16
    row("TOTALE COMPLESSIVO", "19,80", font("DejaVuSansMono-Bold.ttf", 24))
    row("di cui IVA", "1,80")
    row("Pagamento elettronico", "19,80")
    row("Importo pagato", "19,80")
    y += 20
    center("21-10-2026 09:47")
    center("DOCUMENTO N. 0127-0042")
    center("RT 99MEX014327", gap=60)
    center("GRAZIE E ARRIVEDERCI!")
    # handwritten tip
    d.text((330, y + 10), "+ 2,00 mancia", fill="#1d3fa8", font=font("DejaVuSerif-Bold.ttf", 26))
    img = img.crop((0, 0, W, y + 80))

    # photo effect: slight rotation on a table, soft shadow, noise and blur
    rot = img.rotate(-2.2, expand=True, fillcolor=(0, 0, 0, 0), resample=Image.BICUBIC)
    mask = Image.new("L", img.size, 255).rotate(-2.2, expand=True)
    bg = Image.new("RGB", (rot.width + 160, rot.height + 160), "#6b5a48")
    rnd = random.Random(7)
    px = bg.load()
    for _ in range(25000):
        x, yy = rnd.randrange(bg.width), rnd.randrange(bg.height)
        v = rnd.randint(-18, 18)
        r, g, b = px[x, yy]
        px[x, yy] = (r + v, g + v, b + v)
    shadow = Image.new("L", bg.size, 0)
    shadow.paste(mask, (92, 96))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    bg.paste(Image.new("RGB", bg.size, "#2b241d"), (0, 0), shadow.point(lambda v: v * 0.6))
    bg.paste(rot, (80, 80), mask)
    bg = bg.filter(ImageFilter.GaussianBlur(0.7))
    bg.save(path, quality=86)
    return bg


def scan_of(pdf_path: Path, out: Path) -> Image.Image:
    page = pdfium.PdfDocument(str(pdf_path))[0].render(scale=1.6).to_pil()
    gray = ImageOps.grayscale(page).rotate(0.9, expand=True, fillcolor=245, resample=Image.BICUBIC)
    rnd = random.Random(3)
    px = gray.load()
    for _ in range(40000):
        x, y = rnd.randrange(gray.width), rnd.randrange(gray.height)
        px[x, y] = max(0, min(255, px[x, y] + rnd.randint(-40, 25)))
    gray = ImageOps.autocontrast(gray.filter(ImageFilter.GaussianBlur(0.6)), cutoff=1)
    gray.save(out, optimize=True)
    return gray


def main() -> None:
    PREVIEWS.mkdir(exist_ok=True)
    for name, inv in SAMPLES:
        path = ROOT / name
        key = name.split("-")[0]
        if name.endswith(".pdf"):
            render_pdf(path, inv, STYLE[key])
            preview = pdfium.PdfDocument(str(path))[0].render(scale=1.3).to_pil()
        elif name.endswith(".jpg"):
            preview = render_receipt(path, inv)
        else:
            preview = scan_of(ROOT / "northwind-INV-20417.pdf", path)
        preview.thumbnail((900, 1300))
        preview.convert("RGB").save(PREVIEWS / f"{name}.jpg", quality=82)
        print("wrote", name)


if __name__ == "__main__":
    main()
