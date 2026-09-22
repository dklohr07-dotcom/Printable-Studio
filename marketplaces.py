"""Platform-specific, seller-review-ready export packages.

Etsy = home-print PDFs; KDP = no-bleed print interiors and wraparound cover;
Pinterest = 2:3 promotional image and copy. Does not publish or promise acceptance.
"""
import json
import math
import re
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from urllib.parse import urlparse

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit

from engine import THEMES
from rendering import (
    SANS, BOLD, SERIF, clip_text, cover_mockup_jpg, font, pdf_bytes, rgb,
)

PT = 72
TRIMS = {"6x9": (6.0, 9.0), "8.5x11": (8.5, 11.0)}
STOCKS = {
    "bw_white": {"name": "Black-and-white, white paper", "spine": .002252},
    "bw_cream": {"name": "Black-and-white, cream paper", "spine": .0025},
    "color_white": {"name": "Premium color, white paper", "spine": .002347},
}
MAX_KDP_PAGES = 200


def kdp_options(data):
    data = data if isinstance(data, dict) else {}
    trim = str(data.get("trim", "8.5x11"))
    stock = str(data.get("paperStock", "bw_white"))
    if trim not in TRIMS or stock not in STOCKS:
        raise ValueError("Choose a supported KDP trim size and paper stock.")
    try:
        count = int(data.get("pageCount", 48))
    except (TypeError, ValueError):
        raise ValueError("KDP page count must be a whole number.")
    if not 24 <= count <= MAX_KDP_PAGES:
        raise ValueError("Choose 24 to 200 KDP interior pages.")
    if count % 2:
        raise ValueError("Choose an even KDP interior page count.")
    return {"trim": trim, "paperStock": stock, "pageCount": count}


def pin_options(data):
    data = data if isinstance(data, dict) else {}
    url = str(data.get("destinationUrl", "")).strip()[:400]
    if url and (urlparse(url).scheme not in {"http", "https"} or not urlparse(url).netloc):
        raise ValueError("Pinterest destination needs a complete http(s) product URL.")
    return {"destinationUrl": url}


def kdp_dimensions(opts):
    w, h = TRIMS[opts["trim"]]
    spine = opts["pageCount"] * STOCKS[opts["paperStock"]]["spine"]
    return {
        "trimWidthIn": w,
        "trimHeightIn": h,
        "spineWidthIn": round(spine, 5),
        "interiorWidthIn": w,
        "interiorHeightIn": h,
        "coverWidthIn": round(2 * w + spine + .25, 5),
        "coverHeightIn": h + .25,
        "interiorBleed": "none",
        "coverBleedIn": .125,
        "paperStock": STOCKS[opts["paperStock"]]["name"],
    }


def _fit_lines(c, value, face, size, width, maximum):
    """Bound paragraphs to page width, including overlong single words."""
    lines = []
    for word in str(value).split():
        if c.stringWidth(word, face, size) > width:
            while c.stringWidth(word, face, size) > width:
                word = word[:-1]
            word = word or " "
        if not lines:
            lines.append(word)
        elif c.stringWidth(lines[-1] + " " + word, face, size) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines[:maximum]


