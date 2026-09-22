"""Printable Studio single-user, password-protected cloud-ready development server.

Run: python app.py
Optional: OPENAI_API_KEY for AI mode; Etsy env vars for OAuth and drafts.
This is a localhost prototype, not a multi-user/public production server.
"""
import base64
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zipfile import ZipFile, ZIP_DEFLATED

from engine import demo_generate, ai_generate, validate_project, safe_id, MATCH, THEMES
from rendering import pdf_bytes, cover_mockup_jpg
from marketplaces import marketplace_pack, kdp_options, kdp_interior_pdf, kdp_cover_pdf, pin_jpg

BASE=Path(__file__).resolve().parent
from dotenv import load_dotenv
load_dotenv(BASE/".env")
DATA=Path(os.getenv("STUDIO_DATA_DIR",str(BASE/"data")))/"projects"
DATA.mkdir(parents=True,exist_ok=True)
LOCK=threading.Lock()
OAUTH={}   # Local single-user memory only. Production needs encrypted, per-user storage.
ETSY_API="https://api.etsy.com/v3"

def json_bytes(value):return json.dumps(value,ensure_ascii=False,indent=2).encode("utf-8")
def project_file(pid):
 if not safe_id(pid):raise ValueError("Invalid project ID.")
 return DATA/f"{pid}.json"
def file_stem(value):
 import re
 return re.sub(r"[^a-z0-9]+","-",value.lower()).strip("-")[:56] or "printable"

def etsy_enabled():
 return all(os.getenv(x) for x in ("ETSY_KEYSTRING","ETSY_SHARED_SECRET","ETSY_REDIRECT_URI","ETSY_SHOP_ID"))
def etsy_headers():
 return {"x-api-key":os.environ["ETSY_KEYSTRING"]+":"+os.environ["ETSY_SHARED_SECRET"],
         "Authorization":"Bearer "+OAUTH["token"]}
def etsy_call(path,data=None,form=False,file=None,method="POST"):
 headers=etsy_headers()
 if file is not None:
  name,blob,mime=file
  boundary="----PrintableStudio"+secrets.token_hex(12)
  body=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{name}.{ 'pdf' if mime=='application/pdf' else 'jpg'}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n").encode()+blob+(f"\r\n--{boundary}--\r\n").encode()
  headers["Content-Type"]="multipart/form-data; boundary="+boundary
 elif form:
  headers["Content-Type"]="application/x-www-form-urlencoded"
  body=urlencode(data or {},doseq=True).encode()
 else:
  body=json_bytes(data or {})
  headers["Content-Type"]="application/json"
 request=Request(ETSY_API+path,data=body,method=method,headers=headers)
 try:
  with urlopen(request,timeout=50) as res:return json.load(res)
 except HTTPError as ex:
  detail=ex.read(500).decode("utf-8","replace")
  raise RuntimeError(f"Etsy returned HTTP {ex.code}. {detail[:280]}")

def publish_etsy_draft(p,price,taxonomy_id):
 if not etsy_enabled():raise RuntimeError("Etsy credentials and shop ID are not configured.")
 if "token" not in OAUTH:raise RuntimeError("Connect your Etsy shop first.")
 if OAUTH.get("expires",0)<time.time()+30:raise RuntimeError("Etsy session expired; reconnect your shop.")
 try:
  price_v=float(price)
  tax=int(taxonomy_id)
  if price_v<.20 or price_v>1000 or tax<1:raise ValueError()
 except (TypeError,ValueError):
  raise ValueError("Provide a valid USD price and Etsy taxonomy ID.")
 shop=os.environ["ETSY_SHOP_ID"]
 listing=p["listing"]
 draft=etsy_call(f"/application/shops/{shop}/listings",{
  "quantity":999,"title":listing["title"],"description":listing["description"]+
    ("\n\nAI USE DISCLOSURE\n"+listing["aiDisclosure"] if listing["aiDisclosure"] else ""),
  "price":f"{price_v:.2f}","who_made":"i_did","when_made":"made_to_order",
  "taxonomy_id":tax,"type":"download",
  "tags":listing["tags"]
 },form=True)
 listing_id=draft.get("listing_id")
 if not listing_id:raise RuntimeError("Etsy did not return a listing ID.")
 # These uploads are made to a DRAFT only; do not activate or publish live.
 errors=[]
 try:
  etsy_call(f"/application/shops/{shop}/listings/{listing_id}/files",
            file=("file",pdf_bytes(p),"application/pdf"))
 except Exception as exc:errors.append("PDF upload: "+str(exc))
 try:
  etsy_call(f"/application/shops/{shop}/listings/{listing_id}/images",
            file=("image",cover_mockup_jpg(p),"image/jpeg"))
 except Exception as exc:errors.append("Image upload: "+str(exc))
 return {"listing_id":listing_id,"draft_url":f"https://www.etsy.com/your/shops/me/tools/listings/{listing_id}",
         "upload_errors":errors,"note":"Draft created only. Review and publish from Etsy."}

