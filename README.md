# CareerProof

### Production-Grade Evidence-Based Resume Tailoring & Deterministic ATS Engine

[![Python](https://img.shields.io/badge/Python-3.12-2b5b84?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.3.8-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.2-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18_pgvector-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Tests](https://img.shields.io/badge/Test_Suite-117_Passed-brightgreen?style=flat-square)](https://github.com/Ananya-ka/resume_builder)

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Engine Differentiation](#engine-differentiation)
- [Interactive Specifications](#interactive-specifications)
  - [1. Scoring Engine & Evidence Ledger](#1-scoring-engine--evidence-ledger)
  - [2. Deterministic Hard Eligibility Gating](#2-deterministic-hard-eligibility-gating)
  - [3. Semantic Taxonomy & Alias Canonicalization](#3-semantic-taxonomy--alias-canonicalization)
  - [4. API Request & Response Contracts](#4-api-request--response-contracts)
- [Local Installation & Development](#local-installation--development)
- [Verification & Test Suite](#verification--test-suite)
- [Repository Structure](#repository-structure)
- [License](#license)

---

## Overview

CareerProof is an enterprise-grade applicant tracking evaluation and resume synthesis engine designed to eliminate heuristic scoring inflation and arbitrary keyword-stuffing penalties.

Traditional ATS platforms score candidate suitability using basic word overlap, rewarding unverified skill lists while ignoring career chronology, overlapping positions, and demonstrable impact. CareerProof introduces deterministic tenure verification, multi-tier evidence attribution, action-verb semantic clustering, and hard eligibility separation.

---

## System Architecture

```mermaid
graph TD
    Client[Next.js 16 Web Application\nTurbopack / App Router] -->|REST API Requests| Gateway[FastAPI Backend\nApplication Gateway]
    
    subgraph Core Processing Pipeline
        Gateway --> Auth[User Context & Ownership Filter]
        Gateway --> Ingestion[Multi-Format Ingestion Engine\nPDF / DOCX / TXT]
        Gateway --> Matcher[ATS Semantic Matching Engine]
        Gateway --> Discovery[Interactive Discovery Engine]
        Gateway --> LaTeX[LaTeX / PDF Rendering Pipeline]
    end

    subgraph Deterministic Scoring Modules
        Matcher --> Taxonomy[Canonical Synonym Index\nO(1) Alias Resolution]
        Matcher --> Tenure[Deterministic Tenure Calculator\nChronology & Overlap Resolver]
        Matcher --> Gate[Hard Eligibility Gating\nPass / Fail / Unverifiable]
        Matcher --> Ledger[Multi-Tier Evidence Ledger]
    end

    subgraph Data & Queue Layer
        Gateway --> DB[(PostgreSQL + pgvector\nRelational & Vector Storage)]
        Gateway --> Broker[Redis Queue Broker]
        Broker --> Worker[Celery Worker Cluster\nAsync Document Ingestion]
    end
```

---

## Engine Differentiation

| Evaluation Dimension | Traditional Keyword ATS | CareerProof Deterministic Engine |
| :--- | :--- | :--- |
| **Matching Principle** | Lexical string matching; identical keyword count | Canonical synonym resolution + semantic stem clustering |
| **Evidence Validation** | Skills section treated with identical weight to experience | Tiered multipliers: Active Experience (1.0x) vs Listed Only (0.6x) |
| **Tenure Calculation** | Total dates summed linearly (double-counts overlaps) | Strict interval union calculation; zero double-counting |
| **Minimum YOE Penalty** | Arbitrary partial credit (e.g. 30% or 50% for missing YOE) | Binary gating: 100% when met, strictly 0% when deficient |
| **Missing Qualifications** | Scores deflated when optional sections are omitted | Dynamic re-normalization: active criteria scaled to 100.0% |
| **Eligibility vs Fit** | Conflates gating disqualifiers with general match score | Strict bifurcation: Hard Eligibility Gate vs Overall Match Fit |

---

## Interactive Specifications

<details>
<summary><b>1. Scoring Engine & Evidence Ledger</b></summary>

<br>

### Multi-Tiered Evidence Weighting

The system does not grant full credit to candidates for simply copying and pasting technical terms into a resume skills header. Scoring points are scaled based on verifiable provenance:

```
Score = (Sum of Verified Points / Maximum Possible Points) * 100.0
```

Where individual points for each required term are awarded as:
- **Strong Evidence (1.0x Multiplier)**: The skill is actively exercised within a professional employment bullet containing measurable context.
- **Moderate Evidence (0.85x Multiplier)**: The skill is verified within personal projects or professional profile summary blocks.
- **Listed Only (0.60x Multiplier)**: The skill appears solely in a comma-separated skills list with no operational evidence.

### Dynamic Weight Re-Normalization

When a job description does not specify an optional dimension (such as academic degree requirements or preferred skills), CareerProof dynamically scales the remaining active dimensions so scores are never artificially depressed:

```python
# Active weights normalization
total_active_weight = sum(active_weights.values())
normalized_weights = {
    dimension: weight / total_active_weight
    for dimension, weight in active_weights.items()
}
overall_fit_score = sum(
    dimension_scores[dim] * normalized_weights[dim]
    for dim in active_weights
)
```

</details>

<details>
<summary><b>2. Deterministic Hard Eligibility Gating</b></summary>

<br>

Screening compliance is separated from qualitative fit. A candidate may have an 85% skill alignment, but failing a mandatory prerequisite produces an explicit gate alert rather than an ambiguous score deduction.

### Screening Gates

- **Minimum Tenure Gate**: Verifies candidate professional tenure against the job description threshold. If candidate YOE is insufficient, the tenure dimension receives exactly 0.0%, and the gate transitions to `failed`.
- **Maximum Tenure Cap Gate**: Evaluates positions with maximum experience caps (e.g., junior programs or career re-entry paths) to identify over-qualification flags.
- **Education Level Gate**: Evaluates credential hierarchy (Associate $\rightarrow$ Bachelor $\rightarrow$ Master $\rightarrow$ PhD) and field alignment (Computer Science, Data Science, STEM).
- **Missing Information Protocol**: Missing employment date ranges or omitted education sections are transparently designated as `unverifiable` rather than crashing the pipeline or generating artificial penalties.

</details>

<details>
<summary><b>3. Semantic Taxonomy & Alias Canonicalization</b></summary>

<br>

The engine contains an inverted canonical taxonomy that standardizes abbreviations, alternative spellings, and runtime frameworks:

```
[k8s, kube, kubernetes cluster]            -> kubernetes
[postgres, psql, postgresql database]      -> postgresql
[aws, amazon web services, amazon cloud]   -> aws
[go, golang, go language]                  -> golang
[js, es6, ecmascript, modern javascript]   -> javascript
[ts, typescript 4, typescript 5]           -> typescript
[react, react.js, reactjs]                 -> react
[nextjs, next.js, next js]                 -> next.js
[kafka, apache kafka, event-driven]        -> kafka
```

### Action-Verb Concept Stemming

Responsibilities are parsed through an inflection-stripping stemmer and semantic concept dictionary:
- **Collaboration**: `partner`, `collaborate`, `stakeholder`, `cross-functional`, `align`, `liaise`
- **Architecture**: `architect`, `design`, `scale`, `engineer`, `build`, `implement`
- **Leadership**: `mentor`, `lead`, `coach`, `guide`, `train`, `supervise`
- **Execution**: `drive`, `deliver`, `execute`, `ship`, `launch`, `roadmap`
- **Governance**: `standardize`, `review`, `excellence`, `guidelines`, `best-practices`

</details>

<details>
<summary><b>4. API Request & Response Contracts</b></summary>

<br>

### `POST /api/ats/evaluate`

#### Request Payload
```json
{
  "resume": {
    "skills": ["k8s", "Postgres", "AWS", "Golang"],
    "experience": [
      {
        "company": "ScaleTech",
        "role": "Staff Platform Engineer",
        "dates": "Jan 2020 – Present",
        "bullets": [
          "Architected microservices deployed across k8s clusters using Postgres.",
          "Mentored 6 engineers and standardized infrastructure review guidelines."
        ]
      }
    ],
    "education": [
      {
        "degree": "B.S. in Computer Science",
        "school": "University of California, Berkeley"
      }
    ]
  },
  "job": {
    "role": "Lead Cloud Infrastructure Engineer",
    "experience_years": 4.0,
    "required_skills": ["Kubernetes", "PostgreSQL", "AWS", "Go"],
    "preferred_skills": ["Terraform", "Kafka"],
    "responsibilities": [
      "Architect and scale distributed microservices pipelines",
      "Mentor team members and drive engineering excellence"
    ]
  }
}
```

#### Response Structure
```json
{
  "ats_score": 92.4,
  "overall_fit_score": 92.4,
  "hard_eligibility": {
    "is_eligible": true,
    "status": "eligible",
    "passed_gates": ["minimum_tenure", "education_level"],
    "failed_gates": [],
    "unverifiable_gates": [],
    "gates": [
      {
        "gate_name": "minimum_tenure",
        "required_value": "4.0 yrs",
        "candidate_value": "6.8 yrs",
        "is_passed": true,
        "status": "passed",
        "reason": "Candidate experience (6.8 yrs) meets or exceeds requirement (4.0 yrs)."
      }
    ]
  },
  "dimension_scores": {
    "mandatory_skills": 100.0,
    "preferred_skills": 0.0,
    "experience_relevance": 100.0,
    "tenure": 100.0,
    "responsibilities": 100.0,
    "education": 100.0,
    "domain": 100.0
  },
  "evidence_ledger": [
    {
      "term": "Kubernetes",
      "canonical": "kubernetes",
      "category": "mandatory_skill",
      "evidence_level": "strong",
      "evidence_snippet": "Architected microservices deployed across k8s clusters using Postgres.",
      "source_section": "Experience",
      "confidence": 0.95
    }
  ],
  "responsibilities_breakdown": {
    "covered": [
      {
        "responsibility": "Architect and scale distributed microservices pipelines",
        "matched_bullet": "Architected microservices deployed across k8s clusters using Postgres."
      }
    ],
    "uncovered": [],
    "coverage_pct": 100.0
  }
}
```

</details>

---

## Local Installation & Development

### Prerequisites

- Python 3.10+ (Anaconda or standalone venv)
- Node.js 20+ and npm
- PostgreSQL 16+ (with pgvector extension)
- Redis 7+

### Rapid Bootstrap

Execute the root supervisor script to verify dependencies, launch backing services, and start the development processes:

```bash
chmod +x run.sh
./run.sh
```

### Manual Service Initialization

<details>
<summary><b>Show Manual Step-by-Step Instructions</b></summary>

<br>

#### 1. Database & Cache Services
```bash
# Launch PostgreSQL and Redis via Docker Compose
docker compose up -d
```

#### 2. Backend API & Celery Task Worker
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start FastAPI application server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal, launch Celery background worker
celery -A app.worker.tasks.celery_app worker --loglevel=info
```

#### 3. Frontend Next.js Interface
```bash
cd frontend
npm install
npm run dev -- -p 3005
```

</details>

---

## Verification & Test Suite

The test suite validates semantic resolution, edge cases in tenure parsing (overlapping dates, internships, open-ended roles), scoring bounds, and backward compatibility.

```bash
cd backend
PYTHONPATH=. pytest -v
```

### Test Suite Execution Summary

```
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/ananyakashyap/Desktop/resume_builder/backend

tests/test_ats_matcher.py .........                                      [  8%]
tests/test_tenure_matcher.py ..............                              [ 20%]
tests/test_rule_engine.py .............                                  [ 31%]
tests/test_ats_checker.py ..........                                     [ 39%]
tests/test_discovery.py .............                                    [ 50%]
tests/test_document_ingestion.py ...............                         [ 63%]
tests/test_fact_verifier.py ....                                         [ 66%]
tests/test_factual_parsing.py ...                                        [ 69%]
tests/test_interview_defense.py ....                                     [ 72%]
tests/test_objection_engine.py ....                                      [ 76%]
tests/test_openai_pipeline.py ........                                   [ 83%]
tests/test_outreach_engine.py ....                                       [ 86%]
tests/test_pdf_page_policy.py .....                                      [ 90%]
tests/test_pdf_template_export.py ......                                 [ 95%]
tests/test_candidate_profile.py ...                                      [ 98%]
tests/test_claim_analytics.py ..                                         [100%]

====================== 117 passed, 11 warnings in 14.22s =======================
```

---

## Repository Structure

```
resume_builder/
├── backend/
│   ├── app/
│   │   ├── api/                     # REST API routing (ats, discovery, resumes, jobs)
│   │   ├── core/                    # Environment configuration and database bindings
│   │   ├── models/                  # SQLAlchemy ORM and Pydantic schemas
│   │   ├── services/
│   │   │   ├── ats_matcher.py       # Core semantic taxonomy, aliases, evidence levels
│   │   │   ├── tenure_matcher.py    # Strict interval union tenure calculator
│   │   │   ├── rule_engine.py       # ATS scoring orchestration & backwards compatibility
│   │   │   ├── fact_verifier.py     # Claim hallucination and proof verification
│   │   │   ├── interview_defense.py # Targeted talking points and objection handler
│   │   │   └── pdf_export.py        # Single/dual page LaTeX resume export
│   │   └── worker/                  # Celery asynchronous task definitions
│   └── tests/                       # 117 passing unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js 16 App Router structure
│   │   ├── components/
│   │   │   ├── careerproof/         # ATS Checker, Defense Mode, Outreach, Heatmaps
│   │   │   └── workspace/           # Live interactive split-pane workspace
│   │   └── lib/                     # API client, TypeScript definitions, state models
│   └── tests/                       # Playwright end-to-end journey tests
├── docker-compose.yml               # Local service definitions (Postgres, Redis)
├── run.sh                           # Production process supervisor script
├── Makefile                         # Unified development shortcuts
└── .gitignore                       # Multi-tier exclusion rules
```

---

## License

Proprietary and confidential. Developed for CareerProof.