def _section(c, block, x, y, width, min_y, theme, compact=False, fill_space=False):
    """Draw one complete block, shrinking writing space if necessary, never cutting labels."""
    kind = block["type"]
    remaining = max(0, y - min_y)
    row = 19 if compact else 22
    heading = 10 if compact else 11
    max_rows = max(1, int((remaining - 38) / row))
    requested = max(1, min(18, int(block.get("lines", 3))))
    if fill_space and kind in {"lines","table","checklist"}:
        requested = max(requested, min(18, max(1, int((remaining-50)/row))))
    n = min(requested, max_rows)
    if remaining < 46:
        return y, False
    c.setFillColor(HexColor(theme["ink"]))
    c.setFont(BOLD, 8.2 if compact else 9)
    title = clip_text(c, block.get("title", "Notes"), BOLD, 8.2 if compact else 9, width)
    c.drawString(x, y, title)
    y -= heading + 9
    accent = HexColor("#777777" if compact else theme["accent"])
    line = HexColor("#c9c9c6")
    if kind == "two_columns":
        box_h = min(69, max(45, y - min_y - 5))
        gap = 11
        w = (width - gap) / 2
        for i, label in enumerate((block.get("items") or ["First", "Second"])[:2]):
            xx = x + i * (w + gap)
            c.setStrokeColor(line); c.roundRect(xx, y-box_h, w, box_h, 6, stroke=1, fill=0)
            c.setFont(SANS, 8);c.setFillColor(accent)
            c.drawString(xx+8, y-15, clip_text(c, label, SANS, 8, w-16))
        y -= box_h + 14
    elif kind == "callout":
        box_h = min(69, max(42,y-min_y-6))
        c.setFillColor(HexColor("#f6f6f3" if compact else theme["light"]))
        c.roundRect(x,y-box_h,width,box_h,7,stroke=0,fill=1)
        c.setFillColor(HexColor(theme["ink"]));c.setFont(SANS,8)
        for i, line_text in enumerate(_fit_lines(c,"; ".join(block.get("items") or ["Notes"]),SANS,8,width-20,3)):
            c.drawString(x+10,y-15-i*11,line_text)
        y-=box_h+14
    elif kind == "table":
        headers=(block.get("items") or ["Date","Entry","Notes"])[:4]
        count=max(1,len(headers));cell_w=width/count
        c.setStrokeColor(line);c.setFillColor(accent);c.setFont(BOLD,7.3)
        for j,h in enumerate(headers):c.drawString(x+j*cell_w+4,y-10,clip_text(c,h,BOLD,7.3,cell_w-8))
        c.line(x,y-15,x+width,y-15)
        y -= 15
        n = min(n,max(1,int((y-min_y-12)/row)))
        for k in range(n):
            c.line(x,y-row*(k+1),x+width,y-row*(k+1))
        for j in range(1,count):
            c.line(x+j*cell_w,y,x+j*cell_w,y-n*row)
        y-=n*row+13
    elif kind == "checklist":
        labels=(block.get("items") or [])[:n]
        n=min(n,max(1,int((y-min_y-12)/row)))
        for i in range(n):
            yy=y-i*row
            c.setStrokeColor(accent);c.rect(x,yy-9,8,8,fill=0,stroke=1)
            if i<len(labels):
                c.setFillColor(HexColor(theme["ink"]));c.setFont(SANS,7.8)
                c.drawString(x+14,yy-8,clip_text(c,labels[i],SANS,7.8,width-18))
            c.setStrokeColor(line);c.line(x+14,yy-12,x+width,yy-12)
        y-=n*row+13
    else:
        n=min(n,max(1,int((y-min_y-12)/row)))
        c.setStrokeColor(line);c.setLineWidth(.75)
        for i in range(n):
            c.line(x,y-row*(i+1),x+width,y-row*(i+1))
        y-=n*row+13
    return y, True


def kdp_interior_pdf(p, opts):
    """No-bleed trim-size paperback interior; even/odd pages have mirrored safe gutters."""
    w_in,h_in=TRIMS[opts["trim"]]
    W,H=w_in*PT,h_in*PT
    count=opts["pageCount"]
    bio=BytesIO()
    c=canvas.Canvas(bio,pagesize=(W,H),pageCompression=1)
    c.setTitle(p["title"]+" - KDP interior")
    c.setAuthor("Seller-directed Printable Studio project")
    theme=dict(THEMES[p["theme"]])
    if opts["paperStock"].startswith("bw_"):
        theme.update({"ink":"#282828","accent":"#595959","light":"#f2f2f2"})
    for i in range(count):
        page=p["pages"][i % len(p["pages"])]
        # KDP's 24-150 page gutter minimum is .375 inch; use a larger buffer.
        inside=.64*PT
        outside=.48*PT
        left,right=(inside,outside) if i%2==0 else (outside,inside)
        x=left;width=W-left-right
        c.setFillColor(HexColor("#ffffff"));c.rect(0,0,W,H,fill=1,stroke=0)
        c.setStrokeColor(HexColor(theme["accent"]));c.setLineWidth(1.5)
        y=H-54
        c.line(x,y,x+32,y)
        c.setFillColor(HexColor(theme["accent"]));c.setFont(BOLD,8)
        c.drawString(x,y-16,p["productType"].upper()[:45])
        y-=58
        c.setFillColor(HexColor(theme["ink"]));c.setFont(SERIF,19 if w_in<7 else 22)
        for ln in _fit_lines(c,page["title"],SERIF,19 if w_in<7 else 22,width,2):
            c.drawString(x,y,ln);y-=27
        if page.get("subtitle"):
            for ln in _fit_lines(c,page["subtitle"],SANS,7.5,width,2):
                c.setFont(SANS,7.5);c.drawString(x,y-1,ln);y-=11
        y-=18
        blocks=page["blocks"]
        compact=w_in<7 or len(blocks)>2
        min_y=63
        reserve=(len(blocks)-1)*50
        overflow=False
        for j,b in enumerate(blocks):
            remaining_blocks=len(blocks)-j-1
            target=min_y + remaining_blocks*50
            y,ok=_section(c,b,x,y,width,target,theme,compact,fill_space=(j==len(blocks)-1))
            if not ok:overflow=True
        if overflow:
            # Explicit review banner rather than hiding failed elements.
            c.setFillColor(HexColor("#933c35"));c.setFont(BOLD,7)
            c.drawString(x,50,"LAYOUT REVIEW: simplify this worksheet before publishing.")
        c.setStrokeColor(HexColor("#d7d7d4"));c.line(x,44,x+width,44)
        c.setFillColor(HexColor("#666666"));c.setFont(SANS,7)
        c.drawString(x,32,clip_text(c,p["title"],SANS,7,width-55))
        c.drawRightString(x+width,32,str(i+1))
        c.showPage()
    c.save()
    return bio.getvalue()