class Handler(BaseHTTPRequestHandler):
 server_version="PrintableStudio/4.0"
 def log_message(self,fmt,*args):print("[%s] %s"%(self.log_date_time_string(),fmt%args))
 def headers_common(self,mime):
  self.send_header("Content-Type",mime)
  self.send_header("X-Content-Type-Options","nosniff")
  self.send_header("Cache-Control","no-store")
  self.send_header("Referrer-Policy","no-referrer")
  self.send_header("X-Frame-Options","DENY")
  self.send_header("Content-Security-Policy","frame-ancestors 'none'")
  self.send_header("Access-Control-Allow-Origin","null") if False else None
 def send_blob(self,data,mime,status=200,filename=None):
  self.send_response(status)
  self.headers_common(mime)
  self.send_header("Content-Length",str(len(data)))
  if filename:self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
  self.end_headers();self.wfile.write(data)
 def send_json(self,data,status=200):self.send_blob(json_bytes(data),"application/json; charset=utf-8",status)
 def fail(self,ex,status=400):self.send_json({"error":str(ex)[:380]},status)
 def get_json(self):
  try:n=int(self.headers.get("Content-Length","0"))
  except ValueError:raise ValueError("Invalid request size.")
  if n<1 or n>2_500_000:raise ValueError("Expected JSON request under 2.5 MB.")
  raw=self.rfile.read(n)
  data=json.loads(raw)
  if not isinstance(data,dict):raise ValueError("Expected a JSON object.")
  origin=self.headers.get("Origin","")
  if origin and urlparse(origin).netloc != self.headers.get("Host"):
   raise ValueError("Cross-origin changes are not permitted.")
  return data
 def redirect(self,url):
  self.send_response(302);self.send_header("Location",url)
  self.send_header("Cache-Control","no-store");self.end_headers()
 def authorized(self):
  """Protect UI and APIs with one-user Basic Auth; deny unconfigured cloud deployments."""
  required=os.getenv("STUDIO_PASSWORD","")
  on_cloud=bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
  if not required and not on_cloud:return True
  header=self.headers.get("Authorization","")
  if required and header.startswith("Basic "):
   try:
    username,password=base64.b64decode(header[6:],validate=True).decode().split(":",1)
    if hmac.compare_digest(username,"studio") and hmac.compare_digest(password,required):
     return True
   except (ValueError,UnicodeDecodeError,base64.binascii.Error):pass
  self.send_response(401 if required else 503)
  self.headers_common("text/plain; charset=utf-8")
  if required:self.send_header("WWW-Authenticate",'Basic realm="Printable Studio"')
  message=b"Printable Studio requires STUDIO_PASSWORD before public deployment."
  self.send_header("Content-Length",str(len(message)))
  self.end_headers();self.wfile.write(message)
  return False
 def do_GET(self):
  path=urlparse(self.path).path
  try:
   if path=="/api/health":
    cloud=bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
    if cloud and not os.getenv("STUDIO_PASSWORD"):
     self.send_json({"ok":False,"error":"Set STUDIO_PASSWORD before deploying."},503)
    else:self.send_json({"ok":True,"service":"printable-studio"})
    return
   if not self.authorized():return
   if path in ("/","/index.html"):
    self.send_blob((BASE/"static"/"index.html").read_bytes(),"text/html; charset=utf-8");return
   if path in ("/style.css","/app.js"):
    mime="text/css" if path.endswith("css") else "application/javascript"
    self.send_blob((BASE/"static"/path.lstrip("/")).read_bytes(),mime+"; charset=utf-8");return
   if path=="/api/config":
    self.send_json({"aiConfigured":bool(os.getenv("OPENAI_API_KEY")),
      "aiModel":os.getenv("OPENAI_MODEL","gpt-4.1-mini"),
      "etsyConfigured":etsy_enabled(),"etsyConnected":bool(OAUTH.get("token")),
      "themes":THEMES,"productTypes":list(MATCH)});return
   if path=="/api/projects":
    result=[]
    for file in DATA.glob("*.json"):
     try:
      p=json.loads(file.read_text(encoding="utf-8"))
      result.append({"id":p["id"],"title":p["title"],
        "productType":p["productType"],"updated":file.stat().st_mtime})
     except (OSError,KeyError,ValueError):continue
    result.sort(key=lambda x:x["updated"],reverse=True)
    self.send_json({"projects":result[:100]});return
   if path.startswith("/api/projects/"):
    self.send_json(json.loads(project_file(path.split("/")[-1]).read_text(encoding="utf-8")));return
   if path=="/api/etsy/connect":
    if not etsy_enabled():raise RuntimeError("Set ETSY_KEYSTRING, ETSY_SHARED_SECRET, ETSY_SHOP_ID and ETSY_REDIRECT_URI.")
    verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state=secrets.token_urlsafe(24)
    OAUTH["verifier"]=verifier;OAUTH["state"]=state
    self.redirect("https://www.etsy.com/oauth/connect?"+urlencode({
      "response_type":"code","client_id":os.environ["ETSY_KEYSTRING"],
      "redirect_uri":os.environ["ETSY_REDIRECT_URI"],"scope":"listings_r listings_w",
      "state":state,"code_challenge":challenge,"code_challenge_method":"S256"
    }));return
   if path=="/api/etsy/callback":
    qs=parse_qs(urlparse(self.path).query)
    if not OAUTH.get("state") or qs.get("state",[""])[0]!=OAUTH.pop("state",None):
     raise ValueError("Invalid or expired Etsy authorization state.")
    code=qs.get("code",[""])[0]
    if not code:raise ValueError("Etsy did not provide an authorization code.")
    data=urlencode({"grant_type":"authorization_code",
      "client_id":os.environ["ETSY_KEYSTRING"],
      "redirect_uri":os.environ["ETSY_REDIRECT_URI"],
      "code":code,"code_verifier":OAUTH.pop("verifier")}).encode()
    req=Request(ETSY_API+"/public/oauth/token",data=data,
                headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    with urlopen(req,timeout=30) as response:token=json.load(response)
    OAUTH["token"]=token["access_token"]
    OAUTH["expires"]=time.time()+int(token.get("expires_in",3600))
    self.redirect("/?etsy=connected");return
   self.fail("Not found.",404)
  except FileNotFoundError:self.fail("Not found.",404)
  except (RuntimeError,ValueError,KeyError,HTTPError) as ex:self.fail(ex,400)
  except Exception as ex:self.fail("Unexpected server error; see terminal.",500);self.log_message("Error: %s",ex)
 def do_POST(self):
  path=urlparse(self.path).path
  try:
   if not self.authorized():return
   body=self.get_json()
   if path=="/api/generate":
    idea=str(body.get("idea") or "").strip()
    if not idea or len(idea)>1100:raise ValueError("Enter an idea under 1100 characters.")
    product=body.get("productType","Custom Printable")
    if product not in MATCH:raise ValueError("Unknown product type.")
    try:count=int(body.get("pageCount",5))
    except (ValueError,TypeError):raise ValueError("Page count must be a number.")
    if count<1 or count>24:raise ValueError("Generate 1 to 24 pages per product.")
    theme=body.get("theme") or MATCH[product]
    if theme=="auto":theme=MATCH[product]
    if theme not in THEMES:raise ValueError("Unknown visual theme.")
    args=(idea,product,str(body.get("audience") or "")[:100],count,
          body.get("paper","letter"),theme,bool(body.get("cover",True)),bool(body.get("inkSaver",False)))
    mode=body.get("mode","demo")
    if mode=="ai":p=ai_generate(*args)
    elif mode=="demo":p=demo_generate(*args)
    else:raise ValueError("Choose Demo or AI mode.")
    self.send_json({"project":p,"mode":mode});return
   if path=="/api/projects":
    p=validate_project(body.get("project",{}))
    with LOCK:
     dest=project_file(p["id"]);temp=dest.with_suffix(".tmp")
     temp.write_bytes(json_bytes(p));temp.replace(dest)
    self.send_json({"project":p,"saved":True});return
   if path in ("/api/export/pdf","/api/export/mockup","/api/export/pack"):
    p=validate_project(body.get("project",{}));stem=file_stem(p["title"])
    if path.endswith("/pdf"):
     self.send_blob(pdf_bytes(p),"application/pdf",filename=stem+".pdf");return
    if path.endswith("/mockup"):
     self.send_blob(cover_mockup_jpg(p),"image/jpeg",filename=stem+"-listing.jpg");return
    buf=BytesIO()
    with ZipFile(buf,"w",ZIP_DEFLATED) as z:
     z.writestr(stem+".pdf",pdf_bytes(p))
     z.writestr(stem+"-listing.jpg",cover_mockup_jpg(p))
     l=p["listing"]
     z.writestr(stem+"-etsy-listing.txt",
       f"TITLE\n{l['title']}\n\nDESCRIPTION\n{l['description']}\n\nTAGS\n{', '.join(l['tags'])}\n\nAI DISCLOSURE\n{l['aiDisclosure']}\n")
     z.writestr(stem+"-project.json",json_bytes(p))
    self.send_blob(buf.getvalue(),"application/zip",filename=stem+"-etsy-pack.zip");return
   if path in ("/api/export/etsy-pack","/api/export/kdp-pack",
               "/api/export/pinterest-pack","/api/export/all-pack",
               "/api/export/kdp-interior","/api/export/kdp-cover","/api/export/pin"):
    p=validate_project(body.get("project",{}))
    stem=file_stem(p["title"])
    k=body.get("kdp",{})
    pin=body.get("pinterest",{})
    if path.endswith("/kdp-interior"):
     self.send_blob(kdp_interior_pdf(p,kdp_options(k)),"application/pdf",
                    filename=stem+"-kdp-interior.pdf");return
    if path.endswith("/kdp-cover"):
     self.send_blob(kdp_cover_pdf(p,kdp_options(k)),"application/pdf",
                    filename=stem+"-kdp-cover.pdf");return
    if path.endswith("/pin"):
     self.send_blob(pin_jpg(p),"image/jpeg",filename=stem+"-pin-1000x1500.jpg");return
    kind=path.split("/")[-1].removesuffix("-pack")
    self.send_blob(marketplace_pack(p,kind,k,pin),"application/zip",
                   filename=stem+"-"+kind+"-pack.zip");return
   if path=="/api/etsy/draft":
    if not body.get("sellerApproved"):raise ValueError("Review and approve the product before creating an Etsy draft.")
    p=validate_project(body.get("project",{}))
    result=publish_etsy_draft(p,body.get("price"),body.get("taxonomy_id"))
    self.send_json(result);return
   self.fail("Not found.",404)
  except (ValueError,RuntimeError,KeyError,json.JSONDecodeError) as ex:self.fail(ex,400)
  except Exception as ex:self.fail("Unexpected server error; see terminal.",500);self.log_message("Error: %s",ex)

if __name__=="__main__":
 from dotenv import load_dotenv
 load_dotenv(BASE/".env")
 port=int(os.getenv("PORT","8765"))
 host=os.getenv("HOST","0.0.0.0" if os.getenv("RAILWAY_ENVIRONMENT") else "127.0.0.1")
 print(f"Printable Studio 4.0: http://{host}:{port}")
 print("AI mode:", "configured" if os.getenv("OPENAI_API_KEY") else "not configured (Demo works)")
 print("Etsy:", "configured" if etsy_enabled() else "not configured (export pack works)")
 ThreadingHTTPServer((host,port),Handler).serve_forever()
