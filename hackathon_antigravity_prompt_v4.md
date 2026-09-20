# Antigravity Master Prompt v4 — Averis x Monash Hackathon 2026
## Repo-Aware + Problem Statement + Rules + Rubric Aligned
### HARD DEADLINE: ~32 HOURS

You are the primary coding agent working inside the existing:

`Shipping-Document-Verification`

repository.

Repository:
`https://github.com/siting3693/Shipping-Document-Verification`

Your job is to **finish and strengthen the existing project**, not rebuild it from zero.

The target is a **working, demonstrable AI-powered shipping document verification prototype** that can score well both against the provided self-evaluation endpoint and against the human judging rubric.

Core principle:

> **AI understands messy language/documents. Deterministic logic verifies the result. Humans resolve genuine ambiguity.**

---

# 1. NON-NEGOTIABLE COMPETITION REQUIREMENTS

The official rules say:

- the solution MUST meaningfully incorporate **AI**
- the solution MUST utilize **cloud infrastructure** as part of development, deployment, or core functionality
- the technical stack is unrestricted
- the preliminary submission requires at least a low-code solution, with a semi-working prototype strongly encouraged
- the final round expects a working prototype
- the submitted work must be original and completed during the official hackathon period

Therefore:

## AI is NOT optional.

Use AI for meaningful tasks such as:

- semantic email intent classification
- document-role understanding
- messy field extraction
- semantic field-label mapping
- ambiguous/OCR interpretation

Do not use AI only as a cosmetic chatbot.

## Cloud is NOT optional.

The architecture and README/demo must clearly show meaningful cloud usage.

Examples of acceptable roles include:

- cloud-hosted AI/LLM API
- cloud-hosted backend
- cloud-hosted storage/service used by the workflow
- deployed web application/API

Use whatever provider is already available to the team.

Keep credentials in environment variables.

Do not hard-code secrets.

If a cloud API key is unavailable during local development, provide a deterministic fallback so the prototype still runs, but do not remove the intended cloud/AI integration from the final architecture.

---

# 2. JUDGING RUBRIC — BUILD FOR THIS, NOT ONLY THE SCORER

The preliminary judging rubric is 100 points:

### Technical — 70
- System Design & Architecture — 15
- Working Core Prototype — 25
- Technology Integration — 15
- Technical Feasibility & Validation — 15

### Product & Impact — 30
- Problem Statement Understanding — 10
- Innovation & Solution Approach — 10
- Practical Value & Potential — 10

The **largest single criterion is Working Core Prototype (25 points)**.

Judges are instructed to score based on what is demonstrated, submitted, or clearly explained.

Therefore:

> A technically accurate hidden-score submission is not enough. The prototype must be visibly working and the architecture/technology choices must be easy for judges to understand.

The official problem statement also says the self-evaluation scoreboard is only a development aid and does not assess every part of a good solution.

So optimize for BOTH:

```text
1. measurable correctness
2. visible working product
```

Do not sacrifice the latter merely to chase tiny scorer improvements.

---

# 3. FINAL-ROUND DIRECTION

The official rules show the final-round distribution as:

- End-to-End Functionality — 25
- Architecture & Scalability — 15
- Technology Integration — 15
- Engineering Quality & Robustness — 15
- Solution Effectiveness & User Value — 10
- User Experience & Differentiation — 10
- Impact & Future Potential — 10

This means the architecture you build now should already have a credible path toward:

- reliable end-to-end processing
- understandable architecture
- meaningful AI/cloud integration
- robust failure handling
- useful operator workflow
- polished user experience
- future extensibility

Do NOT over-engineer for hypothetical production scale. Build a sensible architecture that can be explained and extended.

---

# 4. ACTUAL PROBLEM

The inbox contains:

- document comparison requests
- new Shipping Instruction requests
- invoice questions
- general operational messages
- spam

Only document comparison requests continue to document verification.

For a comparison request:

