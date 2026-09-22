# Printable Studio 4.1
## A private, Railway-ready creation and multi-platform publishing workspace

## Upgrade notes for the September 2026 Railway deployment

This is a **bugfix and content-coverage update** to the same private site. It does
not require a new Railway project or a new domain.

**Why AI Studio is disabled:** It is intentionally disabled when `OPENAI_API_KEY`
is missing or empty. In Railway → Printable-Studio service → Variables, add
`OPENAI_API_KEY` with a key you create in your own OpenAI API account, then
review/deploy the staged change. The key is server-side; never add it to GitHub,
a `.env` checked into GitHub, or this chat. API billing is separate from any
ChatGPT subscription. `STUDIO_PASSWORD` only protects your website; it is not
an AI API key. Use Demo while you are setting this up.

**Why some page titles were missing:** The earlier Demo mode cycled through a
small list of fixed Garden Planner templates. It did not understand the exact
list of named worksheets in an idea. This upgrade includes distinct herb
templates for: This Planner Belongs To, Garden Goals, Herb Wish List,
Herb Profile Sheet, Planting Planner, Container & Pot Planner, Watering Log,
Sunlight Tracker, Fertilizer Tracker, Harvest Tracker, Seed Inventory,
Garden Notes, and Seasonal Reflection. When the prompt explicitly names more
of these sheets than the page-count dropdown allows, Demo now increases the
number of interior pages to include the recognized requests. The designed
cover is separate. This is *recognition of supported templates*, not full
AI content generation; arbitrary custom page instructions require AI Studio
or manual editing.

**PDF download:** Demo mode is enough. Generate a project first, then click
the new prominent `Download PDF` button above the preview or the
`Download printable PDF` button under Download Center. The site generates the
PDF on the server and the browser saves it in Downloads (or prompts for a save
location, depending on browser settings). If the download fails, the on-screen
error no longer disappears quickly, and a client-side JSON project backup is
also available. An on-screen failure on *your* Railway instance still requires
its exact error message or Deploy Logs for diagnosis; local export tests alone
cannot verify your cloud settings or browser download permissions.

**Update GitHub / Railway:** Unzip the full v4.1 archive, open its
`printable_studio_v4_1` folder, upload the folder's *contents* to the root of
your existing GitHub repository, and commit/replace changed source files.
Do not upload the ZIP as-is. Do not add `.env`, passwords, keys, or delete your
Railway volume. Railway should deploy the new commit. Refresh your site
and check that its header says 4.1. Existing projects stored on a properly
configured persistent volume will remain in place; if you did not configure
a volume, do not rely on Railway's ephemeral filesystem to preserve data.

**Sample:** `examples/beginner-herb-garden-planner.pdf` contains one cover and
13 distinct interior herb-planner sheets, including the wish list and profile
sheet. It is a test/draft, not a proofread, finished commercial product.


**What it does:** From one original idea, make editable printable pages in curated
trend-aware styles and export three different platform packages. The product
editor, optional server-side AI engine, saved projects, Etsy draft integration,
and local PDF generator from v3 are preserved.

This is a **single-user publishing prototype**, not a publicly offered SaaS.
Exports are drafts requiring review. It does not create or publish Amazon KDP
listings or Pinterest Pins, and it does not guarantee a marketplace will accept
a file or that a product will sell.

### What is in each export?

**Etsy digital bundle** (`etsy-pack.zip`):
- Printable PDF in US Letter or A4, with your chosen cover and interior pages.
- Original, programmatically illustrated 2000×1500 JPEG listing image.
- Editable listing description, title, tags, AI-use disclosure and review notes.
- A JSON version of your editable project.

**Amazon KDP paperback bundle** (`kdp-pack.zip`):
- Vector interior PDF with 6×9 or 8.5×11 inch trim and mirrored safe gutter.
- Separate, single-page back–spine–front wraparound cover PDF with the correct
  0.125-inch outer bleed and spine width for your selected page count/paper stock.
- Page count, trim and exact cover dimensions in a preflight checklist.
- Editable metadata draft and editable project JSON.

KDP interiors use **no bleed**. Trim options are 6×9 or 8.5×11 inches; page
counts are 24–200, even only; ink/paper stock choices: black-and-white white
paper, black-and-white cream paper and **premium color** white paper. Spine text
is intentionally omitted. The app repeats the current worksheets to reach a
chosen book page count if necessary, with a prominent warning in the UI and
preflight file. Repeating sheets can suit some low-content planners, but it
does **not** turn 5 distinct pages into a 48-page instructional workbook.
Review or create additional substantive pages before selling a guided workbook.
Use KDP's official Print Previewer and cover calculator to confirm final fit,
barcode placement, and eligibility:
https://kdp.amazon.com/en_US/help/topic/G201857950
https://kdp.amazon.com/en_US/help/topic/G201953020

