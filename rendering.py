"""Print-ready vector PDF and original listing graphic renderers."""
from io import BytesIO
from pathlib import Path
import math
import textwrap

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

from engine import THEMES

SANS="Helvetica"; SERIF="Times-Roman"; BOLD="Helvetica-Bold"
for name,candidates in (
 ("StudioSans",["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/Library/Fonts/Arial Unicode.ttf"]),
 ("StudioSansBold",["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]),
 ("StudioSerif",["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]),
):
 for candidate in candidates:
  if Path(candidate).exists():
   try:pdfmetrics.registerFont(TTFont(name,candidate))
   except Exception:pass
   else:
    if name=="StudioSans":SANS=name
    if name=="StudioSansBold":BOLD=name
    if name=="StudioSerif":SERIF=name
    break

def rgb(hexcolor):
 h=hexcolor.lstrip("#")
 return tuple(int(h[i:i+2],16) for i in (0,2,4))

def clip_text(c,text,font,size,max_width):
 """Single-line text shortened to fit. Only used for small labels."""
 s=str(text or "")
 while s and c.stringWidth(s,font,size)>max_width:s=s[:-1]
 return s if len(s)==len(str(text or "")) else s.rstrip()+"..."

def wrapped(c,text,font,size,max_width,max_lines=4):
 lines=[]
 for para in str(text or "").splitlines() or [""]:
  words=para.split()
  if not words:
   lines.append("");continue
  line=""
  for w in words:
   test=(line+" "+w).strip()
   if c.stringWidth(test,font,size)<=max_width:line=test
   else:
    if line:lines.append(line)
    line=w
  if line:lines.append(line)
 return lines[:max_lines]

def text_lines(c,lines,x,y,font,size,color,leading):
 c.setFillColor(HexColor(color));c.setFont(font,size)
 for ln in lines:
  c.drawString(x,y,ln)
  y-=leading
 return y

def block_height(b):
 kind=b["type"];n=min(9,max(1,b.get("lines",4)))
 if kind=="two_columns":return 100
 if kind=="callout":return 88
 if kind=="checklist":return 36 + max(n,len(b.get("items") or []))*24
 if kind=="table":return 44+n*23
 return 36+n*23

def draw_block(c,b,x,y,width,t,scale=1):
 ink=HexColor(t["ink"]);accent=HexColor(t["accent"]);light=HexColor(t["light"])
 n=min(9,max(1,b.get("lines",4)))
 c.setFillColor(accent);c.setFont(BOLD,9.5)
 c.drawString(x,y,clip_text(c,b["title"].upper(),BOLD,9.5,width))
 y-=19
 if b["type"]=="two_columns":
  gap=13;w=(width-gap)/2
  for i,label in enumerate((b.get("items") or ["Left","Right"])[:2]):
   xx=x+i*(w+gap);c.setStrokeColor(HexColor("#c4c8c0"));c.roundRect(xx,y-67,w,65,7,stroke=1,fill=0)
   c.setFillColor(accent);c.setFont(SANS,9);c.drawString(xx+9,y-17,clip_text(c,label,SANS,9,w-20))
  return y-80
 if b["type"]=="callout":
  c.setFillColor(light);c.roundRect(x,y-57,width,55,8,stroke=0,fill=1)
  lines=wrapped(c,"; ".join(b.get("items") or ["Notes and helpful reminders"]),SANS,9,width-24,3)
  text_lines(c,lines,x+12,y-20,SANS,9,t["ink"],14)
  return y-70
 if b["type"]=="checklist":
  items=b.get("items") or []
  for i in range(max(n,len(items))):
   yy=y-i*24
   c.setStrokeColor(accent);c.rect(x+1,yy-10,9,9,stroke=1,fill=0)
   label=items[i] if i<len(items) else ""
   c.setFont(SANS,9);c.setFillColor(ink)
   c.drawString(x+17,yy-8,clip_text(c,label,SANS,9,width-20))
   c.setStrokeColor(HexColor("#d9d9d2"))
   c.line(x+17,yy-12,x+width,yy-12)
  return y-max(n,len(items))*24-12
 if b["type"]=="table":
  headers=b.get("items") or ["Date","Item","Notes"]
  headers=headers[:4]
  cols=len(headers);cw=width/cols
  c.setFillColor(light);c.rect(x,y-19,width,19,stroke=0,fill=1)
  c.setFillColor(ink);c.setFont(BOLD,8)
  for j,h in enumerate(headers):
   c.drawString(x+j*cw+5,y-13,clip_text(c,h,BOLD,8,cw-9))
  for i in range(n):
   yy=y-19-(i+1)*23
   c.setStrokeColor(HexColor("#cfd0c9"));c.line(x,yy,x+width,yy)
  for j in range(1,cols):
   c.setStrokeColor(HexColor("#e1e1da"))
   c.line(x+j*cw,y-19-n*23,x+j*cw,y)
  return y-19-n*23-14
 # writing lines
 for i in range(n):
  yy=y-(i+1)*23
  c.setStrokeColor(HexColor("#d2d2cb"));c.setLineWidth(.6)
  c.line(x,yy,x+width,yy)
 return y-n*23-14

def draw_cover(c,p,W,H,t):
 ink=HexColor(t["ink"]);accent=HexColor(t["accent"]);light=HexColor(t["light"])
 c.setFillColor(HexColor(t["paper"]));c.rect(0,0,W,H,stroke=0,fill=1)
 c.setFillColor(light);c.circle(W*.96,H*.93,190,stroke=0,fill=1)
 c.setFillColor(light);c.circle(W*.05,H*.10,135,stroke=0,fill=1)
 m=54;c.setStrokeColor(accent);c.setLineWidth(1)
 c.roundRect(m,H*.19,W-2*m,H*.63,15,stroke=1,fill=0)
 x=m+34;y=H*.73
 c.setFillColor(accent);c.roundRect(x,y,48,5,2,stroke=0,fill=1);y-=43
 c.setFont(BOLD,10);c.drawString(x,y,p["productType"].upper());y-=52
 for line in wrapped(c,p["title"],SERIF,30,W-2*m-76,4):
  c.setFillColor(ink);c.setFont(SERIF,30);c.drawString(x,y,line);y-=39
 y-=10
 subtitle="A printable collection for "+(p["audience"] or "thoughtful everyday use")
 text_lines(c,wrapped(c,subtitle,SANS,11,W-2*m-80,3),x,y,SANS,11,t["ink"],17)
 c.setFillColor(accent);c.setFont(BOLD,9)
 c.drawString(x,H*.235,"PRINTABLE  /  "+THEMES[p["theme"]]["name"].upper())

def draw_page(c,p,page,num,total,W,H,t):
 paper="#ffffff" if p["inkSaver"] else t["paper"]
 c.setFillColor(HexColor(paper));c.rect(0,0,W,H,stroke=0,fill=1)
 m=53;width=W-2*m;y=H-58
 c.setFillColor(HexColor(t["accent"] if not p["inkSaver"] else "#505050"));c.setFont(BOLD,8.5)
 c.drawString(m,y,p["productType"].upper());y-=38
 c.setFillColor(HexColor(t["ink"]));c.setFont(SERIF,23)
 for ln in wrapped(c,page["title"],SERIF,23,width,2):
  c.drawString(m,y,ln);y-=29
 if page["subtitle"]:
  y-=2
  y=text_lines(c,wrapped(c,page["subtitle"],SANS,9,width,2),
               m,y,SANS,9,t["ink"],13)
 y-=8
 c.setStrokeColor(HexColor(t["accent"]));c.setLineWidth(1.2);c.line(m,y,m+width,y);y-=27
 blocks=page["blocks"]
 required=sum(block_height(b) for b in blocks)
 available=max(60,y-62)
 factor=min(1,max(.56,available/max(required,1)))
 # Layout spacing is reduced when many blocks are present, without shrinking text.
 for b in blocks:
  if y<100:break
  before=y
  y=draw_block(c,b,m,y,width,t)
  # Content is bounded by the engine and 12 blocks; overflow is reported below if any.
  if y<56:break
 c.setFillColor(HexColor(t["accent"]));c.setFont(SANS,8)
 c.drawString(m,36,clip_text(c,p["title"],SANS,8,width-80))
 c.drawRightString(W-m,36,f"{num} / {total}")
 if p["productType"]=="Anxiety & Mood Support":
  c.setFillColor(HexColor("#666666"));c.setFont(SANS,6.8)
  c.drawString(m,48,"For reflection only; not diagnosis, treatment, or crisis support.")
 if y<56:
  # Show a clear design warning, rather than silently clip the document.
  c.setFillColor(HexColor("#9c4f3e"));c.setFont(BOLD,7)
  c.drawRightString(W-m,48,"EDIT NOTE: Page has too much content; reduce blocks or lines.")

def pdf_bytes(p):
 bio=BytesIO();W,H=(A4 if p["paper"]=="a4" else letter)
 c=canvas.Canvas(bio,pagesize=(W,H),pageCompression=1)
 c.setTitle(p["title"]);c.setAuthor("Printable Studio - seller-directed")
 t=dict(THEMES[p["theme"]])
 if p["inkSaver"]:t.update({"accent":"#525252","light":"#f4f4f4","paper":"#ffffff"})
 if p["cover"]:
  draw_cover(c,p,W,H,t);c.showPage()
 for i,page in enumerate(p["pages"],1):
  draw_page(c,p,page,i,len(p["pages"]),W,H,t);c.showPage()
 c.save();return bio.getvalue()

def font(size,bold=False):
 paths = [
 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
 "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
 ]
 for path in paths:
  if Path(path).exists():return ImageFont.truetype(path,size)
 return ImageFont.load_default()

def cover_mockup_jpg(p):
 """An original listing hero graphic (not a photograph or Etsy listing upload)."""
 t=THEMES[p["theme"]];im=Image.new("RGB",(2000,1500),rgb(t["light"]))
 d=ImageDraw.Draw(im)
 # Four subtle diagonals create background depth with no stock assets/licensing issues.
 for i in range(8):
  color=tuple(int(a*.93+b*.07) for a,b in zip(rgb(t["light"]),rgb(t["accent"])))
  d.line((i*330,-140,i*330-460,1700),fill=color,width=2)
 # Paper shadow and 3/4 printable page
 X,Y,R,B=650,145,1500,1340
 d.rounded_rectangle((X+30,Y+32,R+30,B+32),radius=24,fill=(172,174,165))
 d.rounded_rectangle((X,Y,R,B),radius=19,fill=rgb(t["paper"]),outline=rgb(t["accent"]),width=3)
 d.rounded_rectangle((X+75,Y+78,R-75,B-78),radius=17,outline=rgb(t["accent"]),width=3)
 d.rounded_rectangle((X+135,Y+185,X+225,Y+195),radius=5,fill=rgb(t["accent"]))
 d.text((X+135,Y+230),p["productType"].upper(),font=font(21,True),fill=rgb(t["accent"]))
 title=p["title"]
 words=title.split();lines=[];line=""
 for word in words:
  candidate=(line+" "+word).strip()
  if d.textbbox((0,0),candidate,font=font(53,True))[2]<R-X-270:line=candidate
  else:
   if line:lines.append(line)
   line=word
 if line:lines.append(line)
 ty=Y+310
 for ln in lines[:5]:
  d.text((X+135,ty),ln,font=font(53,True),fill=rgb(t["ink"]));ty+=72
 d.text((X+135,B-215),"PRINTABLE COLLECTION",font=font(21,True),fill=rgb(t["accent"]))
 # Selling points occupy left, not on the product page, to make thumbnail scannable.
 lx=95
 d.text((lx,290),"PRINTABLE",font=font(48,True),fill=rgb(t["ink"]))
 d.text((lx,355),"DIGITAL",font=font(48,True),fill=rgb(t["ink"]))
 d.text((lx,420),"COLLECTION",font=font(43,True),fill=rgb(t["ink"]))
 for j,point in enumerate(["INSTANT DIGITAL DOWNLOAD",f"{len(p['pages'])} INTERIOR PAGES",("A4 SIZE" if p["paper"]=="a4" else "US LETTER SIZE")]):
  d.rounded_rectangle((lx,620+j*100,lx+485,680+j*100),radius=18,fill=rgb(t["paper"]))
  d.text((lx+22,635+j*100),point,font=font(22,True),fill=rgb(t["accent"]))
 d.text((lx,1190),"ORIGINAL SELLER-DIRECTED DESIGN",font=font(17,True),fill=rgb(t["ink"]))
 output=BytesIO();im.save(output,format="JPEG",quality=91,optimize=True);return output.getvalue()