def draw_botanical_sprig(c, cx, cy, scale, color):
    """Original, reproducible vector leaf illustration."""
    c.saveState();c.translate(cx,cy);c.scale(scale,scale)
    c.setStrokeColor(HexColor(color));c.setLineWidth(1.45)
    branch=c.beginPath()
    branch.moveTo(0,0);branch.curveTo(-2,37,11,68,25,108);branch.curveTo(27,119,38,139,48,157)
    c.drawPath(branch,stroke=1,fill=0)
    for x,y,angle,size in ((3,23,-44,26),(13,49,42,28),(12,70,-42,26),
                            (27,96,43,31),(30,118,-40,25),(42,142,34,26)):
        c.saveState();c.translate(x,y);c.rotate(angle)
        leaf=c.beginPath();leaf.moveTo(0,0)
        leaf.curveTo(size*.36,size*.22,size*.57,size*.75,size*.98,size)
        leaf.curveTo(size*.25,size*.94,-size*.1,size*.5,0,0)
        c.drawPath(leaf,fill=0,stroke=1);c.restoreState()
    c.restoreState()


def kdp_cover_pdf(p,opts):
    """Single-page back | spine | front cover with 0.125-inch outer bleed."""
    d=kdp_dimensions(opts); tw=d["trimWidthIn"]*PT;th=d["trimHeightIn"]*PT
    spine=d["spineWidthIn"]*PT; bleed=.125*PT
    W=(2*tw+spine+2*bleed); H=th+2*bleed
    buf=BytesIO()
    c=canvas.Canvas(buf,pagesize=(W,H),pageCompression=1)
    c.setTitle(p["title"]+" - KDP wraparound cover")
    theme=THEMES[p["theme"]]
    c.setFillColor(HexColor(theme["paper"]));c.rect(0,0,W,H,stroke=0,fill=1)
    c.setFillColor(HexColor(theme["light"]))
    c.circle(W*.91,H*.83,min(tw*.38,130),fill=1,stroke=0)
    c.circle(W*.17,H*.12,min(tw*.28,110),fill=1,stroke=0)
    # Back panel (left) with a generous reserved barcode space.
    back_x=bleed
    c.setFillColor(HexColor(theme["accent"]));c.roundRect(back_x+32,H-92,45,5,2,fill=1,stroke=0)
    c.setFont(SERIF,21 if tw<500 else 26);c.setFillColor(HexColor(theme["ink"]))
    by=H-135
    for ln in _fit_lines(c,p["title"],SERIF,21 if tw<500 else 26,tw-76,3):
        c.drawString(back_x+32,by,ln);by-=32
    by-=22
    text=p["idea"][:220]
    for ln in _fit_lines(c,text,SANS,10,tw-76,9):
        c.setFont(SANS,10);c.drawString(back_x+32,by,ln);by-=15
    c.setFillColor(HexColor(theme["paper"]))
    c.roundRect(back_x+tw-170,bleed+29,149,99,5,fill=1,stroke=0)
    # Avoid barcode text or decoration: KDP may add its own barcode here.
    c.setStrokeColor(HexColor("#d3d1ca"))
    c.roundRect(back_x+tw-170,bleed+29,149,99,5,fill=0,stroke=1)
    # Spine: colored, no text. Compatible with fewer than 79 interior pages.
    c.setFillColor(HexColor(theme["accent"]))
    c.rect(bleed+tw,0,spine,H,fill=1,stroke=0)
    # Front panel begins immediately after spine.
    fx=bleed+tw+spine
    c.setStrokeColor(HexColor(theme["accent"]));c.setLineWidth(1.1)
    c.roundRect(fx+26,bleed+38,tw-52,th-76,11,fill=0,stroke=1)
    c.setFillColor(HexColor(theme["accent"]));c.roundRect(fx+55,H-122,51,5,2,fill=1,stroke=0)
    c.setFont(BOLD,9);c.drawString(fx+55,H-153,clip_text(c,p["productType"].upper(),BOLD,9,tw-110))
    cy=H-213
    fsize=26 if tw<500 else 34
    for ln in _fit_lines(c,p["title"],SERIF,fsize,tw-110,5):
        c.setFillColor(HexColor(theme["ink"]));c.setFont(SERIF,fsize)
        c.drawString(fx+55,cy,ln);cy-=fsize*1.22
    cy-=24
    for ln in _fit_lines(c,"A workbook and planner for "+(p["audience"] or "everyday life"),
                         SANS,10,tw-110,3):
        c.setFont(SANS,10);c.drawString(fx+55,cy,ln);cy-=15
    draw_botanical_sprig(c,fx+tw*.59,bleed+134,1.1 if tw<500 else 1.5,theme["accent"])
    c.setFont(BOLD,9);c.setFillColor(HexColor(theme["accent"]))
    c.drawString(fx+55,bleed+75,"WORKBOOK  /  PLANNER  /  PRINT EDITION")
    c.showPage();c.save()
    return buf.getvalue()


