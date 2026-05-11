#!/usr/bin/env python3
"""
Daily Medical AI Paper Search Routine
Searches for recent AI/ML papers from top medical journals and outputs Korean summaries.

Target journals:
  - Nature Medicine
  - npj Digital Medicine
  - The Lancet Digital Health
  - NEJM AI
  - JAMA / JAMA Network Open
  - Radiology / Radiology: AI
  - JAMIA

Usage:
  python medical_ai_papers.py              # print today's digest
  python medical_ai_papers.py --hours 48  # search last 48 hours (default)
  python medical_ai_papers.py --max 7     # max papers to show (default 7)
"""

import argparse
import json
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import urllib.request


JOURNALS = {
    "Nature Medicine": {
        "pubmed_journal": "Nature medicine[Journal]",
        "issn": "1546-170X",
    },
    "npj Digital Medicine": {
        "pubmed_journal": "npj digital medicine[Journal]",
        "issn": "2398-6352",
    },
    "The Lancet Digital Health": {
        "pubmed_journal": "Lancet Digit Health[Journal]",
        "issn": "2589-7500",
    },
    "NEJM AI": {
        "pubmed_journal": "NEJM AI[Journal]",
        "issn": "2836-0818",
    },
    "JAMA": {
        "pubmed_journal": "JAMA[Journal] OR JAMA Netw Open[Journal]",
        "issn": "",
    },
    "Radiology / Radiology AI": {
        "pubmed_journal": "Radiology[Journal] OR Radiology Artif Intell[Journal]",
        "issn": "",
    },
    "JAMIA": {
        "pubmed_journal": "J Am Med Inform Assoc[Journal]",
        "issn": "1527-974X",
    },
}

AI_TERMS = (
    "artificial intelligence[tiab] OR deep learning[tiab] OR machine learning[tiab] "
    "OR foundation model[tiab] OR large language model[tiab] OR neural network[tiab]"
)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_BASE = "https://pubmed.ncbi.nlm.nih.gov/"

HEADERS = {
    "User-Agent": "MedicalAIDigest/1.0 (medical research tool; contact: research@example.com)",
    "Accept": "application/json, text/plain, */*",
}


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def pubmed_search(query: str, days: int, retmax: int = 50) -> list[str]:
    min_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "pub_date",
        "mindate": min_date,
        "datetype": "edat",
    }
    url = f"{PUBMED_ESEARCH}?{urlencode(params)}"
    data = json.loads(_get(url))
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_summary(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    url = f"{PUBMED_ESUMMARY}?{urlencode(params)}"
    data = json.loads(_get(url))
    results = data.get("result", {})
    return [results[pmid] for pmid in pmids if pmid in results]


def fetch_abstract(pmid: str) -> str:
    params = {
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "text",
    }
    url = f"{PUBMED_EFETCH}?{urlencode(params)}"
    try:
        return _get(url).decode("utf-8", errors="replace")
    except Exception:
        return ""


def score_impact(article: dict) -> float:
    """Heuristic score: prefer high-IF journals and recent dates."""
    journal_scores = {
        "nature medicine": 10,
        "nejm ai": 9,
        "lancet digit health": 8,
        "npj digital medicine": 7,
        "jama": 7,
        "jama network open": 6,
        "radiology": 6,
        "radiology: artificial intelligence": 7,
        "j am med inform assoc": 5,
    }
    source = article.get("source", "").lower()
    score = next((v for k, v in journal_scores.items() if k in source), 3)

    # Boost for publication type
    pub_types = [p.get("value", "").lower() for p in article.get("pubtype", [])]
    if any("randomized" in pt for pt in pub_types):
        score += 2
    if any("multicenter" in pt for pt in pub_types):
        score += 1

    return score


def summarize_with_claude(title: str, abstract: str) -> list[str]:
    """Use the claude CLI to produce a 3-line Korean summary."""
    prompt = (
        "다음 의료 AI 논문의 핵심 내용을 한국어로 정확히 3줄로 요약해줘. "
        "각 줄은 핵심 포인트를 담고, 번호(1. 2. 3.) 없이 줄바꿈으로만 구분해줘.\n\n"
        f"제목: {title}\n\n초록: {abstract[:3000]}"
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if len(lines) >= 3:
            return lines[:3]
        # pad if shorter
        while len(lines) < 3:
            lines.append("(요약 불가)")
        return lines
    except Exception:
        return ["(요약 생성 실패)", "(Claude CLI를 확인하세요)", ""]


def format_paper(rank: int, article: dict, summary_lines: list[str]) -> str:
    title = article.get("title", "제목 없음").rstrip(".")
    source = article.get("source", "")
    pub_date = article.get("pubdate", "")
    pmid = article.get("uid", "")
    link = f"{PUBMED_BASE}{pmid}/" if pmid else "(링크 없음)"

    lines = [
        f"{'─'*60}",
        f"[{rank}] {title}",
        f"📰 {source}  |  {pub_date}",
        "",
        "📝 핵심 요약",
    ]
    for i, s in enumerate(summary_lines, 1):
        lines.append(f"  {i}. {s}")
    lines += ["", f"🔗 {link}"]
    return "\n".join(lines)


def run(hours: int = 48, max_papers: int = 7, no_summarize: bool = False):
    days = max(1, hours // 24 + (1 if hours % 24 else 0))
    now = datetime.now(timezone.utc)

    print(f"\n{'='*60}")
    print(f"  의료 AI 논문 데일리 다이제스트")
    print(f"  기준 시각: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  검색 범위: 최근 {hours}시간")
    print(f"{'='*60}\n")

    # Build combined PubMed query
    journal_filter = " OR ".join(
        f"({meta['pubmed_journal']})" for meta in JOURNALS.values()
    )
    full_query = f"({AI_TERMS}) AND ({journal_filter})"

    print(f"🔍 PubMed 검색 중...")
    pmids = pubmed_search(full_query, days=days, retmax=100)
    if not pmids:
        print("  → 최근 논문이 없습니다.")
        return

    print(f"  → {len(pmids)}편 발견. 영향도 순으로 정렬 중...\n")
    articles = pubmed_summary(pmids)
    articles.sort(key=score_impact, reverse=True)
    top = articles[:max_papers]

    for rank, article in enumerate(top, 1):
        pmid = article.get("uid", "")
        title = article.get("title", "")
        abstract = "" if no_summarize else fetch_abstract(pmid)
        summary = (
            ["(요약 생략)", "", ""]
            if no_summarize
            else summarize_with_claude(title, abstract)
        )
        print(format_paper(rank, article, summary))

    print(f"\n{'='*60}")
    print(f"  총 {len(top)}편 | 출처: PubMed E-utilities")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Daily Medical AI Paper Digest")
    parser.add_argument("--hours", type=int, default=48, help="Search window in hours (default: 48)")
    parser.add_argument("--max", type=int, default=7, dest="max_papers", help="Max papers to show (default: 7)")
    parser.add_argument("--no-summarize", action="store_true", help="Skip Claude summarization (faster)")
    args = parser.parse_args()
    run(hours=args.hours, max_papers=args.max_papers, no_summarize=args.no_summarize)


if __name__ == "__main__":
    main()
