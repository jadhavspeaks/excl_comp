"""
Intelligence Routes
────────────────────
GET /api/intelligence/health        — content freshness, knowledge audit, untouched docs
GET /api/intelligence/risk          — vendor dependency + concentration risk per topic
GET /api/intelligence/onboarding    — top 10 docs for a topic (onboarding path)
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, Query
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

VENDOR_PATTERN   = re.compile(r'\[TECH NE\]', re.IGNORECASE)
INTERNAL_PATTERN = re.compile(r'\[TECH\]', re.IGNORECASE)


def _classify(name: str) -> str:
    if VENDOR_PATTERN.search(name or ""):
        return "vendor"
    if INTERNAL_PATTERN.search(name or ""):
        return "internal"
    return "unknown"


def _days_ago(dt) -> int | None:
    if not dt:
        return None
    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def get_health():
    """
    Content health report:
    - Freshness per source (% docs updated in last 30/90/365 days)
    - Knowledge audit (Jira tickets with/without linked Confluence pages)
    - Untouched docs (ingested but never appeared in a search, oldest first)
    - Stale docs (not updated in 180+ days)
    """
    db = get_db()

    # ── 1. Fetch all docs (lightweight projection) ────────────────────────────
    cursor = db.documents.find(
        {},
        {"source_type": 1, "source": 1, "title": 1, "url": 1,
         "updated_at": 1, "ingested_at": 1, "entities": 1, "tags": 1}
    )
    all_docs = await cursor.to_list(length=50000)

    now = datetime.now(timezone.utc)
    source_stats: dict[str, dict] = {}
    stale_docs = []
    total_by_source: dict[str, int] = {}

    for doc in all_docs:
        st = doc.get("source_type", "unknown")
        total_by_source[st] = total_by_source.get(st, 0) + 1

        if st not in source_stats:
            source_stats[st] = {"fresh_30": 0, "fresh_90": 0, "fresh_365": 0, "total": 0}
        source_stats[st]["total"] += 1

        age = _days_ago(doc.get("updated_at") or doc.get("ingested_at"))
        if age is not None:
            if age <= 30:
                source_stats[st]["fresh_30"] += 1
            if age <= 90:
                source_stats[st]["fresh_90"] += 1
            if age <= 365:
                source_stats[st]["fresh_365"] += 1
            if age > 180:
                stale_docs.append({
                    "title":       doc.get("title", ""),
                    "source_type": st,
                    "source":      doc.get("source", ""),
                    "url":         doc.get("url", ""),
                    "days_old":    age,
                })

    # Freshness summary
    freshness = []
    for st, stats in source_stats.items():
        t = stats["total"] or 1
        freshness.append({
            "source":       st,
            "total":        stats["total"],
            "fresh_30d_pct":  round(stats["fresh_30"] / t * 100),
            "fresh_90d_pct":  round(stats["fresh_90"] / t * 100),
            "fresh_365d_pct": round(stats["fresh_365"] / t * 100),
            "health": (
                "good"    if stats["fresh_90"] / t > 0.7 else
                "warning" if stats["fresh_90"] / t > 0.4 else
                "poor"
            )
        })

    # ── 2. Knowledge audit: Jira ↔ Confluence link % ─────────────────────────
    jira_docs = [d for d in all_docs if d.get("source_type") == "jira"]
    confluence_titles = {
        d.get("title", "").lower().strip()
        for d in all_docs if d.get("source_type") == "confluence"
    }

    linked = 0
    for jdoc in jira_docs:
        entities = jdoc.get("entities") or {}
        jira_tickets = entities.get("jira_tickets", [])
        title = jdoc.get("title", "").lower()
        # Count as linked if any confluence page title contains the Jira key
        # or if entities from this doc appear in confluence content
        for ctitle in confluence_titles:
            for ticket in jira_tickets:
                if ticket.lower() in ctitle:
                    linked += 1
                    break

    jira_total = len(jira_docs) or 1
    audit = {
        "jira_total":      len(jira_docs),
        "confluence_total": len([d for d in all_docs if d.get("source_type") == "confluence"]),
        "linked_count":    linked,
        "linked_pct":      round(linked / jira_total * 100, 1),
        "unlinked_count":  len(jira_docs) - linked,
        "health": (
            "good"    if linked / jira_total > 0.5 else
            "warning" if linked / jira_total > 0.2 else
            "poor"
        )
    }

    # ── 3. Untouched docs: ingested long ago, stale ───────────────────────────
    stale_docs.sort(key=lambda x: x["days_old"], reverse=True)

    # ── 4. Untouched knowledge via search logs ────────────────────────────────
    # Docs that have never matched any search (approximate — by tag)
    search_cursor = db.search_logs.find({}, {"query": 1})
    search_logs   = await search_cursor.to_list(length=10000)
    searched_terms = set()
    for sl in search_logs:
        for word in re.findall(r'\b[a-z]{3,}\b', sl.get("query", "").lower()):
            searched_terms.add(word)

    never_searched = []
    for doc in all_docs:
        title = doc.get("title", "").lower()
        title_words = set(re.findall(r'\b[a-z]{3,}\b', title))
        if title_words and not title_words.intersection(searched_terms):
            age = _days_ago(doc.get("ingested_at"))
            if age and age > 30:
                never_searched.append({
                    "title":       doc.get("title", ""),
                    "source_type": doc.get("source_type", ""),
                    "url":         doc.get("url", ""),
                    "days_ingested": age,
                })
    never_searched.sort(key=lambda x: x["days_ingested"], reverse=True)

    return {
        "total_docs":    len(all_docs),
        "freshness":     freshness,
        "audit":         audit,
        "stale_docs":    stale_docs[:20],
        "never_searched": never_searched[:20],
        "generated_at":  now.isoformat(),
    }


# ── Risk ──────────────────────────────────────────────────────────────────────

@router.get("/risk")
async def get_risk():
    """
    Risk intelligence:
    - Vendor dependency per topic/project (TECH NE signal)
    - Knowledge concentration (1 person owns a topic)
    - Overall risk summary
    """
    db = get_db()

    cursor = db.documents.find(
        {},
        {"source_type": 1, "source": 1, "author": 1, "metadata": 1,
         "tags": 1, "title": 1, "updated_at": 1, "url": 1}
    )
    all_docs = await cursor.to_list(length=50000)

    # ── Per-topic contributor analysis ────────────────────────────────────────
    topic_people: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "type": "unknown", "count": 0, "roles": set()
    }))
    # Also track top docs per topic for drill-down links
    topic_docs: dict[str, list] = defaultdict(list)

    for doc in all_docs:
        st = doc.get("source_type", "")
        m  = doc.get("metadata") or {}

        # Get topic identifier
        topics = []
        for tag in (doc.get("tags") or []):
            if tag not in ("jira", "confluence", "sharepoint", "github",
                          "commit", "pull_request", "page", "file", "document"):
                topics.append(tag)

        people = []
        if st == "jira":
            for role, field in [("Reporter", "reporter"), ("Assignee", "assignee")]:
                person = m.get(field, "")
                if person:
                    people.append((person, role))
        elif st == "confluence":
            person = doc.get("author", "")
            if person:
                people.append((person, "Author"))
        elif st == "github":
            person = m.get("author_name") or doc.get("author", "")
            ct     = m.get("content_type", "")
            if person:
                people.append((person, "Commit Author" if ct == "commit" else "PR Author"))
        elif st == "sharepoint":
            person = doc.get("author", "")
            if person:
                people.append((person, "Author"))

        for person, role in people:
            person = person.strip()
            if not person:
                continue
            for topic in topics[:3]:
                topic_people[topic][person]["type"] = _classify(person)
                topic_people[topic][person]["count"] += 1
                topic_people[topic][person]["roles"].add(role)

        # Store doc reference per topic (for drill-down)
        for topic in topics[:3]:
            if len(topic_docs[topic]) < 8:
                topic_docs[topic].append({
                    "title":       doc.get("title", ""),
                    "source_type": st,
                    "url":         doc.get("url", ""),
                    "updated_at":  doc.get("updated_at").isoformat()
                        if isinstance(doc.get("updated_at"), datetime) else "",
                })

    # ── Build risk alerts ─────────────────────────────────────────────────────
    risk_topics = []
    for topic, people in topic_people.items():
        if len(people) == 0:
            continue

        total_contribs = sum(p["count"] for p in people.values())
        vendor_contribs  = sum(p["count"] for p in people.values() if p["type"] == "vendor")
        internal_contribs = sum(p["count"] for p in people.values() if p["type"] == "internal")

        vendor_pct   = round(vendor_contribs / total_contribs * 100) if total_contribs else 0
        internal_pct = round(internal_contribs / total_contribs * 100) if total_contribs else 0
        unique_people = len(people)

        # Risk level
        if vendor_pct >= 80 or (vendor_pct > 50 and unique_people <= 2):
            risk_level = "critical"
        elif vendor_pct >= 50 or (vendor_pct > 30 and unique_people <= 3):
            risk_level = "high"
        elif vendor_pct >= 20:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Concentration risk
        if unique_people == 1:
            concentration = "critical"
        elif unique_people == 2:
            concentration = "high"
        elif unique_people <= 4:
            concentration = "medium"
        else:
            concentration = "low"

        top_people = sorted(
            people.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:5]

        risk_topics.append({
            "topic":          topic,
            "total_docs":     total_contribs,
            "unique_people":  unique_people,
            "vendor_pct":     vendor_pct,
            "internal_pct":   internal_pct,
            "risk_level":     risk_level,
            "concentration":  concentration,
            "top_docs":       topic_docs.get(topic, [])[:6],
            "top_contributors": [
                {
                    "name":  name,
                    "type":  info["type"],
                    "count": info["count"],
                    "roles": list(info["roles"]),
                }
                for name, info in top_people
            ]
        })

    # Sort by risk — critical first, then by vendor %
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    risk_topics.sort(key=lambda x: (risk_order[x["risk_level"]], -x["vendor_pct"]))

    # ── Summary ───────────────────────────────────────────────────────────────
    critical_count = sum(1 for t in risk_topics if t["risk_level"] == "critical")
    high_count     = sum(1 for t in risk_topics if t["risk_level"] == "high")

    # Overall vendor dependency across all docs
    all_authors = defaultdict(lambda: {"type": "unknown", "count": 0})
    for doc in all_docs:
        m = doc.get("metadata") or {}
        for person in [
            doc.get("author"),
            m.get("reporter"),
            m.get("assignee"),
            m.get("author_name"),
        ]:
            if person and person.strip():
                p = person.strip()
                all_authors[p]["type"]  = _classify(p)
                all_authors[p]["count"] += 1

    total_people   = len(all_authors)
    vendor_people  = sum(1 for a in all_authors.values() if a["type"] == "vendor")
    internal_people = sum(1 for a in all_authors.values() if a["type"] == "internal")

    return {
        "summary": {
            "total_topics":     len(risk_topics),
            "critical_topics":  critical_count,
            "high_risk_topics": high_count,
            "total_contributors": total_people,
            "vendor_contributors": vendor_people,
            "internal_contributors": internal_people,
            "vendor_pct": round(vendor_people / total_people * 100) if total_people else 0,
        },
        "topics": risk_topics[:50],
    }


# ── Onboarding (Learning Path) ───────────────────────────────────────────────

# Source priority for learning — Jira is reference only, not primary reading
LEARNING_PRIORITY = {"confluence": 1, "sharepoint": 2, "github": 3, "jira": 99}
LEARNING_LABELS   = {
    "confluence": "📖 Read First",
    "sharepoint": "📋 Process Docs",
    "github":     "💻 Code Reference",
    "jira":       "🎫 Related Tickets",
}

@router.get("/onboarding")
async def get_onboarding_path(
    topic: str = Query(..., min_length=1),
    limit: int = Query(15, ge=1, le=30)
):
    """
    Generate a structured learning path for a topic.
    Sources are grouped and ordered: Confluence -> SharePoint -> GitHub -> Jira (reference only).
    """
    from utils.bm25 import rerank_bm25

    db = get_db()

    cursor = db.documents.find(
        {"$text": {"$search": topic}},
        {"title": 1, "source_type": 1, "source": 1, "url": 1,
         "content": 1, "author": 1, "updated_at": 1, "tags": 1, "metadata": 1}
    ).limit(300)
    docs = await cursor.to_list(length=300)

    if not docs:
        cursor = db.documents.find(
            {"tags": {"$regex": re.escape(topic), "$options": "i"}},
            {"title": 1, "source_type": 1, "source": 1, "url": 1,
             "content": 1, "author": 1, "updated_at": 1, "tags": 1}
        ).limit(150)
        docs = await cursor.to_list(length=150)

    if not docs:
        return {"topic": topic, "sections": [], "total": 0}

    ranked = rerank_bm25(topic, docs)

    # Group by source type with per-source limits
    buckets = {"confluence": [], "sharepoint": [], "github": [], "jira": []}
    per_source_limit = {"confluence": 8, "sharepoint": 5, "github": 5, "jira": 5}

    for doc in ranked:
        st = doc.get("source_type", "")
        if st not in buckets:
            continue
        if len(buckets[st]) >= per_source_limit.get(st, 5):
            continue
        age = _days_ago(doc.get("updated_at"))
        buckets[st].append({
            "title":       doc.get("title", ""),
            "source_type": st,
            "source":      doc.get("source", ""),
            "url":         doc.get("url", ""),
            "author":      doc.get("author"),
            "updated_at":  doc.get("updated_at").isoformat()
                if isinstance(doc.get("updated_at"), datetime) else "",
            "days_old":    age,
            "relevance":   round(doc.get("bm25_score", 0), 2),
            "stale":       age > 180 if age else False,
        })

    # Build ordered sections — Confluence first, Jira last
    sections = []
    read_order = 1
    for st in ["confluence", "sharepoint", "github", "jira"]:
        if not buckets[st]:
            continue
        for doc in buckets[st]:
            doc["read_order"] = read_order
            read_order += 1
        sections.append({
            "source_type":  st,
            "label":        LEARNING_LABELS[st],
            "is_reference": st == "jira",
            "docs":         buckets[st],
        })

    total = sum(len(s["docs"]) for s in sections)
    return {"topic": topic, "sections": sections, "total": total}


# ── Knowledge Gaps ────────────────────────────────────────────────────────────

@router.get("/gaps")
async def get_knowledge_gaps():
    """
    Undocumented systems: topics active in Jira/GitHub but with zero Confluence/SharePoint pages.
    """
    db = get_db()

    cursor = db.documents.find(
        {},
        {"source_type": 1, "tags": 1, "title": 1, "url": 1, "updated_at": 1, "metadata": 1}
    )
    all_docs = await cursor.to_list(length=50000)

    SKIP_TAGS = {"jira", "confluence", "sharepoint", "github",
                 "commit", "pull_request", "page", "file", "document"}

    tag_sources = defaultdict(lambda: defaultdict(int))
    tag_samples = defaultdict(list)

    for doc in all_docs:
        st = doc.get("source_type", "")
        for tag in (doc.get("tags") or []):
            if tag in SKIP_TAGS or len(tag) < 3:
                continue
            tag_sources[tag][st] += 1
            if len(tag_samples[tag]) < 3:
                tag_samples[tag].append({
                    "title":       doc.get("title", ""),
                    "source_type": st,
                    "url":         doc.get("url", ""),
                })

    gaps = []
    for tag, sources in tag_sources.items():
        jira_count       = sources.get("jira", 0)
        github_count     = sources.get("github", 0)
        confluence_count = sources.get("confluence", 0)
        sharepoint_count = sources.get("sharepoint", 0)
        activity         = jira_count + github_count
        documented       = confluence_count + sharepoint_count

        if activity < 3 or documented > 0:
            continue

        severity = "critical" if activity >= 20 else "high" if activity >= 10 else "medium"

        gaps.append({
            "topic":           tag,
            "severity":        severity,
            "jira_tickets":    jira_count,
            "github_refs":     github_count,
            "activity_total":  activity,
            "confluence_docs": confluence_count,
            "sharepoint_docs": sharepoint_count,
            "sample_docs":     tag_samples[tag],
            "recommendation":  (
                f"Create a Confluence page for '{tag}' — "
                f"{activity} work items reference this system with no documentation."
            ),
        })

    severity_order = {"critical": 0, "high": 1, "medium": 2}
    gaps.sort(key=lambda x: (severity_order[x["severity"]], -x["activity_total"]))

    return {
        "total_gaps":    len(gaps),
        "critical_gaps": sum(1 for g in gaps if g["severity"] == "critical"),
        "high_gaps":     sum(1 for g in gaps if g["severity"] == "high"),
        "gaps":          gaps[:40],
    }


# ── Expert Knowledge At Risk ──────────────────────────────────────────────────

@router.get("/experts-at-risk")
async def get_experts_at_risk():
    """
    SMEs whose knowledge is at risk: inactive 90d+, vendors, or sole topic owners.
    """
    db = get_db()

    cursor = db.documents.find(
        {},
        {"source_type": 1, "author": 1, "metadata": 1,
         "tags": 1, "title": 1, "url": 1, "updated_at": 1}
    )
    all_docs = await cursor.to_list(length=50000)

    now = datetime.now(timezone.utc)
    SKIP_TAGS = {"jira", "confluence", "sharepoint", "github",
                 "commit", "pull_request", "page", "file", "document"}

    person_stats = {}

    for doc in all_docs:
        st = doc.get("source_type", "")
        m  = doc.get("metadata") or {}

        people = []
        if st == "jira":
            for p in [m.get("reporter"), m.get("assignee")]:
                if p: people.append(p.strip())
        elif st == "confluence":
            p = doc.get("author", "")
            if p: people.append(p.strip())
        elif st == "github":
            p = m.get("author_name") or doc.get("author", "")
            if p: people.append(p.strip())
        elif st == "sharepoint":
            p = doc.get("author", "")
            if p: people.append(p.strip())

        topics = [t for t in (doc.get("tags") or []) if t not in SKIP_TAGS and len(t) >= 3]

        updated = doc.get("updated_at")
        if updated and isinstance(updated, str):
            try: updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except: updated = None
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)

        for person in set(people):
            if not person:
                continue
            if person not in person_stats:
                person_stats[person] = {
                    "name": person, "type": _classify(person),
                    "doc_count": 0, "topics": set(),
                    "sources": set(), "last_active": None,
                }
            ps = person_stats[person]
            ps["doc_count"] += 1
            ps["sources"].add(st)
            ps["topics"].update(topics[:3])
            if updated:
                if ps["last_active"] is None or updated > ps["last_active"]:
                    ps["last_active"] = updated

    at_risk = []
    for person, ps in person_stats.items():
        if ps["doc_count"] < 3:
            continue
        last_active   = ps["last_active"]
        days_inactive = (now - last_active).days if last_active else 999
        is_inactive   = days_inactive >= 90
        is_vendor     = ps["type"] == "vendor"
        topic_count   = len(ps["topics"])

        if not is_inactive and not is_vendor:
            continue

        risk_factors = []
        if is_inactive: risk_factors.append(f"Inactive {days_inactive}d")
        if is_vendor:   risk_factors.append("External vendor [TECH NE]")

        risk_level = (
            "critical" if (is_inactive and is_vendor) or days_inactive >= 365 else
            "high"     if is_inactive or (is_vendor and topic_count >= 3) else
            "medium"
        )

        at_risk.append({
            "name":           person,
            "type":           ps["type"],
            "risk_level":     risk_level,
            "risk_factors":   risk_factors,
            "doc_count":      ps["doc_count"],
            "topic_count":    topic_count,
            "top_topics":     list(ps["topics"])[:5],
            "sources":        list(ps["sources"]),
            "last_active":    last_active.strftime("%Y-%m-%d") if last_active else None,
            "days_inactive":  days_inactive,
            "recommendation": (
                "Urgent knowledge transfer — vendor + inactive." if (is_inactive and is_vendor) else
                f"Schedule knowledge transfer — inactive {days_inactive}d." if is_inactive else
                "Document knowledge before contract ends."
            ),
        })

    risk_order = {"critical": 0, "high": 1, "medium": 2}
    at_risk.sort(key=lambda x: (risk_order[x["risk_level"]], -x["doc_count"]))

    return {
        "total_at_risk":  len(at_risk),
        "critical_count": sum(1 for p in at_risk if p["risk_level"] == "critical"),
        "high_count":     sum(1 for p in at_risk if p["risk_level"] == "high"),
        "experts":        at_risk[:30],
    }


# ── Documentation Coverage Score ─────────────────────────────────────────────

@router.get("/coverage")
async def get_coverage():
    """
    Per-topic documentation coverage score (0-100).
    Confluence=40pts, SharePoint=30pts, GitHub files=20pts, Jira=10pts.
    """
    db = get_db()

    cursor = db.documents.find(
        {},
        {"source_type": 1, "tags": 1, "title": 1, "url": 1, "metadata": 1}
    )
    all_docs = await cursor.to_list(length=50000)

    SKIP_TAGS = {"jira", "confluence", "sharepoint", "github",
                 "commit", "pull_request", "page", "file", "document"}
    WEIGHTS   = {"confluence": 40, "sharepoint": 30, "github": 20, "jira": 10}

    tag_counts = defaultdict(lambda: defaultdict(int))

    for doc in all_docs:
        st = doc.get("source_type", "")
        m  = doc.get("metadata") or {}
        if st == "github" and m.get("content_type") == "commit":
            continue  # commits don't count as docs
        for tag in (doc.get("tags") or []):
            if tag in SKIP_TAGS or len(tag) < 3:
                continue
            tag_counts[tag][st] += 1

    coverage = []
    for tag, sources in tag_counts.items():
        if sum(sources.values()) < 2:
            continue
        raw_score = sum(
            min(sources.get(st, 0) / 5, 1.0) * w
            for st, w in WEIGHTS.items()
        )
        score = round(min(raw_score, 100))
        grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"
        missing = [st for st in ["confluence", "sharepoint", "github"] if sources.get(st, 0) == 0]

        coverage.append({
            "topic":           tag,
            "score":           score,
            "grade":           grade,
            "by_source":       dict(sources),
            "total_docs":      sum(sources.values()),
            "missing_sources": missing,
            "recommendation":  (
                f"Add Confluence docs for '{tag}'." if "confluence" in missing and sources.get("jira", 0) > 2
                else f"Add runbook to SharePoint." if "sharepoint" in missing and score >= 60
                else None
            ),
        })

    coverage.sort(key=lambda x: x["score"])
    avg = round(sum(c["score"] for c in coverage) / len(coverage)) if coverage else 0
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for c in coverage:
        grade_dist[c["grade"]] += 1

    return {
        "total_topics":       len(coverage),
        "average_score":      avg,
        "grade_distribution": grade_dist,
        "coverage":           coverage[:50],
    }


# ── Knowledge Velocity ────────────────────────────────────────────────────────

@router.get("/velocity")
async def get_velocity(topic: str = Query(None)):
    """
    Knowledge activity over the last 12 months, per source.
    If topic given — scoped to that topic. Otherwise org-wide.
    Returns monthly buckets suitable for a line/bar chart.
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    # Build 12 month buckets
    months = []
    for i in range(11, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year - ((now.month - i - 1) // 12 if (now.month - i - 1) < 0 else (i >= now.month and 1 or 0))
        # simpler approach
        pass

    # Use date arithmetic properly
    from dateutil.relativedelta import relativedelta
    buckets = {}
    for i in range(11, -1, -1):
        dt    = now - relativedelta(months=i)
        label = dt.strftime("%b %Y")
        buckets[label] = {"confluence": 0, "jira": 0, "github": 0, "sharepoint": 0, "label": label}

    # Query filter
    since = now - relativedelta(months=12)
    filt  = {"$or": [
        {"updated_at":  {"$gte": since}},
        {"ingested_at": {"$gte": since}},
    ]}
    if topic:
        filt["tags"] = {"$regex": re.escape(topic), "$options": "i"}

    cursor = db.documents.find(filt, {"source_type": 1, "updated_at": 1, "ingested_at": 1})
    docs   = await cursor.to_list(length=50000)

    for doc in docs:
        dt = doc.get("updated_at") or doc.get("ingested_at")
        if not dt:
            continue
        if isinstance(dt, str):
            try: dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except: continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        label = dt.strftime("%b %Y")
        if label in buckets:
            st = doc.get("source_type", "")
            if st in buckets[label]:
                buckets[label][st] += 1

    series = list(buckets.values())

    # Compute trend — compare last 3 months vs previous 3
    recent   = sum(sum(s[src] for src in ["confluence","jira","github","sharepoint"]) for s in series[-3:])
    previous = sum(sum(s[src] for src in ["confluence","jira","github","sharepoint"]) for s in series[-6:-3])
    trend    = "up" if recent > previous else "down" if recent < previous else "flat"
    trend_pct = round((recent - previous) / max(previous, 1) * 100)

    return {
        "topic":     topic or "all",
        "series":    series,
        "trend":     trend,
        "trend_pct": trend_pct,
        "recent_3m": recent,
        "prev_3m":   previous,
    }


# ── Handover Tracker ──────────────────────────────────────────────────────────

@router.get("/handover/{name:path}")
async def get_handover(name: str):
    """
    Generate a handover pack for a person.
    Returns all systems they own, open tickets, key docs, contacts — structured as a checklist.
    """
    db = get_db()

    name_regex = {"$regex": re.escape(name), "$options": "i"}
    cursor = db.documents.find(
        {"$or": [
            {"author":            name_regex},
            {"metadata.assignee": name_regex},
            {"metadata.reporter": name_regex},
            {"metadata.author_name": name_regex},
        ]},
        {"source_type": 1, "title": 1, "url": 1, "tags": 1,
         "metadata": 1, "updated_at": 1, "author": 1, "content": 1}
    ).limit(500)
    docs = await cursor.to_list(length=500)

    if not docs:
        return {"name": name, "total_docs": 0, "sections": []}

    SKIP_TAGS = {"jira", "confluence", "sharepoint", "github",
                 "commit", "pull_request", "page", "file", "document"}

    # Group by source
    by_source: dict[str, list] = {"confluence": [], "jira": [], "github": [], "sharepoint": []}
    topic_set: set[str] = set()

    for doc in docs:
        st = doc.get("source_type", "")
        if st not in by_source:
            continue
        m = doc.get("metadata") or {}
        for tag in (doc.get("tags") or []):
            if tag not in SKIP_TAGS and len(tag) >= 3:
                topic_set.add(tag)
        by_source[st].append({
            "title":      doc.get("title", ""),
            "url":        doc.get("url", ""),
            "updated_at": doc.get("updated_at").isoformat()
                if isinstance(doc.get("updated_at"), datetime) else "",
            "status":     m.get("status", ""),
            "priority":   m.get("priority", ""),
            "tags":       [t for t in (doc.get("tags") or []) if t not in SKIP_TAGS][:4],
        })

    # Open Jira tickets specifically
    open_tickets = [
        d for d in by_source["jira"]
        if d.get("status", "").lower() not in ("done", "resolved", "closed", "cancelled")
    ]

    # Build checklist sections
    sections = []

    if by_source["confluence"]:
        sections.append({
            "id":    "documentation",
            "title": "📖 Documentation to Transfer",
            "desc":  "Confluence pages this person owns — assign a new owner for each",
            "items": [{"doc": d, "checked": False} for d in by_source["confluence"][:20]],
        })

    if open_tickets:
        sections.append({
            "id":    "open_tickets",
            "title": "🎫 Open Jira Tickets",
            "desc":  "Tickets currently assigned — reassign or close before handover",
            "items": [{"doc": d, "checked": False} for d in open_tickets[:20]],
        })

    if by_source["github"]:
        sections.append({
            "id":    "code",
            "title": "💻 Code Contributions",
            "desc":  "GitHub commits and PRs — identify critical areas needing new owner",
            "items": [{"doc": d, "checked": False} for d in by_source["github"][:10]],
        })

    if by_source["sharepoint"]:
        sections.append({
            "id":    "process_docs",
            "title": "📋 Process Documents",
            "desc":  "SharePoint files — review and reassign ownership",
            "items": [{"doc": d, "checked": False} for d in by_source["sharepoint"][:10]],
        })

    # Knowledge topics summary
    top_topics = sorted(topic_set)[:10]

    return {
        "name":         name,
        "type":         _classify(name),
        "total_docs":   len(docs),
        "open_tickets": len(open_tickets),
        "top_topics":   top_topics,
        "sections":     sections,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/handover/{name:path}/progress")
async def save_handover_progress(name: str, body: dict):
    """Save handover checklist progress to MongoDB."""
    db = get_db()
    await db.handover_progress.update_one(
        {"name": name},
        {"$set": {
            "name":       name,
            "progress":   body.get("progress", {}),
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )
    return {"status": "saved"}


@router.get("/handover/{name:path}/progress")
async def get_handover_progress(name: str):
    """Get saved handover checklist progress."""
    db  = get_db()
    doc = await db.handover_progress.find_one({"name": name})
    return {"progress": doc.get("progress", {}) if doc else {}}