**Pinterest promotional bundle** (`pinterest-pack.zip`):
- Original 1000×1500 pixel, 2:3 JPEG Pin graphic.
- Draft Pin title, description, alt text, and optional destination URL.
- Project JSON and review checklist.
Pinterest is a product discovery channel here; this feature does not sell PDFs
on Pinterest or post Pins automatically.

**All-platform ZIP:** Includes all three bundles together, in labeled folders.

### Run locally

Install Python 3.10+; from this folder:

```sh
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8765 . Without `.env` settings, the app starts in Demo mode
and can produce/use/edit/export worksheets without any API payment.

To use real AI generation, copy `.env.example` to `.env`, set `OPENAI_API_KEY`
(and an appropriate `OPENAI_MODEL`), then restart. Your own provider charges
apply. AI mode requires a live internet connection; its model call could not be
end-to-end verified with your account credentials in this packaged demo.

### Deploy privately on Railway

1. Put **the contents of this folder** in your own **private** GitHub repository.
   Do **not** add `.env` or real API credentials to the repository.
2. In Railway, create a project → deploy from your GitHub repo. The included
   `Dockerfile` and `railway.json` configure the application start and healthcheck.
3. Add a Railway environment variable: `STUDIO_PASSWORD` with a strong unique
   password. The app deliberately refuses to serve a Railway deployment without
   it. The browser login is username `studio`, password is `STUDIO_PASSWORD`.
4. Optional: add `OPENAI_API_KEY` and `OPENAI_MODEL` environment variables for
   AI generation. Never paste credentials into the printable idea field.
5. **Important:** attach a persistent Railway Volume mounted at **`/data`**,
   and set `STUDIO_DATA_DIR=/data`. Projects are stored in `/data/projects`.
   Without a volume, saved projects can disappear on deployment/restart.
6. Under Networking, generate an HTTPS Railway domain, then visit your
   password-protected studio. Railway supplies the `PORT`; do not hard-code it.
7. Optional Etsy draft upload: configure `ETSY_KEYSTRING`, `ETSY_SHARED_SECRET`,
   `ETSY_SHOP_ID` and a matching **HTTPS** `ETSY_REDIRECT_URI` such as
   `https://YOUR-DOMAIN.railway.app/api/etsy/callback`. This prototype holds
   OAuth tokens in memory; tokens are lost on restart. It does not support
   long-term automatic publishing or per-user accounts.

The volume is mounted as root by Railway, so the included Dockerfile runs
as the default image user for this single-user prototype. It should undergo
a security review before operating as a public, multi-user service.

Official Railway documentation:
https://docs.railway.com/guides/flask (Flask guide; the app itself uses Python's HTTP server)
https://docs.railway.com/volumes

### How to use the application

Enter your original idea. Choose product, audience, trend-aware style, page
count, paper size and Demo or AI mode. Generate pages. Use the editor to
rewrite/duplicate/reorder worksheets, change blocks, add useful prompts, and
proofread. Save your project. For KDP, set trim, paper stock and page count.
For Pinterest, add the real product URL once your Etsy or Amazon listing
exists. Then download the corresponding ZIP.

The brand palette system is a **curated set of current-style directions**,
not a live Etsy trend scanner. Trend choices are not proof of customer demand.
Research your audience and marketplace keywords independently.

### Licensing, ethics and human review

You are responsible for ensuring original creative contribution, copyright /
trademark permissions, factual accuracy, accessibility, and platform policies.
Etsy's Creativity Standards require relevant AI-use disclosure for seller-
prompted AI creations:
https://www.etsy.com/legal/creativity/
KDP requires disclosure of AI-generated content, and distinguishes AI-generated
from AI-assisted work:
https://kdp.amazon.com/en_US/help/topic/G200672390
For anxiety/depression-related materials, position general worksheets as
non-clinical reflection, not as diagnosis, therapy, treatment, or crisis care.

### Verification and limitations

Run `python tests.py` to smoke-test local generation, page count/format,
print geometry, bundles, project saving and password gate. The generated
PDFs are actual vector PDFs. Full Etsy OAuth, KDP account uploads, Pinterest
publication, Railway cloud deployment and paid AI calls cannot be tested here
without your accounts/keys and must be checked after connection.

There is no payment processing, multi-user authentication, web-borne image
generation, automatic live trend research, full KDP category validation,
ISBN generator, barcode generator, or marketplace sales guarantee. Exported
cover artwork is vector/graphic, not a licensed photograph. Seller should
order a KDP physical proof and check any image/copy against the real product.

## Folder guide

- `app.py`: server, password access, save/load, export endpoints and optional Etsy draft.
- `engine.py`: demo templates, project validation and optional server-side AI.
- `rendering.py`: Etsy PDF and listing graphic.
- `marketplaces.py`: platform-specific packs, KDP geometry, Pinterest image.
- `static/`: editable browser UI.
- `Dockerfile`, `railway.json`: Railway deployment.
- `.env.example`: local/Railway settings (no real credentials).
- `tests.py`: 11 smoke tests including geometry and access checks.