```text
Email
→ identify task
→ find SI + BL
→ extract 7 fields
→ normalize
→ compare
→ produce discrepancy report
→ human review if uncertain
```

The seven required comparison fields are:

```text
shipper
consignee
notify_party
port_of_loading
port_of_discharge
container_count
gross_weight_kg
```

The SI is the reference for the check.

The system should surface the exact mismatching fields and show SI/BL values side by side.

If all seven match:

```text
No mismatch detected.
```

The advanced challenge emphasizes:

- PDF and Word
- tables and different layouts
- scanned documents
- OCR / vision-capable models
- varied field labels
- formatting differences
- misleading subjects
- missing attachments
- distinguishing real defects from reading/formatting issues
- human escalation with evidence
- visible handling of processing failures
- retries

---

# 5. CURRENT REPOSITORY — PRESERVE WHAT EXISTS

Inspect before modifying:

```text
classify_emails.py
loader.py
sample_submission.json
classified_submission.json
classification_debug.json
docker-compose.yml
dockerREADME.md
main.py
server/
inbox/
attachments/
data_v2/
```

The existing `classify_emails.py` already provides a meaningful Stage-1 rule baseline.

It already uses:

- subject
- body
- sender
- attachment names
- attachment extensions
- comparison phrases
- SI-request signals
- invoice signals
- spam signals

It also validates submission shape.

DO NOT rewrite it wholesale.

Instead:

```text
existing classifier
      ↓
measure
      ↓
fix only observed weak cases
```

The current large gap is the verification stage after `BL_COMPARISON`.

---

# 6. OFFICIAL DATA + DOCKER CONTRACT

The supplied static bundle contains:

```text
inbox/
attachments/
sample_submission.json
loader.py
```

The local Docker option serves the same dataset over:

```text
http://localhost:8080
```

No database or extra setup is required.

The loader supports both styles:

```python
from loader import Inbox

Inbox("data")
```

or:

```python
Inbox("http://localhost:8080")
```

The local server exposes a self-evaluation endpoint.

Use:

```text
POST /submit
```

to submit your generated output.

The server compares it against private reference data and does NOT return the answer key.

## Critical rule

Never make application logic depend on hidden ground truth.

Do not:

- read ground_truth.json
- modify the challenge scorer
- expose answer keys
- reverse-engineer the private reference set
- change the evaluator to improve your score

The self-evaluation endpoint is a feedback loop, not an oracle.

---

# 7. TARGET ARCHITECTURE

Build this:

```text
                    INBOX
                      |
                      v
             +----------------+
             | Stage 1        |
             | Email Classifier|
             +-------+--------+
                     |
             BL_COMPARISON?
                /          \
              no            yes
              |              |
              v              v
        Final category   Attachment Resolver
                              |
                              v
                       Document Parser
                              |
                    +---------+---------+
                    |                   |
                    v                   v
               SI Extraction       BL Extraction
                    |                   |
                    +---------+---------+
                              |
                              v
                        Normalization
                              |
                              v
                          Validation
                              |
                              v
                    Deterministic Compare
                     /         |          \
                   OK      MISMATCH    NEEDS_REVIEW
                    \         |          /
                     +--------+---------+
                              |
                              v
                     Submission Adapter
                              |
                              v
                      Self-evaluation
```

Optional but strongly useful:

```text
NEEDS_REVIEW
      |
      v
Human Review UI
      |
      v
Corrected result
```

---

# 8. AI / NON-AI RESPONSIBILITY SPLIT

## AI SHOULD HANDLE

- semantic email intent
- semantic document-type detection
- messy layout interpretation
- ambiguous field-label mapping
- unstructured field extraction
- OCR/vision interpretation
- difficult cases

## DETERMINISTIC CODE SHOULD HANDLE

- JSON loading
- attachment loading
- XLSX parsing
- PDF/DOCX parsing where deterministic libraries work
- numeric parsing
- normalization
- field validation
- exact comparison
- allowed status/review values
- submission formatting
- retries
- error handling

