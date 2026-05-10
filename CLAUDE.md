# Claude Routine — Medical AI Paper Digest

## Overview
Daily morning routine that searches PubMed for the latest medical AI papers and outputs concise Korean summaries via Claude.

## Script: `medical_ai_papers.py`

### Usage
```bash
# Default: last 48 hours, up to 7 papers, with Claude summaries
python medical_ai_papers.py

# Custom search window
python medical_ai_papers.py --hours 24

# Skip Claude summarization (faster, no summaries)
python medical_ai_papers.py --no-summarize

# Show up to 10 papers
python medical_ai_papers.py --max 10
```

### Requirements
- Python 3.10+
- Internet access (PubMed E-utilities API — free, no key needed)
- `claude` CLI installed and authenticated (for Korean summaries)

### Target Journals
| Journal | Tier |
|---|---|
| Nature Medicine | Top |
| NEJM AI | Top |
| The Lancet Digital Health | High |
| npj Digital Medicine | High |
| JAMA / JAMA Network Open | High |
| Radiology / Radiology: AI | High |
| JAMIA | Mid |

### Scheduling (cron example)
```cron
# Every morning at 8 AM KST (23:00 UTC previous day)
0 23 * * * /usr/bin/python3 /path/to/medical_ai_papers.py >> /var/log/med_ai_digest.log 2>&1
```

## Architecture
- **Data source**: PubMed Entrez E-utilities (esearch → esummary → efetch)
- **Ranking**: Heuristic journal-IF score + publication type bonus
- **Summarization**: Claude Haiku via `claude -p` CLI for fast, cheap Korean summaries
