"""Basic local smoke tests: no outside network or real API credentials required."""
import json
import os
import sys
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from zipfile import ZipFile

from engine import demo_generate,validate_project
from rendering import pdf_bytes,cover_mockup_jpg
from app import Handler,ThreadingHTTPServer

class SmokeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
  cls.base="http://127.0.0.1:"+str(cls.server.server_port)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
  cls.thread.start()
 @classmethod
 def tearDownClass(cls):
  cls.server.shutdown();cls.server.server_close()
 def post(self,path,body):
  req=Request(self.base+path,data=json.dumps(body).encode(),
              headers={"Content-Type":"application/json"},method="POST")
  with urlopen(req,timeout=15) as resp:return resp.read(),resp.headers

 def test_demo_page_count_and_safe_theme(self):
  p=demo_generate("Beginner herb garden planner with crop calendar",
    "Garden Planner","new gardeners",5,"letter","botanical",True,False)
  self.assertEqual(len(p["pages"]),5)
  self.assertEqual(p["theme"],"botanical")
  self.assertEqual(p["title"],"Beginner Herb Garden Planner")
  self.assertLessEqual(len(p["listing"]["tags"]),13)
  for tag in p["listing"]["tags"]:self.assertLessEqual(len(tag),20)
  self.assertTrue(all(len(page["blocks"])<=3 for page in p["pages"]))

 def test_named_herb_sheets_are_kept_even_if_default_count_is_five(self):
  idea=("Beginner herb garden planner including garden goals, herb wish list, "
        "herb profile sheet, planting planner, watering log, sunlight tracker, "
        "fertilizer tracker, harvest tracker, garden notes and seasonal reflection.")
  raw,_=self.post("/api/generate",{
    "idea":idea,"productType":"Garden Planner","audience":"first-time gardeners",
    "pageCount":5,"paper":"letter","theme":"botanical","mode":"demo"})
  project=json.loads(raw)["project"]
  titles=[p["title"] for p in project["pages"]]
  for name in ("Herb Wish List","Herb Profile Sheet","Garden Goals","Fertilizer Tracker",
               "Sunlight Tracker","Seasonal Reflection"):
   self.assertIn(name,titles)
  self.assertEqual(len(titles),10)
  pdf,_=self.post("/api/export/pdf",{"project":project})
  from pypdf import PdfReader
  reader=PdfReader(BytesIO(pdf))
  self.assertEqual(len(reader.pages),11) # cover + 10 sheets
  all_text=" ".join(page.extract_text() for page in reader.pages)
  self.assertIn("Herb Wish List",all_text)
  self.assertIn("Herb Profile Sheet",all_text)

 def test_pdf_and_mockup_export(self):
  p=demo_generate("Herb garden planner","Garden Planner","beginners",3,"a4","botanical",True,False)
  raw,headers=self.post("/api/export/pdf",{"project":p})
  self.assertTrue(raw.startswith(b"%PDF"))
  self.assertEqual(headers.get_content_type(),"application/pdf")
  from pypdf import PdfReader
  self.assertEqual(len(PdfReader(BytesIO(raw)).pages),4)
  jpg,_=self.post("/api/export/mockup",{"project":p})
  self.assertTrue(jpg.startswith(b"\xff\xd8\xff"))

 def test_download_pack(self):
  p=demo_generate("Weekly reflection journal","Journal","adults",3,"letter","analog",True,True)
  blob,_=self.post("/api/export/pack",{"project":p})
  with ZipFile(BytesIO(blob)) as z:
   names=z.namelist()
   self.assertEqual(len(names),4)
   self.assertTrue(any(x.endswith(".pdf") for x in names))
   self.assertTrue(any(x.endswith("-listing.jpg") for x in names))
   self.assertTrue(any(x.endswith("-etsy-listing.txt") for x in names))
   self.assertTrue(any(x.endswith("-project.json") for x in names))

 def test_save_then_load_project(self):
  p=demo_generate("Study notes printable","Learning Resource","students",3,"letter","playful",True,False)
  raw,_=self.post("/api/projects",{"project":p})
  pid=json.loads(raw)["project"]["id"]
  try:
   with urlopen(self.base+"/api/projects/"+pid) as resp:
    reloaded=json.load(resp)
   self.assertEqual(reloaded["title"],p["title"])
   self.assertEqual(len(reloaded["pages"]),3)
  finally:
   from app import project_file
   project_file(pid).unlink(missing_ok=True)

 def test_no_ai_key_returns_clear_error(self):
  if os.getenv("OPENAI_API_KEY"):self.skipTest("AI key exists; do not make paid API test calls.")
  with self.assertRaises(HTTPError) as raised:
   self.post("/api/generate",{"idea":"Herb journal","productType":"Journal","pageCount":3,
    "mode":"ai"})
  self.assertEqual(raised.exception.code,400)
  detail=json.loads(raised.exception.read())
  self.assertIn("OPENAI_API_KEY",detail["error"])

 def test_bad_path_rejected(self):
  with self.assertRaises(HTTPError):
   urlopen(self.base+"/api/projects/../../.env")


 def test_kdp_pack_pdf_geometry_and_repeat_warning(self):
  from marketplaces import kdp_dimensions
  from pypdf import PdfReader
  p=demo_generate("Herb garden workbook","Garden Planner","adults",5,"letter","botanical",True,False)
  opts={"trim":"6x9","paperStock":"bw_white","pageCount":48}
  blob,_=self.post("/api/export/kdp-pack",{"project":p,"kdp":opts})
  with ZipFile(BytesIO(blob)) as z:
   paths=z.namelist()
   self.assertIn("amazon-kdp/paperback-interior.pdf",paths)
   self.assertIn("amazon-kdp/paperback-wraparound-cover.pdf",paths)
   self.assertIn("amazon-kdp/preflight-checklist.json",paths)
   interior=PdfReader(BytesIO(z.read("amazon-kdp/paperback-interior.pdf")))
   cover=PdfReader(BytesIO(z.read("amazon-kdp/paperback-wraparound-cover.pdf")))
   self.assertEqual(len(interior.pages),48)
   self.assertAlmostEqual(float(interior.pages[0].mediabox.width),432,delta=.05)
   self.assertAlmostEqual(float(interior.pages[0].mediabox.height),648,delta=.05)
   dims=kdp_dimensions(opts)
   self.assertAlmostEqual(float(cover.pages[0].mediabox.width),dims["coverWidthIn"]*72,delta=.05)
   self.assertAlmostEqual(float(cover.pages[0].mediabox.height),dims["coverHeightIn"]*72,delta=.05)
   chk=json.loads(z.read("amazon-kdp/preflight-checklist.json"))
   self.assertTrue(chk["repeatsPages"])

 def test_pinterest_pack_image_and_copy(self):
  from PIL import Image
  p=demo_generate("Herb garden printable","Garden Planner","adults",5,"letter","botanical",True,False)
  blob,_=self.post("/api/export/pinterest-pack",
    {"project":p,"pinterest":{"destinationUrl":"https://www.etsy.com/shop/example"}})
  with ZipFile(BytesIO(blob)) as z:
   self.assertIn("pinterest/pin-1000x1500.jpg",z.namelist())
   img=Image.open(BytesIO(z.read("pinterest/pin-1000x1500.jpg")))
   self.assertEqual(img.size,(1000,1500))
   self.assertIn("https://www.etsy.com/shop/example",
                 z.read("pinterest/pin-copy.txt").decode())

 def test_all_platform_pack(self):
  p=demo_generate("Calm organization planner","Journal","adults",5,"letter","analog",True,False)
  blob,_=self.post("/api/export/all-pack",
    {"project":p,"kdp":{"trim":"8.5x11","paperStock":"bw_cream","pageCount":24}})
  with ZipFile(BytesIO(blob)) as z:
   self.assertIn("etsy/printable.pdf",z.namelist())
   self.assertIn("amazon-kdp/paperback-interior.pdf",z.namelist())
   self.assertIn("pinterest/pin-1000x1500.jpg",z.namelist())
   self.assertIn("editable-project.json",z.namelist())

 def test_kdp_validation(self):
  p=demo_generate("Work book","Learning Resource","students",3,"letter","playful",True,False)
  for bad in (12,25,202):
   with self.subTest(pageCount=bad):
    with self.assertRaises(HTTPError) as ex:
     self.post("/api/export/kdp-pack",
       {"project":p,"kdp":{"trim":"6x9","paperStock":"bw_white","pageCount":bad}})
    self.assertEqual(ex.exception.code,400)

 def test_studio_password_and_public_health(self):
  import base64
  previous=os.environ.get("STUDIO_PASSWORD")
  os.environ["STUDIO_PASSWORD"]="temporary-private-test-password"
  try:
   with urlopen(self.base+"/api/health") as res:
    self.assertTrue(json.load(res)["ok"])
   with self.assertRaises(HTTPError) as ex:
    urlopen(self.base+"/api/projects")
   self.assertEqual(ex.exception.code,401)
   token=base64.b64encode(b"studio:temporary-private-test-password").decode()
   req=Request(self.base+"/api/projects",headers={"Authorization":"Basic "+token})
   with urlopen(req) as res:self.assertIn("projects",json.load(res))
  finally:
   if previous is None:os.environ.pop("STUDIO_PASSWORD",None)
   else:os.environ["STUDIO_PASSWORD"]=previous

if __name__=="__main__":unittest.main(verbosity=2)
