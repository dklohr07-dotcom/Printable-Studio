const $ = id => document.getElementById(id);
const app = {project:null, index:0, config:null, busy:false};
const match = {
 "Journal":"analog","Garden Planner":"botanical","Menu":"persimmon",
 "Organizational Chart":"editorial","Anxiety & Mood Support":"blue",
 "Learning Resource":"playful","Custom Printable":"editorial"
};
const example = "A 12-page beginner herb garden planner with a planting calendar, watering tracker, harvest journal and seasonal reflection pages. Calm, premium stationery style.";
function esc(value) {
 return String(value ?? "").replace(/[&<>"']/g, s=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[s]));
}
function toast(msg, error=false) {
 const el=$("toast"); el.textContent=msg;el.className=error?"error":"";
 el.style.display="block";
 clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.style.display="none",5600);
}
async function api(path,body) {
 const response=await fetch(path,{method:body===undefined?"GET":"POST",
  headers:body===undefined?{}:{"Content-Type":"application/json"},
  body:body===undefined?undefined:JSON.stringify(body)});
 const result=await response.json();
 if(!response.ok)throw new Error(result.error || "The request failed.");
 return result;
}
function activeTheme() {
 const p=app.project;
 if(p)return p.theme;
 const selected=$("theme").value;
 return selected==="auto"?(match[$("product").value]||"editorial"):selected;
}
function colors(){
 const key=activeTheme();
 return app.config?.themes?.[key] || {
  name:"Editorial Calm",ink:"#272722",accent:"#465646",light:"#edf0e9",paper:"#fffefa"
 };
}
function paletteMarkup(t){return [t.ink,t.accent,t.light,t.paper].map(v=>`<span title="${esc(v)}" style="background:${esc(v)}"></span>`).join("");}
function updatePalette(){
 const t=colors();
 $("palette").innerHTML=paletteMarkup(t);$("artColors").innerHTML=paletteMarkup(t);
 $("themeName").textContent=t.name;
 const reasons={
  botanical:"A garden-inspired editorial palette, organic forms and breathing room. Warm, tactile without wasting printer ink.",
  editorial:"Quiet serif-inspired hierarchy, crisp framing and deliberate whitespace for organized information.",
  analog:"A familiar notebook feel with warm earth accents and clear spaces for handwritten thoughts.",
  blue:"Cool Blue creates a calm visual tone while keeping reflective worksheets readable and uncluttered.",
  persimmon:"An expressive warm accent helps menus and celebration planners stand out without crowding interior pages.",
  plum:"A rich plum palette adds a premium editorial feel to covers while maintaining a light writing surface.",
  playful:"Soft rounded framing and friendly structure fit educational pages without overwhelming learners."
 };
 $("themeWhy").textContent=reasons[activeTheme()]||"A considered visual system.";
}
function setBusy(value){
 app.busy=value;$("generateBtn").disabled=value;
 $("generateBtn").innerHTML=value?"Generating your pages…":"✳ Generate collection <span>→</span>";
}
async function generate(){
 if(app.busy)return;
 const idea=$("idea").value.trim();
 if(!idea){toast("Add your product idea to begin.",true);$("idea").focus();return;}
 const mode=document.querySelector('input[name="mode"]:checked').value;
 const payload={idea,productType:$("product").value,audience:$("audience").value.trim(),
  pageCount:Number($("pageCount").value),theme:$("theme").value,paper:$("paper").value,
  cover:$("cover").checked,inkSaver:$("inkSaver").checked,mode};
 setBusy(true);
 try {
  const result=await api("/api/generate",payload);
  app.project=result.project;app.index=0;
  syncFromProject(); renderAll();
  toast(result.mode==="ai"?"AI collection generated. Review and edit before selling.":"Demo collection generated. Edit prompts or switch to AI mode.");
 } catch(error){toast(error.message,true);}
 finally{setBusy(false);}
}
function syncFromProject(){
 const p=app.project;if(!p)return;
 $("idea").value=p.idea;$("product").value=p.productType;$("audience").value=p.audience;
 $("theme").value=p.theme;$("paper").value=p.paper;
 $("cover").checked=p.cover;$("inkSaver").checked=p.inkSaver;
 $("listingTitle").value=p.listing.title;$("description").value=p.listing.description;
 $("tags").value=p.listing.tags.join(", ");$("disclosure").value=p.listing.aiDisclosure;
}
function applyControls(){
 const p=app.project;if(!p){updatePalette();return;}
 p.theme=$("theme").value==="auto"?(match[$("product").value]||"editorial"):$("theme").value;
 p.paper=$("paper").value;p.cover=$("cover").checked;p.inkSaver=$("inkSaver").checked;
 p.audience=$("audience").value;p.productType=$("product").value;
 p.idea=$("idea").value;
 app.index=Math.min(app.index,totalPages()-1);
 renderAll();
}
function totalPages(){
 const p=app.project;return p?p.pages.length+(p.cover?1:0):0;
}
function isCover(){return !!app.project?.cover && app.index===0;}
function pageIndex(){return app.index-(app.project.cover?1:0);}
function selectedPage(){return isCover()?null:app.project.pages[pageIndex()];}
function selectPage(index){if(!app.project)return;app.index=Math.max(0,Math.min(totalPages()-1,index));renderAll();}
function contentForBlock(b){
 const n=Math.min(6,Math.max(1,Number(b.lines)||4));
 if(b.type==="two_columns")return `<div class="columns">${(b.items||[]).slice(0,2).map(x=>`<div class="col">${esc(x)}</div>`).join("")}</div>`;
 if(b.type==="table"){
  const heads=(b.items||[]).slice(0,4);if(!heads.length)heads.push("Date","Item","Notes");
  return `<table class="table-preview"><tr>${heads.map(h=>`<th>${esc(h)}</th>`).join("")}</tr>${Array.from({length:n},()=>`<tr>${heads.map(()=>"<td></td>").join("")}</tr>`).join("")}</table>`;
 }
 if(b.type==="checklist"){
  const items=b.items||[];return Array.from({length:Math.max(n,items.length)},(_,i)=>`<div class="checkrow"><span></span>${esc(items[i]||"")}</div>`).join("");
 }
 if(b.type==="callout")return `<div class="callout">${esc((b.items||[]).join(" · ")||"Helpful reminders and notes")}</div>`;
 return Array.from({length:n},()=>'<div class="writeline"></div>').join("");
}
function renderPreview(){
 const p=app.project;
 if(!p)return;
 const t=colors(),sheetClass=p.paper==="a4"?" a4":"";
 const ink=p.inkSaver?{...t,accent:"#555555",light:"#f3f3f3",paper:"#ffffff"}:t;
 const style=`--sheet-paper:${ink.paper};--sheet-ink:${ink.ink};--sheet-accent:${ink.accent};--sheet-light:${ink.light}`;
 let html="";
 if(isCover()){
  html=`<div class="sheet cover-sheet${sheetClass}" style="${style}">
   <div class="cover-frame"><div class="dash"></div><div class="kicker">${esc(p.productType)}</div>
    <h3>${esc(p.title)}</h3><p>A printable collection for ${esc(p.audience||"thoughtful everyday use")}</p>
    <div class="kicker" style="margin-top:50px">PRINTABLE / ${esc(t.name)}</div></div>
    <footer><span>Original seller-directed concept</span><span>Cover</span></footer></div>`;
 } else {
  const page=selectedPage();
  html=`<div class="sheet${sheetClass}" style="${style}">
    <div class="kicker">${esc(p.productType)}</div><h3>${esc(page.title)}</h3>
    <div class="subtitle">${esc(page.subtitle)}</div><hr>
    ${page.blocks.map(b=>`<section class="block"><b>${esc(b.title)}</b>${contentForBlock(b)}</section>`).join("")}
    <footer><span>${esc(p.title)}</span><span>${pageIndex()+1} / ${p.pages.length}</span></footer></div>`;
 }
 $("preview").innerHTML=html;
 $("pageNumber").textContent=`${app.index+1} / ${totalPages()}`;
 $("pageStatus").textContent=isCover()?"Coordinated cover page":`Interior page ${pageIndex()+1} · ${t.name}`;
 $("pager").innerHTML=Array.from({length:totalPages()},(_,i)=>`<button class="${i===app.index?"active":""}" data-page="${i}" title="${i===0&&p.cover?"Cover":"Page "+(i+(p.cover?0:1))}">${i+1}</button>`).join("");
 $("projectTitle").textContent=p.title;
 $("projectMeta").textContent=`${p.productType} · ${p.pages.length} interior pages${p.cover?" + cover":""} · ${t.name}`;
}
function renderEditor(){
 const p=app.project;
 if(!p){$("editArea").innerHTML=`<div class="sideempty">Generate a product to edit its page titles, prompts, writing space, layout blocks and listing copy.</div>`;return;}
 if(isCover()){
  $("editArea").innerHTML=`<label>Collection title</label><input data-edit="projectTitle" value="${esc(p.title)}">
  <label>Audience</label><input data-edit="audience" value="${esc(p.audience)}">
  <p class="hint">Cover text updates as you type. Change the art direction on the left.</p>`;
  return;
 }
 const page=selectedPage();
 const blocks=page.blocks.map((b,i)=>`<div class="blockeditor">
   <h4>Block ${i+1}</h4>
   <label>Prompt or section name</label><input data-edit="blockTitle" data-block="${i}" value="${esc(b.title)}">
   <label>Layout</label><select data-edit="blockType" data-block="${i}">
     ${["lines","two_columns","table","checklist","callout"].map(kind=>`<option value="${kind}" ${b.type===kind?"selected":""}>${kind.replace("_"," ")}</option>`).join("")}
    </select>
    <label>Rows / writing lines</label><select data-edit="blockLines" data-block="${i}">
      ${[1,2,3,4,5,6].map(n=>`<option value="${n}" ${b.lines===n?"selected":""}>${n}</option>`).join("")}
    </select>
    <label>Labels <small>(one per line, used by tables/columns/checklists)</small></label>
    <textarea rows="3" data-edit="blockItems" data-block="${i}">${esc((b.items||[]).join("\n"))}</textarea>
    <div class="toolrow">
      <button data-action="up" data-block="${i}" title="Move block up">↑</button>
      <button data-action="down" data-block="${i}" title="Move block down">↓</button>
      <button data-action="copy" data-block="${i}">Copy</button>
      <button class="danger" data-action="remove" data-block="${i}">Remove</button>
    </div>
   </div>`).join("");
 $("editArea").innerHTML=`<label>Page title</label><input data-edit="pageTitle" value="${esc(page.title)}">
  <label>Small description</label><textarea data-edit="pageSubtitle" rows="2">${esc(page.subtitle)}</textarea>
  <div class="toolrow"><button data-action="pageUp">← Move</button><button data-action="pageDown">Move →</button>
  <button data-action="duplicatePage">Duplicate</button><button class="danger" data-action="removePage">Delete</button></div>
  <div class="navtitle">LAYOUT BLOCKS</div>${blocks}
  <button class="outline full" data-action="addBlock">+ Add writing block</button>
  <button class="subtle full" style="margin-top:9px" data-action="addPage">+ Add new page</button>`;
}
function renderAll(){if(app.project){updatePalette();renderPreview();renderEditor();}}
function edited(event){
 const p=app.project;if(!p)return;
 const role=event.target.dataset.edit;
 if(!role)return;
 const page=selectedPage(),i=Number(event.target.dataset.block),value=event.target.value;
 if(role==="projectTitle")p.title=value.slice(0,110);
 if(role==="audience"){p.audience=value.slice(0,100);$("audience").value=p.audience;}
 if(role==="pageTitle")page.title=value.slice(0,90);
 if(role==="pageSubtitle")page.subtitle=value.slice(0,200);
 if(role==="blockTitle")page.blocks[i].title=value.slice(0,90);
 if(role==="blockType")page.blocks[i].type=value;
 if(role==="blockLines")page.blocks[i].lines=Number(value);
 if(role==="blockItems")page.blocks[i].items=value.split("\n").map(x=>x.trim()).filter(Boolean).slice(0,12);
 renderPreview();
}
function editorAction(event){
 const b=event.target.closest("button[data-action]");if(!b||!app.project)return;
 const action=b.dataset.action,p=app.project;
 if(isCover())return;
 const page=selectedPage(),index=pageIndex(),i=Number(b.dataset.block);
 if(action==="up"&&i>0)[page.blocks[i-1],page.blocks[i]]=[page.blocks[i],page.blocks[i-1]];
 if(action==="down"&&i<page.blocks.length-1)[page.blocks[i+1],page.blocks[i]]=[page.blocks[i],page.blocks[i+1]];
 if(action==="remove"&&page.blocks.length>1)page.blocks.splice(i,1);
 if(action==="copy"){
  if(page.blocks.length>=3){toast("Up to three blocks per page keeps the PDF readable.",true);return;}
  page.blocks.splice(i+1,0,structuredClone(page.blocks[i]));
 }
 if(action==="addBlock"){
  if(page.blocks.length>=3){toast("Up to three blocks per page keeps the PDF readable.",true);return;}
  page.blocks.push({type:"lines",title:"New reflection or planning prompt",lines:4,items:[]});
 }
 if(action==="pageUp"&&index>0){[p.pages[index-1],p.pages[index]]=[p.pages[index],p.pages[index-1]];app.index--;}
 if(action==="pageDown"&&index<p.pages.length-1){[p.pages[index+1],p.pages[index]]=[p.pages[index],p.pages[index+1]];app.index++;}
 if(action==="duplicatePage"){
  if(p.pages.length>=24){toast("24-page editor limit reached.",true);return;}
  p.pages.splice(index+1,0,structuredClone(page));app.index++;
 }
 if(action==="removePage"){
  if(p.pages.length<=1){toast("Keep at least one printable page.",true);return;}
  p.pages.splice(index,1);app.index=Math.min(app.index,totalPages()-1);
 }
 if(action==="addPage"){
  if(p.pages.length>=24){toast("24-page editor limit reached.",true);return;}
  p.pages.push({title:"New Worksheet",subtitle:p.idea.slice(0,140),
   blocks:[{type:"lines",title:"Write your prompt",lines:5,items:[]}]});
  app.index=totalPages()-1;
 }
 renderAll();
}
async function save(){
 if(!app.project){toast("Generate a collection before saving.",true);return;}
 try{
  const result=await api("/api/projects",{project:app.project});
  app.project=result.project;toast("Project saved in your local library.");loadProjects();
 }catch(error){toast(error.message,true);}
}
async function loadProjects(){
 try{
  const data=await api("/api/projects");
  $("savedProjects").innerHTML=data.projects.length?data.projects.map(p=>
   `<button data-open="${esc(p.id)}">${esc(p.title)}<small>${esc(p.productType)} · ${new Date(p.updated*1000).toLocaleDateString()}</small></button>`).join("")
   :'<div class="hint">Nothing saved yet. Save a generated product to start a library.</div>';
 }catch(e){$("savedProjects").textContent="Could not load library.";}
}
async function openProject(id){
 try{app.project=await api("/api/projects/"+id);app.index=0;syncFromProject();renderAll();toast("Saved collection opened.");}
 catch(e){toast(e.message,true);}
}
async function exportMarketplace(kind){
  if(!app.project){toast("Generate a collection first.",true);return;}
  const count=Number($("kdpPages").value);
  const isKdp=["kdp","all"].includes(kind);
  if(isKdp && count>app.project.pages.length){
    const accepted=window.confirm(
      `Your product has ${app.project.pages.length} unique worksheets. `+
      `The ${count}-page paperback will repeat them. Continue creating a DRAFT pack for seller review?`
    );
    if(!accepted)return;
  }
  const payload={
    project:app.project,
    kdp:{trim:$("kdpTrim").value,pageCount:count,paperStock:$("kdpPaper").value},
    pinterest:{destinationUrl:$("pinUrl").value.trim()}
  };
  const files={etsy:"etsy-pack",kdp:"kdp-pack",pinterest:"pinterest-pack",all:"all-pack"};
  try {
    toast("Rendering the "+kind+" publishing package...");
    const response=await fetch("/api/export/"+files[kind],{
      method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
    });
    if(!response.ok){const error=await response.json();throw new Error(error.error||"Export failed.");}
    const blob=await response.blob(),url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    const stem=app.project.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,56)||"printable";
    a.href=url;a.download=stem+"-"+kind+"-pack.zip";a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1800);
    toast("Export complete. Review the PDFs, copy, and marketplace checklist before selling.");
  }catch(error){toast(error.message,true);}
}
async function exportAsset(kind){
 if(!app.project){toast("Generate a collection first.",true);return;}
 const key=kind==="pack"?"pack":kind==="pdf"?"pdf":"mockup";
 try{
  toast("Preparing your "+(kind==="pack"?"Etsy pack":kind.toUpperCase())+"…");
  const response=await fetch("/api/export/"+key,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({project:app.project})});
  if(!response.ok){const error=await response.json();throw new Error(error.error||"Export failed.");}
  const blob=await response.blob(),url=URL.createObjectURL(blob);
  const a=document.createElement("a"),stem=app.project.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,56)||"printable";
  a.href=url;a.download=stem+(kind==="pdf"?".pdf":kind==="pack"?"-etsy-pack.zip":"-listing.jpg");a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
  toast("Download prepared. Review the PDF and listing before sale.");
 }catch(error){toast(error.message,true);}
}
function syncListing(){
 const p=app.project;if(!p)return;
 p.listing.title=$("listingTitle").value.slice(0,140);
 p.listing.description=$("description").value.slice(0,3500);
 p.listing.tags=$("tags").value.split(",").map(x=>x.trim().slice(0,20)).filter(Boolean).slice(0,13);
 p.listing.aiDisclosure=$("disclosure").value.slice(0,350);
}
async function publishDraft(){
 const p=app.project;if(!p){toast("Generate a product first.",true);return;}
 if(!$("sellerApproved").checked){toast("Please review the product and check approval first.",true);return;}
 if(!window.confirm("Create an Etsy DRAFT only for this product? This will not activate it."))return;
 $("draftBtn").disabled=true;
 try{
  const response=await api("/api/etsy/draft",{project:p,price:$("price").value,
   taxonomy_id:$("taxonomy").value,sellerApproved:true});
  const message=response.upload_errors.length?
   "Draft created, but upload warnings: "+response.upload_errors.join(" | "):
   "Etsy draft created with PDF and listing image. Review it in Etsy.";
  toast(message,!!response.upload_errors.length);
  $("etsyState").textContent="Draft ID: "+response.listing_id+" — "+message;
 }catch(error){toast(error.message,true);}
 finally{$("draftBtn").disabled=false;}
}
async function init(){
 for(const id of ["theme","product"])$(id).addEventListener("change",()=>app.project?applyControls():updatePalette());
 for(const id of ["paper","cover","inkSaver"])$(id).addEventListener("change",applyControls);
 $("audience").addEventListener("change",applyControls);
 $("idea").addEventListener("change",applyControls);
 $("sampleBtn").addEventListener("click",()=>{$("idea").value=example;$("product").value="Garden Planner";$("audience").value="first-time herb gardeners";updatePalette();toast("Example added. Choose a mode, then generate.");});
 $("generateBtn").addEventListener("click",generate);
 $("prevBtn").addEventListener("click",()=>selectPage(app.index-1));
 $("nextBtn").addEventListener("click",()=>selectPage(app.index+1));
 $("pager").addEventListener("click",e=>{const b=e.target.closest("button[data-page]");if(b)selectPage(Number(b.dataset.page));});
 $("editArea").addEventListener("input",edited);
 $("editArea").addEventListener("change",e=>{if(e.target.dataset.edit==="blockType")renderEditor();});
 $("editArea").addEventListener("click",editorAction);
 $("saveBtn").addEventListener("click",save);$("refreshProjects").addEventListener("click",loadProjects);
 $("savedProjects").addEventListener("click",e=>{const b=e.target.closest("button[data-open]");if(b)openProject(b.dataset.open);});
 $("packBtn").addEventListener("click",()=>exportMarketplace("all"));
 $("bundleBtn").addEventListener("click",()=>exportAsset("pack"));
 $("pdfBtn").addEventListener("click",()=>exportAsset("pdf"));
 $("jpgBtn").addEventListener("click",()=>exportAsset("mockup"));
  $("etsyPackBtn").addEventListener("click",()=>exportMarketplace("etsy"));
  $("kdpPackBtn").addEventListener("click",()=>exportMarketplace("kdp"));
  $("pinPackBtn").addEventListener("click",()=>exportMarketplace("pinterest"));
  $("allPackBtn").addEventListener("click",()=>exportMarketplace("all"));
 for(const id of ["listingTitle","description","tags","disclosure"])$(id).addEventListener("input",syncListing);
 $("etsyConnect").addEventListener("click",()=>window.location.assign("/api/etsy/connect"));
 $("draftBtn").addEventListener("click",publishDraft);
 try{
  app.config=await api("/api/config");
  const aiRadio=document.querySelector('input[name="mode"][value="ai"]');
  aiRadio.disabled=!app.config.aiConfigured;
  $("modeHint").textContent=app.config.aiConfigured?
   `AI Studio is enabled with ${app.config.aiModel}. Your key stays on the server.`:
   "AI mode needs OPENAI_API_KEY in your server .env file; Demo works without it.";
  $("etsyConnect").disabled=!app.config.etsyConfigured;
  $("draftBtn").disabled=!app.config.etsyConnected;
  $("etsyState").textContent=app.config.etsyConnected?
   "Etsy connected for this server session. Creating a draft requires taxonomy ID and seller review.":
   app.config.etsyConfigured?"Connect your Etsy shop to authorize draft listing creation.":
   "Set Etsy environment variables first. Downloadable Etsy packs work without connecting.";
  if(new URLSearchParams(window.location.search).get("etsy")==="connected")
   toast("Your Etsy authorization returned successfully. Review the listing before publishing.");
 }catch(e){toast("Could not connect to the local server.",true);}
 updatePalette();loadProjects();
}
document.addEventListener("DOMContentLoaded",init);