def pin_jpg(p):
    """Original 1000x1500 JPEG promotional artwork; no implied lifestyle photograph."""
    from PIL import ImageFont
    t=THEMES[p["theme"]]
    im=Image.new("RGB",(1000,1500),rgb(t["light"]))
    d=ImageDraw.Draw(im)
    def f(n,bold=False):return font(n,bold)
    ink=rgb(t["ink"]);accent=rgb(t["accent"]);paper=rgb(t["paper"])
    # Editorial headline
    d.rounded_rectangle((67,68,184,79),radius=5,fill=accent)
    d.text((69,109),"PRINTABLE",font=f(61,True),fill=ink)
    d.text((69,181),"COLLECTION",font=f(61,True),fill=ink)
    # stacked stationery pages with subtle offset shadow
    for x0,y0,x1,y1 in ((231,373,870,1268),(174,339,813,1234),(118,309,757,1204)):
        d.rounded_rectangle((x0+15,y0+18,x1+15,y1+18),radius=15,fill=(174,178,168))
        d.rounded_rectangle((x0,y0,x1,y1),radius=13,fill=paper,outline=accent,width=2)
    d.rounded_rectangle((175,365,698,1140),radius=10,outline=accent,width=2)
    d.rounded_rectangle((213,434,273,441),radius=3,fill=accent)
    d.text((213,472),p["productType"].upper()[:31],font=f(21,True),fill=accent)
    words=p["title"].split()
    lines=[];current=""
    for word in words:
        candidate=(current+" "+word).strip()
        if d.textbbox((0,0),candidate,font=f(40,True))[2] < 435:
            current=candidate
        else:
            if current:lines.append(current)
            current=word
    if current:lines.append(current)
    for i,ln in enumerate(lines[:6]):d.text((213,565+i*53),ln,font=f(40,True),fill=ink)
    d.text((213,922),p["pages"][0]["title"][:27],font=f(21,True),fill=accent)
    for i in range(5):
        yy=969+i*35;d.line((213,yy,651,yy),fill=(191,193,183),width=2)
    d.rounded_rectangle((66,1320,932,1429),radius=20,fill=accent)
    d.text((96,1344),"EXPLORE THE PRINTABLE",font=f(37,True),fill=(255,255,255))
    out=BytesIO();im.save(out,"JPEG",quality=91,optimize=True)
    return out.getvalue()


def pin_copy(p,opts):
    dest=opts["destinationUrl"] or "[ADD YOUR LIVE ETSY OR AMAZON PRODUCT URL]"
    name=p["title"]
    title=(name+" | Printable "+p["productType"])[:100]
    desc=(f"Explore {name}, a {p['productType'].lower()} collection designed for "
          f"{p['audience'] or 'everyday planning'}. See the preview and details before buying. "
          f"Digital printable or print-book availability depends on the linked shop.")
    return f"PIN TITLE\n{title}\n\nPIN DESCRIPTION\n{desc[:800]}\n\nDESTINATION URL\n{dest}\n\nALT TEXT\nEditorial graphic showing a coordinated printable {p['productType'].lower()} called {name}.\n"


