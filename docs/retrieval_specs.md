# 📘 **PROJECT SPECIFICATION (FINAL ALIGNMENT VERSION)**

### *Anime Poster → OP/ED Retrieval System*

**Architecture: React Frontend + FastAPI Backend + CLIP/FAISS RAG + Gemini Fallback + AniList Provider**

---

## **1. System Overview**

This system identifies an anime from its poster and retrieves the corresponding opening/ending songs. It supports:

* Single-poster upload
* Future multi-poster tier-list segmentation
* Local embedding-based retrieval (RAG)
* Gemini fallback when the local DB has no match
* Automatic local database growth
* A UI built in React/TypeScript

The goal is a **hybrid engine** where RAG is fast, local, and scalable, while Gemini fills in missing knowledge.

---

## **2. High-Level Flow**

<pre class="overflow-visible! px-0!" data-start="3082" data-end="3348"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>Frontend → Upload Poster
Backend → CLIP Embedding
→ FAISS </span><span>Search</span><span> (</span><span>local</span><span>)
→ IF confident </span><span>match</span><span> → </span><span>return</span><span></span><span>result</span><span>
→ </span><span>ELSE</span><span> → Gemini classification
→ </span><span>Normalize</span><span></span><span>+</span><span> store image
→ Compute </span><span>+</span><span> store embedding
→ </span><span>Update</span><span> FAISS
→ </span><span>Fetch</span><span> OP</span><span>/</span><span>ED </span><span>from</span><span> AniList
→ </span><span>Return</span><span></span><span>result</span><span></span><span>to</span><span> UI
</span></span></code></div></div></pre>

---

## **3. Core Components**

### **3.1 Frontend (React + TypeScript)**

* Upload component
* Camera component
* API service file calling `/api/identify`
* Shows anime name and OP/ED list
* Shows fallback engine used (RAG vs Gemini)

Frontend DOES NOT:

* Call Gemini directly
* Handle embeddings
* Store business logic

---

### **3.2 Backend (Python + FastAPI)**

Backend routes:

* `POST /api/identify` — main engine
* `POST /api/add_poster` — future manual ingestion
* `GET /api/db` — debug route for listing DB contents

Backend modules:

* `router.py` → orchestrates RAG vs Gemini
* `rag/clip_embedder.py` → CLIP embedding
* `rag/vector_store.py` → FAISS nearest neighbor
* `gemini/client.py` → Gemini image classification
* `database/storage.py` → JSON read/write
* `anilist/fetcher.py` → OP/ED retrieval

---

### **3.3 Local Database (JSON)**

#### **Structure file:**

`data/posters.json`

#### **Purpose:**

* Already-known anime
* Embeddings
* Poster metadata
* Lookup table for FAISS backend

---

### **3.4 Vector Database (FAISS)**

#### **Purpose**

* Fast nearest-neighbor search
* Helps detect exact matches or close variants

#### **Runtime**

* Loaded at server start
* Updated dynamically when new posters are added

---

### **3.5 CLIP Embedding Model**

#### **Purpose**

Convert images → 512 dimensional vectors.

#### **Why CLIP?**

* Reliable for anime posters
* Embeddings stable across lighting/variations
* Fast inference

---

### **3.6 Gemini Fallback System**

Used only when:

* Vector search confidence is low
* Poster not in local DB
* Poster is visually ambiguous

Gemini returns:

* Anime title (raw)

Backend normalizes:

* converts to slug
* renames file
* stores to DB

---

## **4. File Naming Normalization**

**Rules:**

* snake_case
* english alphabet only
* spaces → `_`
* punctuation removed
* season → `_s1`, `_s2`, etc.
* extension preserved

Examples:

<pre class="overflow-visible! px-0!" data-start="5323" data-end="5392"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>steins_gate.png
jujutsu_kaisen_s1.jpg
attack_on_titan_s3.webp
</span></span></code></div></div></pre>

---

## **5. JSON Metadata Structure (Final)**

<pre class="overflow-visible! px-0!" data-start="5442" data-end="5737"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre! language-json"><span><span>{</span><span>
  </span><span>"<slug>"</span><span>:</span><span></span><span>{</span><span>
    </span><span>"title"</span><span>:</span><span></span><span>"<canonical anime title>"</span><span>,</span><span>
    </span><span>"slug"</span><span>:</span><span></span><span>"<normalized_slug>"</span><span>,</span><span>
    </span><span>"path"</span><span>:</span><span></span><span>"posters/<filename>"</span><span>,</span><span>
    </span><span>"season"</span><span>:</span><span> <number or </span><span>null</span><span>></span><span>,</span><span>
    </span><span>"embedding"</span><span>:</span><span></span><span>[</span><span></span><span>/* 512 floats */</span><span></span><span>]</span><span>,</span><span>
    </span><span>"added_at"</span><span>:</span><span></span><span>"<ISO timestamp>"</span><span>,</span><span>
    </span><span>"source"</span><span>:</span><span></span><span>"user"</span><span> | </span><span>"auto"</span><span>,</span><span>
    </span><span>"notes"</span><span>:</span><span></span><span>null</span><span>
  </span><span>}</span><span>
</span><span>}</span><span>
</span></span></code></div></div></pre>

---

## **6. RAG vs Gemini Routing Decision**

### **Distance Threshold Rule**

<pre class="overflow-visible! px-0!" data-start="5818" data-end="5904"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>IF nearest_neighbor_distance </span><span><</span><span></span><span>0.28</span><span>
      → TRUST RAG
</span><span>ELSE</span><span>
      → </span><span>CALL</span><span> GEMINI
</span></span></code></div></div></pre>

Threshold adjustable after testing.

---

## **7. Frontend–Backend Contract**

### **POST /api/identify** returns:

<pre class="overflow-visible! px-0!" data-start="6021" data-end="6179"><div class="contain-inline-size rounded-2xl corner-superellipse/1.1 relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre! language-json"><span><span>{</span><span>
  </span><span>"title"</span><span>:</span><span></span><span>"Steins;Gate"</span><span>,</span><span>
  </span><span>"slug"</span><span>:</span><span></span><span>"steins_gate"</span><span>,</span><span>
  </span><span>"engine"</span><span>:</span><span></span><span>"RAG"</span><span>,</span><span>
  </span><span>"op"</span><span>:</span><span></span><span>[</span><span>...</span><span>]</span><span>,</span><span>
  </span><span>"ed"</span><span>:</span><span></span><span>[</span><span>...</span><span>]</span><span>,</span><span>
  </span><span>"poster_path"</span><span>:</span><span></span><span>"posters/steins_gate.png"</span><span>
</span><span>}</span><span>
</span></span></code></div></div></pre>

Frontend only needs to support this structure.

---

## **8. Future Extensions**

* Tier list segmentation
* Web scraping for alternative providers
* Moving from JSON → SQLite/Postgres
* Batch imports of poster folders
* Anime character recognition fallback
