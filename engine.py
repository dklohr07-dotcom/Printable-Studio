"""Content planner, deterministic demo mode, and optional server-side AI generation."""
import json
import os
import re
import urllib.error
import urllib.request
import uuid

THEMES = {
 "botanical":{"name":"Tactile Botanical","ink":"#293128","accent":"#58725b","light":"#e4ece0","paper":"#fffefa"},
 "editorial":{"name":"Editorial Calm","ink":"#272722","accent":"#465646","light":"#edf0e9","paper":"#fffefa"},
 "analog":{"name":"Analog Notes","ink":"#302f2a","accent":"#9b623f","light":"#f2e8d8","paper":"#fffcf7"},
 "blue":{"name":"Cool Blue Modern","ink":"#202d3b","accent":"#4f83a5","light":"#e5f1f6","paper":"#ffffff"},
 "persimmon":{"name":"Persimmon Pop","ink":"#382822","accent":"#d86645","light":"#f8e2d8","paper":"#fffaf6"},
 "plum":{"name":"Plum Editorial","ink":"#2e2230","accent":"#59364f","light":"#eee4eb","paper":"#fffafd"},
 "playful":{"name":"Playful Learning","ink":"#26302b","accent":"#627e72","light":"#e4eee7","paper":"#fffdf7"},
}
MATCH = {"Journal":"analog", "Garden Planner":"botanical","Menu":"persimmon",
         "Organizational Chart":"editorial","Anxiety & Mood Support":"blue",
         "Learning Resource":"playful","Custom Printable":"editorial"}

# Allowed field types are purposefully restricted: AI output cannot render HTML or JS.
BLOCK_TYPES = {"lines", "two_columns", "table", "checklist", "callout"}
MAX_PAGES = 32

def clean(value, limit=400):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]

def safe_id(value):
    return bool(re.fullmatch(r"[a-f0-9]{32}",str(value)))

def block(kind,title,lines=3,items=None):
    return {"type":kind, "title":clean(title,90), "lines":max(0,min(6,int(lines))),
            "items":[clean(x,80) for x in (items or [])][:12]}

def ideas_for(product, subject):
    """Meaningful offline starter templates, personalized with the idea."""
    if product=="Garden Planner":
        return [
          ("Garden Vision", [block("two_columns","Growing conditions",items=["Sun exposure","Growing zone"]),block("lines","My goal for "+subject,4)]),
          ("Planting Calendar",[block("table","Planting plan",6,["Plant / variety","Sow date","Harvest estimate"])]),
          ("Watering Tracker",[block("table","Watering and care",7,["Date","Plant or bed","Water / notes"])]),
          ("Garden Layout",[block("two_columns","Bed / container map",items=["Area A","Area B"]),block("lines","Spacing and companion notes",5)]),
          ("Harvest Notes",[block("table","Harvest log",6,["Crop","Date","Quantity"]),block("lines","What I would change",3)]),
        ]
    if product=="Journal":
        return [
          ("Daily Reflection",[block("lines","What matters today",4),block("lines","What I want to remember",5)]),
          ("Intention Setting",[block("two_columns","Today and tomorrow",items=["Priorities","Boundaries"]),block("lines","One achievable step",4)]),
          ("Gratitude Page",[block("lines","Three moments I appreciate",6),block("lines","A small delight",4)]),
          ("Weekly Review",[block("two_columns","Reflections",items=["What helped","What drained me"]),block("lines","My next chapter",4)]),
        ]
    if product=="Menu":
        return [
          ("Menu Concept",[block("two_columns","Event basics",items=["Occasion","Guests"]),block("lines","Creative direction",4)]),
          ("Weekly Menu",[block("table","Meal plan",7,["Day","Main","Side"])]),
          ("Shopping List",[block("checklist","Ingredients and supplies",7,["Produce","Pantry","Protein","Other"])]),
          ("Recipe Card",[block("lines","Ingredients",5),block("lines","Preparation",5)]),
          ("Budget Planner",[block("table","Ingredient costs",6,["Item","Quantity","Cost"])]),
        ]
    if product=="Organizational Chart":
        return [
          ("Team Overview",[block("lines","Mission and ownership",4),block("two_columns","Key roles",items=["Leadership","Operations"])]),
          ("Reporting Structure",[block("two_columns","Org hierarchy",items=["Team A","Team B"]),block("table","Roles and reporting",5,["Role","Reports to","Owner"])]),
          ("Responsibilities",[block("table","Role clarity",6,["Person","Function","Decision rights"])]),
          ("People Directory",[block("table","Team contacts",7,["Name","Role","Contact"])]),
        ]
    if product=="Anxiety & Mood Support":
        return [
          ("Gentle Check-In",[block("two_columns","How I am feeling",items=["Energy 1-10","Mood 1-10"]),block("lines","What I notice",5)]),
          ("Grounding Practice",[block("checklist","Five-senses grounding",5,["5 things I can see","4 I can feel","3 I can hear","2 I can smell","1 I can taste"])]),
          ("Supportive Thoughts",[block("lines","What happened?",3),block("lines","A kinder perspective",5)]),
          ("Personal Support Map",[block("two_columns","Support options",items=["People to reach out to","Activities that help"]),block("lines","A manageable next step",4)]),
        ]
    if product=="Learning Resource":
        return [
          ("Learning Goals",[block("lines","What I want to understand about "+subject,4),block("two_columns","Starting point",items=["What I know","My questions"])]),
          ("Concept Notes",[block("lines","Key ideas",6),block("lines","Worked example",4)]),
          ("Practice",[block("lines","Try it yourself",5),block("lines","What I learned",4)]),
          ("Vocabulary",[block("table","Words to know",6,["Word","Meaning","Example"])]),
          ("Review",[block("checklist","Learning check",5,["I can explain the key idea","I can give an example","I know what to study next"])]),
        ]
    return [
      ("Overview",[block("lines","My focus for "+subject,5),block("two_columns","Quick ideas",items=["Ideas","Actions"])]),
      ("Working Sheet",[block("lines","Notes",8)]),
      ("Progress Tracker",[block("checklist","My next steps",7,["Start","Continue","Finish"])]),
    ]

