# **Anime Poster → OP/ED Retrieval Tool**

*Project Specification Document*

---

## **1. Purpose**

Build a lightweight local tool that takes **one anime poster image** as input and returns **all opening and ending songs** associated with that anime (across all seasons), using a combination of image embedding similarity and AniList metadata retrieval.

This is the **MVP** that will later scale into the full “tier list segmentation + batch identification” tool.

---

## **2. Problem Statement**

Manually searching OP/ED songs for dozens or hundreds of anime is slow, error-prone, and repetitive. Posters inside tier list images are tiny and inconsistent, making reverse image search unreliable.

The solution must:

* Work offline (aside from AniList API calls).
* Identify anime using the uploaded poster.
* Produce correct OP/ED metadata automatically.
* Be extendable to multi-poster tier list segmentation later.

---

## **3. Scope**

### **In Scope**

* Single-poster upload through a simple UI (e.g., Streamlit).
* Embed the poster with a CLIP model.
* Compare against a local embedding database of known posters.
* Retrieve the anime title from the best match.
* Query AniList API for OP/ED lists.
* Return structured results (JSON/table).
* Automatic database expansion (optional).

### **Out of Scope (for MVP)**

* Tier list segmentation.
* Multi-poster batch processing.
* LLM orchestration (LangChain, agents).
* Local training or fine-tuning.

These will be reserved for the patched version.

---

## **4. Functional Requirements**

### **4.1 Inputs**

* A single poster image (`.jpg`, `.png`, `.jpeg`).

### **4.2 Core Functionalities**

1. **Poster Embedding Generation**
   * Use a CLIP model (`ViT-B/32` or equivalent) to generate an image embedding.
2. **Nearest Neighbor Search**
   * Compare embedding against local embedding store using cosine similarity.
   * Return top candidate with similarity score.
3. **Anime Matching Logic**
   * If similarity score is above threshold (e.g., 0.38–0.45), accept match.
   * Else present top 3 matches for manual confirmation (MVP fallback).
4. **Metadata Retrieval**
   * Query AniList API using anime ID/title.
   * Fetch:
     * Opening themes
     * Ending themes
     * Season/year info
     * Cover image
5. **Result Presentation**
   * Display OP/ED list cleanly (title, artist, season).
6. **Optional: Auto-Add New Posters**
   * If manual confirmation is done on an unknown anime:
     * Download official poster via AniList
     * Add poster + embedding to local DB automatically

### **4.3 Outputs**

* Anime title
* Synonyms / alternate titles
* Season list
* Opening themes (text + episode ranges)
* Ending themes (text + episode ranges)
* Confidence score
* (Optional) Downloaded poster saved into `poster_db/`

---

## **5. Non-Functional Requirements**

### **Performance**

* Poster identification within 1–2 seconds on CPU.
* AniList query < 500ms per call.

### **Reliability**

* System should gracefully handle:
  * No match found
  * Network/API failures
  * Bad image inputs

### **Maintainability**

* Modular folder structure:
  * `poster_db/` (raw images)
  * `embeddings/` (FAISS index or `.npy`)
  * `scripts/` (embedding builder, updater)
  * `app/` (Streamlit UI)

### **Extensibility**

* Clean enough that segmentation module can plug in later via:
  * `segment.py` → outputs array of crops
  * each crop goes through the same identification pipeline

### **Cost**

* Must run with  **zero paid APIs or LLMs** .
* Only external service: free AniList GraphQL endpoint.

---

## **6. Data Structures**

### **Embedding Index**

* `FAISS` index (recommended), or a simple NumPy matrix
* `labels.json` containing filenames or anime titles in matching index order

### **Poster Files**

Naming convention:

<pre class="overflow-visible!" data-start="4060" data-end="4146"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>poster_db/
    Steins Gate.jpg
    Haikyuu!! S1.jpg
    Attack </span><span>on</span><span> Titan S3.png
</span></span></code></div></div></pre>

### **Config File**

* `config.json`
  * CLIP model name
  * threshold values
  * DB paths

---

## **7. Workflow (MVP Data Flow)**

1. **User Uploads Poster**
2. Preprocess image (resize → tensor → normalize)
3. Generate embedding (CLIP)
4. Search in local embedding store (FAISS)
5. Pick top-ranked match
6. Load label → anime title
7. Query AniList API
8. Extract OP/ED lists
9. Display output to user
10. (Optional) If match was manually corrected:
    * auto-download correct poster
    * embed and add to DB

---

## **8. Assumptions**

* User has already downloaded posters for at least some anime.
* File naming is accurate and consistent.
* Poster images are visually representative of the anime (not fanart).
* CLIP is adequate for poster-level similarity.

---

## **9. Risks**

* Very small or noisy posters might produce false matches.
* Two posters with extremely similar compositions (e.g., same MC poses) might confuse CLIP.
* AniList may require debouncing if too many API calls per minute (rare for MVP).
* Naming inconsistencies can break metadata resolution.

---

## **10. Future Extensions**

### Short-Term

* Multi-image segmentation for full tier list extraction.
* Automatically scrape posters for *all* AniList titles in the tier list.
* Auto-build YouTube/Spotify OP/ED playlists.

### Long-Term

* YOLO-based poster detection in complex tier list layouts.
* OCR to detect series titles directly from tier list thumbnails.
* Local captioning model to auto-label new posters (zero manual work).
* Agent-based orchestration if you later decide to experiment with LLMs.

---

## **11. Success Metrics**

* **Accuracy** : ≥ 90% correct anime match on clean posters.
* **Speed** : ≤ 3 seconds end-to-end.
* **DB Growth** : Self-expands with minimal human intervention.
* **User Effort** : Zero manual OP/ED lookup required.