This separation is deliberate.

Do not ask an LLM:

> "Are these documents the same?"

and directly trust its response.

---

# 9. STAGE 1 — EMAIL CLASSIFICATION

Required categories:

```text
BL_COMPARISON
SI_REQUEST
INVOICE_QUERY
GENERAL
SPAM
```

Use the existing rule-based classifier first.

Then add an AI fallback ONLY for ambiguous cases.

### Strong BL comparison signals

- compare SI and BL
- check draft BL against SI
- verify BL matches SI
- document verification
- check for discrepancies
- compare attached shipping documents

### Important distinction

Do not classify every email containing `SI` or `BL` as `BL_COMPARISON`.

Example:

> Please prepare a new SI.

must remain:

```text
SI_REQUEST
```

---

# 10. ATTACHMENT RESOLUTION

For `BL_COMPARISON`:

```text
identify SI
identify BL
```

Use:

```text
filename
+
file type
+
document contents
+
semantic clues
```

SI clues:

```text
Shipping Instruction
SHIPPING INSTRUCTION
SI
requested shipment details
```

BL clues:

```text
Bill of Lading
BILL OF LADING
B/L
Draft BL
B/L No.
```

Do not trust filename alone.

If the documents cannot be reliably identified:

```text
NEEDS_REVIEW
review_reason = wrong_doc_type or missing_attachment
```

---

# 11. DOCUMENT FORMAT PRIORITY

The problem statement says the basic stage starts with JSON email + plain-text attachments and the advanced stage introduces PDF/Word/scanned/messy documents.

The actual repository fixtures also include spreadsheet attachments.

Therefore implement in this order:

## P0
TXT

## P0/P1
XLSX

## P1
Text PDF

## P2
DOCX

## P3
Scanned PDF/image + OCR/vision

Do NOT spend most of the deadline on OCR before TXT/XLSX/PDF comparison works.

---

# 12. XLSX HANDLING

Use a real spreadsheet parser such as `openpyxl`.

For each workbook:

- inspect all relevant sheets
- extract non-empty cells
- preserve row/column structure when useful
- detect labels and values
- flatten meaningful table content into a parser-friendly representation
- preserve source evidence

Do NOT pass raw XLSX binary data into an LLM.

Convert it to structured text/table content first.

---

# 13. SEVEN-FIELD EXTRACTION

Canonical schema:

```json
{
  "shipper": null,
  "consignee": null,
  "notify_party": null,
  "port_of_loading": null,
  "port_of_discharge": null,
  "container_count": null,
  "gross_weight_kg": null
}
```

For every extracted value, retain internal evidence:

```json
{
  "value": 131058,
  "raw_text": "Gross Wt (kgs): 131,058 KG",
  "document": "SI",
  "location": "line 10",
  "method": "rule"
}
```

Do NOT hallucinate absent values.

---

# 14. REAL FIXTURE VARIATION TO HANDLE

The repository's sample fixtures demonstrate that equivalent concepts may use different labels such as:

```text
Consignee
Consignee (Non-Negotiable)

Notify
Notify Party

Port of Loading (POL)
Load Port
POL

POD
Port of Discharge

Total Containers
Container Count

Gross Wt (kgs)
Gross Weight (KG)
```

There are also values such as:

```text
6 x 40'HC
```

which means:

```text
container_count = 6
container_type = 40HC
```

Only `container_count` is one of the required seven comparison fields.

Build semantic field mapping, not exact-label matching.

---

# 15. FIELD ALIAS LAYER

Keep a compact canonical alias dictionary.

Example:

```python
ALIASES = {
    "port_of_loading": [
        "port of loading",
        "load port",
        "loading port",
        "pol"
    ],
    "port_of_discharge": [
        "port of discharge",
        "discharge port",
        "pod"
    ],
    "gross_weight_kg": [
        "gross weight",
        "gross wt",
        "gross wt (kgs)",
        "total gross weight",
        "weight"
    ],
    "container_count": [
        "container count",
        "total containers",
        "containers",
        "number of containers"
    ]
}
```