def validate_project(data):
    """Normalize untrusted data from AI or browser; avoid HTML rendering/excess PDF pages."""
    if not isinstance(data,dict): raise ValueError("Project must be an object")
    product=clean(data.get("productType") or "Custom Printable",45)
    if product not in MATCH: product="Custom Printable"
    idea=clean(data.get("idea") or "Untitled printable idea",1100)
    theme=clean(data.get("theme") or MATCH[product],30)
    if theme not in THEMES:theme=MATCH[product]
    pgs=data.get("pages") or []
    if not isinstance(pgs,list): raise ValueError("Pages must be an array")
    pages=[]
    for page in pgs[:MAX_PAGES]:
        if not isinstance(page,dict):continue
        raw_blocks=page.get("blocks") or []
        if not isinstance(raw_blocks,list):raw_blocks=[]
        blocks=[]
        for raw in raw_blocks[:3]:
            if not isinstance(raw,dict):continue
            kind=clean(raw.get("type"),20)
            if kind not in BLOCK_TYPES:kind="lines"
            try:n=int(raw.get("lines",4))
            except (ValueError,TypeError):n=4
            items=raw.get("items") if isinstance(raw.get("items"),list) else []
            blocks.append(block(kind,raw.get("title") or "Notes",n,items))
        if not blocks:blocks=[block("lines","Notes",5)]
        pages.append({"title":clean(page.get("title") or "Worksheet",90),
                      "subtitle":clean(page.get("subtitle") or "",200),
                      "blocks":blocks})
    if not pages:raise ValueError("At least one page is required")
    listing=data.get("listing") if isinstance(data.get("listing"),dict) else {}
    tags=listing.get("tags") if isinstance(listing.get("tags"),list) else []
    unique=[]
    for item in tags:
        tag=clean(item,20).strip(",.; ")
        if tag and tag.lower() not in [x.lower() for x in unique]:unique.append(tag)
    return {
     "id":clean(data.get("id") or uuid.uuid4().hex,32) if safe_id(data.get("id")) else uuid.uuid4().hex,
     "title":clean(data.get("title") or "My Printable Collection",110),
     "idea":idea,"productType":product,"audience":clean(data.get("audience"),100),
     "theme":theme,"paper":data.get("paper") if data.get("paper") in ("letter","a4") else "letter",
     "cover":bool(data.get("cover",True)),"inkSaver":bool(data.get("inkSaver",False)),
     "pages":pages,"listing":{
       "title":clean(listing.get("title"),140),
       "description":str(listing.get("description") or "")[:3500],
       "tags":unique[:13],
       "aiDisclosure":clean(listing.get("aiDisclosure"),350)
      }
    }

def listing_for(title,idea,product,audience):
    tags=[product.lower(),"printable planner","digital download","pdf worksheets",
          "instant download",audience.lower() if audience else "printable pages"]
    if product=="Anxiety & Mood Support":tags=["mood journal","reflection pages","wellness printable","grounding worksheet","digital download"]
    tags=[x[:20] for x in dict.fromkeys(tags)]
    desc=(f"{title}\n\nAn editable, coordinated {product.lower()} printable set designed around: {idea}.\n\n"
          "WHAT YOU RECEIVE\n- A printable PDF with coordinated cover and worksheet pages\n"
          "- US Letter or A4 layout, as selected\n- Digital download; no physical item is shipped\n\n"
          "Print at home or through a local print shop. Printer settings and colors may vary.\n")
    if product=="Anxiety & Mood Support":
        desc+="\nWELLNESS NOTE\nFor general personal reflection only. Not diagnosis, treatment, crisis support, or a replacement for professional care.\n"
    return {"title":clean(f"{title} | {product} Printable PDF Digital Download",140),
            "description":desc,"tags":tags[:13],
            "aiDisclosure":"AI-assisted content/design developed from the seller's original idea and creative direction; reviewed and edited by the seller."}

