<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
<img src="https://img.shields.io/badge/MongoDB-7.0-47A248?style=for-the-badge&logo=mongodb&logoColor=white"/>
<img src="https://img.shields.io/badge/Status-MVP_v2.0-0D9488?style=for-the-badge"/>

# 🧠 Enterprise Knowledge Management (EKM)

**One Search. Every Source. Zero Silos.**

EKM unifies **SharePoint**, **Confluence**, **Jira**, and **GitHub Enterprise** into a single MongoDB-backed search engine — with BM25 relevance ranking, SME identification, entity extraction, code intelligence, and a full intelligence layer covering risk, velocity, gaps, handovers and learning paths.

[Features](#-features) · [Intelligence Layer](#-intelligence-layer) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [Configuration](#-configuration) · [API Reference](#-api-reference) · [Roadmap](#-roadmap)

</div>

---

## 💡 Why EKM?

> Employees at large organisations spend **up to 20% of their working week** searching for information — one full day per person, per week, wasted.

Knowledge lives in silos. Engineers work in Jira. Processes live in Confluence. Policies sit in SharePoint. Code history is buried in GitHub. When someone needs an answer, they search four tools, skim dozens of results, and still might not find it.

**The hidden costs:**
- **£104K+/year** per 10-person team at fully loaded cost rates
- **3–6 months** new joiner ramp time with no structured learning path
- **2 days** to compile audit evidence that EKM delivers in one click
- **60% of knowledge** lost when an SME or vendor exits

**EKM fixes this** — one query, every source, instant results, with intelligence on top.

---

## ✨ Features

### Core Search
- 🔍 **BM25 full-text search** — relevance-ranked results across all sources
- 🏷️ **Source filtering** — narrow to SharePoint / Confluence / Jira / GitHub instantly
- 🔄 **Incremental + Force Full sync** — incremental by default; Force Full toggle in UI
- 📊 **Live dashboard** — per-source doc counts, sync status, activity log
- 🔎 **Fuzzy fallback** — word-level regex fallback when exact match returns nothing
- ⌨️ **Global `/` keyboard search** — press `/` anywhere to open search modal

### Code Intelligence (GitHub)
- 📦 Commit indexing, source file crawl, PR indexing
- 🔍 **Explain this code** — 4-signal analysis: Jira cross-link, PR body, diff analysis, architecture docs

---

## 🧠 Intelligence Layer

10 tabs built entirely on existing indexed data:

| Tab | What it shows |
|-----|---------------|
| 📊 Analytics | Search volume, top queries, zero-result gaps |
| 📈 Velocity | 12-month activity chart, trend up/down per system |
| 🔴 Risk & Vendors | Vendor dependency alerts, concentration risk, 🔴🟠🟡🟢 levels |
| ❤️ Health | Freshness %, Jira↔Confluence link audit, stale docs |
| 🕳️ Knowledge Gaps | Systems active in Jira/GitHub with zero documentation |
| ⚠️ Experts At Risk | SMEs inactive 90d+ or vendor knowledge at risk |
| 📋 Coverage Score | 0–100 score per system, grade A–F, missing sources |
| 📦 Handover Tracker | Full pack + auto-saved checklist + Teams button |
| 👤 People | Contributor profiles, clickable topic chips |
| 🎓 Learning Path | Shareable new joiner URLs, Confluence-first ordering |

---

## 🎓 New Joiner Shareable URL

```
http://localhost:3000/join/payments-pipeline
```

No login required. Progress checkboxes. Completion banner. Copy link button.

---

## ⌨️ Global Search

Press `/` from anywhere → modal opens → type to search → `↑↓` navigate → `Enter` open → `Esc` close.

---

## 🔄 Force Full Sync

Dashboard has an **Incremental ↔ Force Full** toggle. Flip before Sync All to re-pull everything.

---

## Data Sources

| Source | Auth | Content |
|--------|------|---------|
| **Jira** (on-premise) | PAT token | Issues, comments, ADF bodies, metadata |
| **Confluence** (on-premise) | PAT token | Pages, spaces, HTML → plain text |
| **SharePoint Online** | Azure AD app | SitePages, document libraries |
| **GitHub Enterprise** | PAT token | Commits, code files, pull requests |

---

## 🏗️ Architecture

```
DATA SOURCES → CONNECTORS → CORE ENGINE → INTELLIGENCE (10 tabs)

🎫 Jira ──────── jira.py ──────┐
📖 Confluence ── confluence.py ─┤  🍃 MongoDB       📊 Analytics
📋 SharePoint ── sharepoint.py ─┤  BM25 Full-text   📈 Velocity
💻 GitHub GHE ── github.py ─────┘  FastAPI           🔴 Risk & Vendors
                                    APScheduler       🕳️ Knowledge Gaps
                  bm25.py           /api/search       ⚠️ Experts At Risk
                  sme_ranker.py     /api/intelligence  📋 Coverage Score
                  extractor.py                        📦 Handover Tracker
                  code_explainer.py                   👤 People
                                                      🎓 Learning Path
```

> **Editable architecture diagram**: `docs/EKM-Architecture.pptx` — fully editable PowerPoint shapes.

---

## 📁 Project Structure

```
ekm-mvp/
├── docs/
│   ├── EKM-Architecture.pptx    ← Editable architecture diagram
│   └── architecture.png         ← Legacy PNG
├── backend/
│   ├── main.py / config.py / database.py / models.py
│   ├── connectors/   jira.py · confluence.py · sharepoint.py · github.py
│   ├── routes/       search.py · api.py · explain.py · people.py
│   │                 analytics.py · intelligence.py
│   └── utils/        sync_service.py · bm25.py · sme_ranker.py
│                     extractor.py · file_extractor.py · code_explainer.py
└── frontend/src/
    ├── App.jsx                  ← Router, GlobalSearch, /join/:topic
    ├── api.js                   ← All API calls
    ├── pages/
    │   ├── Dashboard.jsx        ← Force Full toggle, sync, stats
    │   ├── Search.jsx           ← BM25 search, SME panel, GitHub cards
    │   ├── Documents.jsx        ← Document browser
    │   ├── Intelligence.jsx     ← 10-tab intelligence page
    │   └── NewJoiner.jsx        ← Public /join/:topic page
    └── components/
        ├── UI.jsx               ← Shared components
        └── GlobalSearch.jsx     ← Global / keyboard search modal
```

---

## ⚡ Quick Start

```bash
# 1. Configure
cp .env.example backend/.env
# Edit backend/.env

# 2. Backend
start-backend.bat          # Windows
./start-backend.sh         # Mac/Linux
# → http://localhost:8000

# 3. Frontend
start-frontend.bat         # Windows
./start-frontend.sh        # Mac/Linux
# → http://localhost:3000

# 4. Sync
# Click Sync All on Dashboard, then search or press /
```

---

## ⚙️ Configuration (`backend/.env`)

```env
MONGO_URI=mongodb://user:pass@host:port/db
MONGO_DB=your_database

JIRA_URL=https://jira.company.com
JIRA_USERNAME=your.name@company.com
JIRA_API_TOKEN=your-pat-token

CONFLUENCE_URL=https://confluence.company.com/confluence
CONFLUENCE_USERNAME=your.name@company.com
CONFLUENCE_API_TOKEN=your-pat-token

GITHUB_HOST=github.yourcompany.com
GITHUB_TOKEN=your-ghe-pat-token
GITHUB_REPOS=org/repo1,org/repo2

SHAREPOINT_SITE_URLS=https://company.sharepoint.com/sites/site1

SYNC_INTERVAL_MINUTES=60
TEAMS_DOMAIN=citi.com
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/search?q={query}` | BM25 search |
| `POST` | `/api/sync` | `{"source_type":"jira","force_full":false}` |
| `GET` | `/api/config` | App config |
| `GET` | `/api/people/search?q={name}` | Contributor search |
| `GET` | `/api/people/{name}` | Contribution profile |
| `GET` | `/api/analytics/stats?days=30` | Search trends |
| `GET` | `/api/intelligence/health` | Content health |
| `GET` | `/api/intelligence/risk` | Vendor dependency risk |
| `GET` | `/api/intelligence/velocity?topic={t}` | 12-month activity chart |
| `GET` | `/api/intelligence/gaps` | Undocumented systems |
| `GET` | `/api/intelligence/experts-at-risk` | At-risk SMEs |
| `GET` | `/api/intelligence/coverage` | Coverage score per topic |
| `GET` | `/api/intelligence/onboarding?topic={t}` | Structured learning path |
| `GET` | `/api/intelligence/handover/{name}` | Handover pack |
| `POST` | `/api/intelligence/handover/{name}/progress` | Save checklist |

---

## 🗺️ Roadmap

### ✅ Phase 1 — MVP v2.0 (Complete)
- [x] Unified BM25 search — 4 sources
- [x] SME ranking, entity extraction, code intelligence
- [x] 10-tab intelligence layer
- [x] Knowledge Velocity, Gaps, Experts At Risk, Coverage, Handover
- [x] New Joiner shareable URLs
- [x] Global `/` keyboard search
- [x] Force Full Sync UI toggle
- [x] Teams deep-link buttons

### Phase 2 — Workflow & Alerts
- [ ] Saved searches + email alerts
- [ ] Weekly knowledge digest email
- [ ] Jira webhook → auto-doc-check
- [ ] Export to PDF / CSV

### Phase 3 — Enterprise Security
- [ ] SSO (Azure AD / Okta)
- [ ] SharePoint Azure AD registration
- [ ] Role-based access
- [ ] Audit log (GDPR)

### Phase 4 — Sources
- [ ] ServiceNow, Slack, Google Drive

### Phase 5 — AI Layer
- [ ] RAG-based Q&A
- [ ] Knowledge graph
- [ ] Duplicate detection

---

<div align="center">
Built as an enterprise MVP · Python + FastAPI + React + MongoDB · v2.0 · March 2026
</div>
