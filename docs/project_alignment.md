# 🧩 **ALIGNMENT GAME PLAN FOR THE AI POSTER → SONG RETRIEVAL PROJECT**

*(For Planner Agent Awareness & Coordination)*

## **1. Core Constraint: Avoid Identity Crisis in the Codebase**

The system currently has two prototype directions:

* **Prototype A:** Frontend (React + TypeScript) calling Gemini directly
* **Prototype B:** Backend (Python) scaffold prepared for RAG, embeddings, segmentation, etc.

The planner must ensure:

* No cross-language pollution
* No duplicated logic
* No rewriting working components unnecessarily
* No collapsing the project into a single-language stack “just because it feels cleaner”

The solution is  **proper layering** , not rewriting.

---

# **2. Final Architecture Direction (Locked In)**

The planner must commit to this architecture:

### **Frontend (React + TS)**

* Handles UI, uploads, camera, interaction
* Sends files → Python backend
* Receives JSON results
* Does NOT call Gemini directly after integration
* Does NOT contain business logic

### **Backend (Python + FastAPI)**

* Orchestrates the entire system
* Hosts the RAG retrieval path
* Hosts Gemini call path
* Normalizes outputs
* Stores/updates poster embeddings
* Acts as the single source of truth
* Exposes `/api/identify` for the frontend

### **Database (Vector DB or simple local embedding storage)**

* Stores poster embeddings
* Supports approximate nearest neighbor search
* Gets updated when user adds new posters

---

# **3. Hybrid Engine Strategy**

The planner must maintain a  **fallback-first approach** :

### Order of operations:

1. **Try RAG match**
   * If similarity ≥ threshold → trust RAG
2. **If no match or confidence low → call Gemini**
   * Gemini returns the title
3. **Normalize anime title string**
4. **Add poster + embedding to the local DB**
5. **Return OP/ED data fetched via AniList API**

This guarantees:

* Local RAG grows stronger over time
* Gemini becomes a fallback, not the main driver
* The system is practical while still learning-RAG design principles

---

# **4. File Naming + Data Hygiene Rules**

Planner must enforce a clean data naming rule:

<pre class="overflow-visible! px-0!" data-start="2496" data-end="2589"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>poster/steins_gate_01.png
poster/attack_on_titan_s3.jpg
poster/jujutsu_kaisen_s1.webp
</span></span></code></div></div></pre>

* Use snake_case
* Only anime titles + season
* Never store raw user filenames
* Backend renames images automatically
* Frontend never touches filenames

Backend stores mapping:

<pre class="overflow-visible! px-0!" data-start="2779" data-end="2873"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>{</span><span>
  </span><span>"steins_gate"</span><span>:</span><span></span><span>"Steins;Gate"</span><span>,</span><span>
  </span><span>"jujutsu_kaisen_s1"</span><span>:</span><span></span><span>"Jujutsu Kaisen (Season 1)"</span><span>
</span><span>}</span><span>
</span></span></code></div></div></pre>

---

# **5. Planning the Merge**

The existing TS service files that currently call Gemini need to be:

**Refactored** to call:

<pre class="overflow-visible! px-0!" data-start="3002" data-end="3049"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>POST http://localhost:8000/api/identify
</span></span></code></div></div></pre>

NOT **ported** into Python.

NOT **copied** into Python.

NOT **placed** in the backend folder.

The planner should ensure:

* TS logic stays in frontend
* Gemini logic is rewritten in Python
* Frontend transitions from using Gemini → using backend route

---

# **6. Component Responsibility Definition**

### **Frontend:**

* Uploads image
* Sends file to backend
* Displays results
* Nothing more

### **Backend:**

* Receives image
* Runs RAG
* If no confident match, queries Gemini
* Parses Gemini output
* Queries AniList
* Writes result back
* Stores embedding

### **Vector DB:**

* Embedding store
* RAG search
* Local knowledge base

The planner must defend these borders.

---

# **7. Integration Approach**

Planner should follow this order:

### Phase 1 — Stabilize front-back link

* Make backend endpoint live
* Frontend calls `/api/identify` successfully
* Make sure both prototypes communicate

### Phase 2 — Implement Gemini backend version

* Move TS Gemini logic to Python
* Keep API contract stable

### Phase 3 — Implement RAG pipeline

* Build embeddings and local index
* Add fallback logic
* Add storage

### Phase 4 — Add auto-ingestion and renaming

* Backend renames poster
* Stores embedding
* Updates vector DB

### Phase 5 — Add segmentation (optional future)

* Multi-poster tier list
* Extracting individual posters

Planner must not jump phases.

Planner must not optimize prematurely.

Planner must avoid breaking the working prototype.

---

# **8. Priority Philosophy (for the Planner)**

If stuck choosing between:

* Doing it the clean RAG/ML way

  vs.
* Doing it the practical fast way

**Choose practical, but leave clear hooks for the ML version.**

This prevents dead ends and rework.

---

# **9. Non-Negotiable Rules**

The planner must enforce:

* Do NOT merge TS into backend
* Do NOT rewrite frontend into Python
* Do NOT break API contract
* Do NOT store business logic in the frontend
* Do NOT store user filenames
* Do NOT delay backend integration
* Do NOT run RAG before wiring the base endpoint

If violated, raise a warning of “Architecture Drift Detected.”