def demo_generate(idea,product,audience,page_count,paper,theme,cover,ink_saver):
    subject=clean(re.split(r"\b(?:with|including|featuring|that)\b", idea.split(".")[0], maxsplit=1, flags=re.I)[0],70) or product
    subject=re.sub(r"^(?:a|an|the)\s+", "", subject, flags=re.I).strip(" .,:;-")
    title=clean(subject.title(),85)
    starters=ideas_for(product,subject)
    pages=[]
    for i in range(max(1,min(MAX_PAGES,page_count))):
        heading,blocks=starters[i%len(starters)]
        if i>=len(starters):heading+=f" · {i//len(starters)+1}"
        pages.append({"title":heading,
                      "subtitle":clean(f"{subject} · {audience or 'personal planning'}",140),
                      "blocks":blocks})
    return validate_project({"title":title,"idea":idea,"productType":product,"audience":audience,
        "theme":theme,"paper":paper,"cover":cover,"inkSaver":ink_saver,"pages":pages,
        "listing":listing_for(title,idea,product,audience)})

AI_PAGE_SCHEMA={
 "type":"object","additionalProperties":False,
 "properties":{
   "title":{"type":"string"},"subtitle":{"type":"string"},
   "blocks":{"type":"array","items":{"type":"object","additionalProperties":False,
     "properties":{"type":{"type":"string","enum":sorted(BLOCK_TYPES)},
                   "title":{"type":"string"},"lines":{"type":"integer"},
                   "items":{"type":"array","items":{"type":"string"}}},
     "required":["type","title","lines","items"]}}},
 "required":["title","subtitle","blocks"]
}
AI_SCHEMA={
 "type":"object","additionalProperties":False,
 "properties":{"title":{"type":"string"},"pages":{"type":"array","items":AI_PAGE_SCHEMA},
   "listing":{"type":"object","additionalProperties":False,
    "properties":{"title":{"type":"string"},"description":{"type":"string"},
      "tags":{"type":"array","items":{"type":"string"}},
      "aiDisclosure":{"type":"string"}},
    "required":["title","description","tags","aiDisclosure"]}},
 "required":["title","pages","listing"]
}

def ai_generate(idea,product,audience,count,paper,theme,cover,ink_saver):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:raise RuntimeError("OPENAI_API_KEY is not configured; choose Demo mode.")
    instructions=(
      "You create ORIGINAL, useful, high-quality printable products for a human seller to edit and approve. "
      "Return JSON matching schema exactly. Each page must contain 2-4 varied blocks and enough writing space; "
      "avoid duplicating page content and generic repetitive worksheets. Make the requested idea central. "
      "For wellness topics, create only non-clinical reflection and organizational tools; no diagnosis, "
      "treatment claims, medication instructions, or crisis interventions. Do not claim commercial success "
      "or pretend to have researched Etsy search volume. No copyrighted characters or imitations of living artists. "
      "tags: max 13 distinct, each at most 20 characters; title <=140 chars. "
      "All pages and all block headings must be specific and useful. "
      "Use 'table' for trackers, 'checklist' for action pages, 'lines' for prompts, "
      "'two_columns' for paired planning, 'callout' for tips. "
      "lines=2..7; items contain 2..5 labels for table/columns/checklist. "
      "Include explicit seller-prompted AI disclosure. "
      "Return exactly the specified number of pages."
    )
    payload={
     "model":os.getenv("OPENAI_MODEL","gpt-4.1-mini"),
     "instructions":instructions,
     "input":json.dumps({"idea":idea,"productType":product,"audience":audience,
                          "pageCount":count,"pageSize":paper,"style":THEMES[theme]["name"]},
                         ensure_ascii=False),
     "text":{"format":{"type":"json_schema","name":"printable_project",
                       "schema":AI_SCHEMA,"strict":True}},
     "max_output_tokens":min(12000,max(3500,count*750))
    }
    req=urllib.request.Request("https://api.openai.com/v1/responses",
      data=json.dumps(payload).encode("utf-8"),
      headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
      method="POST")
    try:
        with urllib.request.urlopen(req,timeout=95) as response:
            reply=json.load(response)
    except urllib.error.HTTPError as ex:
        # Never echo keys / full upstream errors into the browser.
        raise RuntimeError(f"AI provider returned HTTP {ex.code}; check model access, key, and usage limits.")
    output=[]
    for item in reply.get("output",[]):
        for content in item.get("content",[]):
            if content.get("type")=="output_text":output.append(content.get("text",""))
    if not output:raise RuntimeError("AI returned no printable content. Try again or use Demo mode.")
    parsed=json.loads("".join(output))
    if len(parsed.get("pages",[]))!=count:
        raise RuntimeError("AI returned a different page count; try again or use Demo mode.")
    assembled={"title":parsed["title"],"pages":parsed["pages"],"listing":parsed["listing"],
          "idea":idea,"productType":product,"audience":audience,"theme":theme,
          "paper":paper,"cover":cover,"inkSaver":ink_saver}
    return validate_project(assembled)