Extend based on real fixtures.

Do not build an enormous ontology.

Unknown labels can be sent through semantic/LLM mapping.

---

# 16. CONTAINER COUNT PARSER

Must correctly distinguish:

```text
6
06
6 containers
6 x 40'HC
6X40HC
```

from:

```text
40
40HC
```

Example:

```text
6 x 40'HC
```

=>:

```text
count = 6
type = 40HC
```

Do not accidentally take `40` as the count.

---

# 17. GROSS WEIGHT PARSER

Normalize:

```text
131,058 KG
131058 KG
131,058 KGS
131058 kilograms
```

to:

```text
131058
```

Do not invent a business tolerance.

Default to exact normalized equality unless the challenge explicitly specifies another rule.

---

# 18. ENTITY NORMALIZATION

Safe normalization:

- case
- whitespace
- punctuation
- repeated spaces
- obvious corporate suffix punctuation

Example:

```text
ABC LOGISTICS SDN. BHD.
ABC Logistics Sdn Bhd
```

can normalize to the same comparison key.

But do NOT automatically equate:

```text
ABC LOGISTICS
ABC LOGISTICS MALAYSIA
```

just because fuzzy similarity is high.

Fuzzy similarity may be used as an ambiguity signal, never as an unquestioned final truth.

---

# 19. PORT NORMALIZATION

Support safe variants such as:

```text
Port Klang
PORT KLANG
Port Klang, Malaysia
```

Known port-code aliases may be supported when clearly justified by the dataset.

Do not spend the deadline building a giant external port database.

---

# 20. DETERMINISTIC COMPARISON ENGINE

For each of the seven fields:

```text
extract
→ validate
→ normalize
→ compare
```

Internal states:

```text
MATCH
MISMATCH
MISSING
UNCERTAIN
```

Logic:

```python
if uncertain:
    UNCERTAIN
elif missing:
    MISSING
elif normalized_si == normalized_bl:
    MATCH
else:
    MISMATCH
```

Final document result:

```text
IF any clear MISMATCH:
    status = MISMATCH

ELSE IF any MISSING:
    status = NEEDS_REVIEW

ELSE IF any UNCERTAIN:
    status = NEEDS_REVIEW

ELSE:
    status = OK
```

---

# 21. EXACT DEFECT FIELD REQUIREMENT

The challenge's self-scorer evaluates the exact defect fields.

Therefore:

If:

```text
container_count
```

differs:

```json
"defect_fields": ["container_count"]
```

If:

```text
container_count
gross_weight_kg
```

differ:

```json
"defect_fields": [
  "container_count",
  "gross_weight_kg"
]
```

Do NOT:

- return only the first mismatch
- return all seven fields
- rely only on `status=MISMATCH`
- use fuzzy similarity to decide the defect list

---

# 22. READING ERROR VS REAL DEFECT

Critical requirement:

```text
SI: 22,000 KG
BL raw OCR: 22,O00 K6
```

Do NOT confidently report a mismatch if the difference may be an OCR/read error.

Use:

```text
uncertain extraction
→ secondary validation if available
→ NEEDS_REVIEW if unresolved
```

Likewise:

```text
ABC SDN BHD
ABC SDN. BHD.
```

is normally a formatting match.

Reliability is not about avoiding all review.

Reliability means:

> make a decision when evidence is sufficient, and escalate when it is not.

---

# 23. REVIEW REASONS

Public reasons must be:

```text
wrong_doc_type
missing_attachment
unreadable
missing_value
```

Examples:

```text
BL cannot be found
→ missing_attachment

attachment is clearly not a BL
→ wrong_doc_type

document cannot be read
→ unreadable

required gross weight does not exist
→ missing_value
```