def etsy_copy(p):
    l=p["listing"]
    return (
        f"TITLE\n{l['title']}\n\nDESCRIPTION\n{l['description']}\n\n"
        f"TAGS\n{', '.join(l['tags'])}\n\nAI DISCLOSURE\n{l['aiDisclosure']}\n"
    )


def kdp_checklist(p,opts):
    d=kdp_dimensions(opts)
    page_types=len(p["pages"])
    repeated=opts["pageCount"]>page_types
    details=[
        "Review every page for accuracy, readability, writing space, and clipped content.",
        "Confirm the chosen trim, paper, and page count match your KDP setup exactly.",
        "Preview both PDFs in KDP's Print Previewer and fix any reported issues.",
        "Use your own ISBN decision and confirm low-content classification where applicable.",
        "Confirm the barcode area is clear and check the finished cover template.",
        "Review Amazon KDP's current AI-generated content disclosure rules.",
        "Order a physical proof before making the paperback available to customers.",
    ]
    if repeated:
        details.insert(0,
          f"IMPORTANT: {page_types} distinct worksheet pages were repeated to make "
          f"{opts['pageCount']} interior pages. Edit/expand content before selling a guided workbook.")
    return {
        "status":"PRODUCTION FILES: seller proof and KDP preview required; not guaranteed acceptance",
        "trim":opts["trim"],"dimensions":d,"pageCount":opts["pageCount"],
        "distinctWorksheetPages":page_types,"repeatsPages":repeated,
        "recommendation":"For fuller workbooks, create additional distinct pages before the paperback release.",
        "tasks":details,
        "source":"https://kdp.amazon.com/en_US/help/topic/G201857950",
    }


def add_etsy(z,p,prefix):
    z.writestr(prefix+"printable.pdf",pdf_bytes(p))
    z.writestr(prefix+"listing-hero.jpg",cover_mockup_jpg(p))
    z.writestr(prefix+"listing-copy.txt",etsy_copy(p))
    z.writestr(prefix+"review-before-selling.txt",
        "Check PDF page sizes, spelling, unique seller creative contribution, licensed elements, "
        "pricing, listing accuracy, Etsy AI disclosure and current upload limits.\n")


def add_kdp(z,p,prefix,opts):
    z.writestr(prefix+"paperback-interior.pdf",kdp_interior_pdf(p,opts))
    z.writestr(prefix+"paperback-wraparound-cover.pdf",kdp_cover_pdf(p,opts))
    chk=kdp_checklist(p,opts)
    z.writestr(prefix+"preflight-checklist.json",json.dumps(chk,indent=2))
    z.writestr(prefix+"metadata-draft.txt",
      "BOOK TITLE\n"+p["title"]+"\n\nBOOK DESCRIPTION (EDIT BEFORE USE)\n"+
      p["idea"]+"\n\nSELLER REVIEW\nConfirm originality, category, keywords, and AI-use disclosure.\n")


def add_pinterest(z,p,prefix,opts):
    z.writestr(prefix+"pin-1000x1500.jpg",pin_jpg(p))
    z.writestr(prefix+"pin-copy.txt",pin_copy(p,opts))
    z.writestr(prefix+"pin-checklist.txt",
      "Add a live product URL, check that the landing page matches the Pin, "
      "review accessibility alt text and copy, and publish manually in Pinterest.\n")


def marketplace_pack(p,kind,kdp=None,pinterest=None):
    if kind not in {"etsy","kdp","pinterest","all"}:
        raise ValueError("Unknown marketplace package.")
    k=kdp_options(kdp) if kind in {"kdp","all"} else None
    pin=pin_options(pinterest) if kind in {"pinterest","all"} else None
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        if kind in {"etsy","all"}:add_etsy(z,p,"etsy/")
        if kind in {"kdp","all"}:add_kdp(z,p,"amazon-kdp/",k)
        if kind in {"pinterest","all"}:add_pinterest(z,p,"pinterest/",pin)
        z.writestr("editable-project.json",json.dumps(p,ensure_ascii=False,indent=2))
        z.writestr("START-HERE.txt",
          "Printable Studio 4.0 - seller review package\n\n"
          "Files are production drafts, not automatically published or guaranteed to meet "
          "a marketplace's current acceptance requirements. Verify all exports and disclosure.\n"
          "Etsy: https://www.etsy.com/legal/creativity/\n"
          "KDP: https://kdp.amazon.com/en_US/help/topic/G201857950\n"
          "Pinterest: https://help.pinterest.com/en/business/article/pinterest-product-specs\n")
    return out.getvalue()