Do not invent additional public values.

---

# 24. PROCESSING FAILURES + RETRIES

The problem statement explicitly asks for failures to be handled visibly and retried where appropriate.

Implement:

```text
parse failure
→ retry once/twice where safe
→ if still failing:
   NEEDS_REVIEW
```

Expose internal error details to the UI/log.

Do NOT silently convert failures into:

```text
OK
```

---

# 25. SELF-EVALUATION LOOP

Run the Docker server.

Verify:

```text
GET /health
GET /emails
GET /sample_submission
```

Then:

```text
generate submission
→ POST /submit
→ inspect score
→ inspect failure patterns
→ fix
→ repeat
```

The official guide explicitly says the result can be submitted repeatedly while developing.

However:

> Do not optimize blindly from the score.

If the score decreases, inspect the actual source documents and make a reasoned change.

Do not use the hidden answer key.

---

# 26. TEST STRATEGY

Create automated tests for at least:

```text
1. all 7 fields match
2. shipper formatting variation
3. consignee formatting variation
4. notify variation
5. POL label variation
6. POD label variation
7. container count mismatch
8. gross weight mismatch
9. multiple mismatches
10. "6 x 40'HC" container parsing
11. XLSX SI
12. XLSX BL
13. missing SI
14. missing BL
15. wrong document
16. missing value
17. OCR-like ambiguity
18. new SI email
19. invoice query
20. general email
21. spam
22. every email ID preserved
23. exact submission schema
```

Use real repository fixtures wherever possible.

---

# 27. VALIDATION REPORT

Create a local report:

```text
=== SDOC REGRESSION ===

Emails processed: ...

Stage 1:
  BL_COMPARISON: ...
  SI_REQUEST: ...
  INVOICE_QUERY: ...
  GENERAL: ...
  SPAM: ...

Verification:
  OK: ...
  MISMATCH: ...
  NEEDS_REVIEW: ...

Formats:
  TXT: ...
  XLSX: ...
  PDF: ...
  DOCX: ...

Failures:
  classification: ...
  attachment resolution: ...
  extraction: ...
  normalization: ...
  comparison: ...
```

This report is for engineering.

Do not put unnecessary debug fields into public submission JSON.

---

# 28. HUMAN REVIEW UI

Because human-in-the-loop is explicitly part of the problem, make this visible.

A reviewer should see:

```text
EMAIL
↓
ATTACHMENTS
↓
SI / BL
↓
FIELD-BY-FIELD COMPARISON
↓
EVIDENCE
↓
REVIEW REASON
↓
ACTION
```

Example:

| Field | SI | BL | Status |
|---|---|---|---|
| Shipper | ABC Sdn Bhd | ABC SDN. BHD. | MATCH |
| Consignee | XYZ Ltd | XYZ Ltd | MATCH |
| Notify Party | XYZ Ltd | XYZ Ltd | MATCH |
| Port Loading | Port Klang | Port Klang | MATCH |
| Port Discharge | Singapore | Singapore | MATCH |
| Container Count | 3 | 4 | MISMATCH |
| Gross Weight | 22,000 kg | 22,O00 K6 | REVIEW |

Actions:

```text
Confirm Match
Confirm Mismatch
Edit Value
Retry
```

Keep it simple.

---

# 29. DEMO UX

The prototype should look like an **operations verification tool**, not a generic AI chat application.

Main dashboard:

```text
Total Emails
Document Checks
Clean
Discrepancies
Needs Review
```

Then:

```text
Inbox / Verification Queue
```

Then:

```text
Verification Detail
```

Avoid:

- login systems
- billing
- user administration
- giant analytics dashboards
- generic chat screens
- fake enterprise features

Every UI element should support the problem.

---

# 30. THREE REQUIRED DEMO STORIES

Prepare three polished cases.

## CASE 1 — CLEAN

```text
Email
→ identify comparison request
→ SI + BL
→ extract 7 fields
→ normalize
→ all match
→ OK
→ "No mismatch detected"
```

## CASE 2 — DEFECT

```text
Email
→ SI + BL
→ one/multiple fields differ
→ exact defect fields
→ MISMATCH
→ side-by-side evidence
```

## CASE 3 — HUMAN REVIEW

```text
Email
→ missing/unreadable/ambiguous data
→ NEEDS_REVIEW
→ evidence + reason
→ human confirms/edits
```

This demonstrates the entire problem rather than only extraction.

---

# 31. CLOUD + AI STORY FOR JUDGES

Be able to explain in one sentence:

> **Our cloud AI handles semantic understanding of messy emails and shipping documents, while our deterministic verification engine validates normalized values and escalates uncertainty instead of allowing the model to guess.**

Architecture slide:

```text
User
 ↓
Cloud-hosted Web App
 ↓
Backend API
 ├── Email Classifier
 ├── Document Parser
 ├── Cloud AI / LLM
 ├── Normalization + Validation
 ├── Comparison Engine
 └── Human Review Queue
 ↓
Result
```

Make the AI and cloud components visibly meaningful.

---

# 32. TECHNICAL FEASIBILITY / VALIDATION STORY

The judges explicitly assess whether key technical assumptions have been tested.

Your demo/docs should be able to show:

```text
real sample fixture
→ parsed correctly
→ normalized correctly
→ comparison correct
→ self-evaluation submitted
```

Also document limitations honestly:

```text
Supported:
TXT
XLSX
text PDF
...

Partial:
scanned PDF
...

Future:
advanced OCR/layout models
```

Do not claim production-grade OCR if you only have a prototype.

---

# 33. INNOVATION / DIFFERENTIATION

Do not pitch the idea as:

> "We use an LLM to compare two documents."

That is too generic.

The differentiator is:

```text
Inbox triage
+
document-role resolution
+
semantic extraction
+
deterministic verification
+
evidence-backed human escalation
```

The safety/reliability mechanism is central:

```text
AI does not decide blindly.
```

---

# 34. PRACTICAL VALUE / BUSINESS STORY

The system helps shipping operations reduce repetitive checking effort by:

```text
finding the right emails
→ extracting shipment fields
→ identifying discrepancies early
→ preventing avoidable draft corrections
→ sending ambiguous cases to a human
```

Do not claim unsupported monetary savings.

Use measured prototype metrics instead, for example:

```text
520 emails processed
X comparison requests
Y discrepancies detected
Z cases escalated
```

Only report metrics actually measured by the implementation.

---

# 35. SUBMISSION REQUIREMENTS

The rules require:

### Project Description
Include:

- project name
- purpose
- problem statement

### Demo Video
Maximum:

```text
5 minutes
```

Video should cover:

```text
Quick Intro
Problem
Tech Stack
Live Demo
Impact
```

The rules specify a deduction for every 30-second delay beyond the maximum, so target approximately:

```text
4:15–4:45
```

rather than producing a video near the hard limit.

### GitHub
Public repository with clear README and setup instructions.

### Live Prototype
Publicly accessible and functional during judging.

### Slides / Documentation
Must cover:

- Technical Architecture
- Implementation Details
- Challenges Faced
- Future Roadmap

Antigravity should update the README and create/maintain any technical documentation needed for these requirements.

---

# 36. 32-HOUR EXECUTION PLAN

## HOUR 0–1
Audit:

- existing repo
- Docker
- loader
- sample data
- sample submission
- current classifier

Run everything.

## HOUR 1–6
Build:

```text
BL_COMPARISON
→ SI + BL
→ TXT extraction
→ 7 fields
→ normalize
→ compare
→ exact submission
```

Get one real case completely working.

## HOUR 6–10
Add:

```text
XLSX parsing
field aliases
container parsing
numeric normalization
```

## HOUR 10–14
Add:

```text
PDF support
AI semantic extraction
AI cloud integration
```

Use AI meaningfully, but keep deterministic fallback paths.

## HOUR 14–17
Run the complete sample bundle.

Submit to:

```text
POST /submit
```

Fix the highest-impact errors.

## HOUR 17–20
Add:

```text
NEEDS_REVIEW
missing attachment
missing value
wrong doc
unreadable
retry handling
evidence
```

## HOUR 20–24
Build polished UI:

```text
Dashboard
Inbox
Verification
Review
```

## HOUR 24–27
Deploy publicly.

Verify:

- startup
- cloud AI
- API
- frontend
- sample demo

## HOUR 27–29
Prepare:

- architecture diagram
- README
- technical explanation
- measured metrics

## HOUR 29–31
Record the 3 demo cases and the ≤5 minute video.

## HOUR 31–32
FREEZE.

Only:

- bugs
- deployment fixes
- submission verification

No major new features.

---

# 37. ANTIGRAVITY CODING RULES

Because the deadline is hard:

### MUST
- inspect before editing
- reuse existing code
- run tests
- use real fixtures
- validate against the Docker scorer
- preserve exact submission schema
- keep AI meaningful
- keep cloud integration demonstrable
- show evidence for review cases
- document limitations

### MUST NOT
- rewrite the whole project
- modify the challenge scorer
- depend on ground truth
- add arbitrary shipping rules
- invent weight tolerances
- overuse fuzzy matching
- add a multi-agent framework unnecessarily
- build a vector database unnecessarily
- build authentication/billing
- spend hours on UI before the backend works
- claim unsupported accuracy

---

# 38. DEFINITION OF DONE

## Core
- [ ] all inbox emails classified
- [ ] BL comparison emails routed correctly
- [ ] SI identified
- [ ] BL identified
- [ ] seven fields extracted
- [ ] field aliases supported
- [ ] XLSX supported
- [ ] TXT supported
- [ ] PDF path works where present
- [ ] values normalized
- [ ] exact comparison implemented
- [ ] exact `defect_fields` generated
- [ ] NEEDS_REVIEW implemented
- [ ] retries implemented
- [ ] evidence preserved

## AI + Cloud
- [ ] AI is a meaningful part of the workflow
- [ ] cloud integration is real and demonstrable
- [ ] secrets use environment variables
- [ ] local fallback exists where practical

## Evaluator
- [ ] sample submission schema exact
- [ ] every email ID preserved
- [ ] `/submit` works
- [ ] self-evaluation results recorded
- [ ] no private answer-key dependency

## Human judging
- [ ] architecture is easy to explain
- [ ] core prototype works visibly
- [ ] tech integrations are meaningful
- [ ] validation evidence exists
- [ ] practical value is clear
- [ ] differentiation is clear
- [ ] future roadmap is documented

## Demo
- [ ] clean match
- [ ] true mismatch
- [ ] human review
- [ ] live deployed link
- [ ] 5-minute-or-less video

---

# 39. START IMMEDIATELY

Execute:

```text
1. Inspect actual repository and data.
2. Run existing classifier.
3. Run Docker.
4. Verify /health, /emails, /sample_submission, /submit.
5. Inspect representative TXT + XLSX + PDF fixtures.
6. Implement one complete end-to-end verification case.
7. Test against real data.
8. Submit to self-evaluation.
9. Fix the biggest errors.
10. Add AI + cloud integration.
11. Add review workflow.
12. Deploy.
13. Prepare demo/docs.
14. Freeze.
```

At the end, report:

```text
FILES CHANGED
WHAT ALREADY EXISTED
WHAT WAS ADDED
AI COMPONENT
CLOUD COMPONENT
TESTS RUN
SELF-EVALUATION RESULT
DEPLOYMENT URL
SUBMISSION FILE
KNOWN LIMITATIONS
DEFERRED FEATURES
```

Do not report a feature as complete unless you actually ran it.
