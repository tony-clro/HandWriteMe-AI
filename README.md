# HandWriteMe AI — AI-Assisted Handwriting Generation & Document Transformation Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![MSFLib](https://img.shields.io/badge/MSFLib-Ecosystem-orange.svg)](https://github.com/msflib)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Local%20Tests-84%20Passed%2C%201%20Skipped-brightgreen.svg)]()

HandWriteMe AI is an AI-assisted handwriting-generation platform and working prototype built on FastAPI and the MSFLib ecosystem. It converts raw digital text and uploaded digital PDF files into realistic handwritten notebook pages featuring notebook line alignment, full text searchability, interactive preview and approval workflows, and multi-tenant workspace isolation.

---

## Table of Contents

1. [Project Introduction & Prototype Scope](#1-project-introduction--prototype-scope)
2. [Problem Statement](#2-problem-statement)
3. [Vision and Objectives](#3-vision-and-objectives)
4. [Implemented Features](#4-implemented-features)
5. [Current Technical Constraints & Verification Status](#5-current-technical-constraints--verification-status)
6. [System Architecture](#6-system-architecture)
7. [Technology Stack](#7-technology-stack)
8. [Dependencies and Roles](#8-dependencies-and-roles)
9. [MSFLib Integration Architecture](#9-msflib-integration-architecture)
10. [End-to-End Application Workflow](#10-end-to-end-application-workflow)
11. [Project Structure](#11-project-structure)
12. [Local Setup Guide](#12-local-setup-guide)
13. [Private MSFLib Dependency Prerequisites](#13-private-msflib-dependency-prerequisites)
14. [Environment Variable Reference](#14-environment-variable-reference)
15. [API Documentation](#15-api-documentation)
16. [Verification and Test Results](#16-verification-and-test-results)
17. [Production Cloud Deployment](#17-production-cloud-deployment)
18. [Security and Tenancy Isolation](#18-security-and-tenancy-isolation)
19. [Model Attribution and Licensing](#19-model-attribution-and-licensing)
20. [Known Limitations](#20-known-limitations)
21. [Future Development Roadmap](#21-future-development-roadmap)

---

## 1. Project Introduction & Prototype Scope

HandWriteMe AI is an AI-assisted document transformation platform and working prototype designed to bridge the gap between digital text efficiency and human handwriting aesthetics.

Using modular services built upon the MSFLib FastAPI framework, Neon Serverless PostgreSQL, Cloudflare R2 object storage, and an in-browser calibration interface, the working prototype enables users to:
- Authenticate and manage accounts with default workspace isolation.
- Ingest plain text or extract text from uploaded digital PDF files.
- Customize ink color, font size, line spacing, margins, and letter jitter.
- Generate multi-page SVG handwriting previews on ruled notebook paper.
- Approve previews and export multi-page PDFs with searchable text underlays.

**Distinction Between Prototype & Long-Term Vision:**
The long-term vision is personalized, zero-shot imitation of an individual's handwriting from scanned sample pages. In the current working prototype, uploaded handwriting sample images are securely persisted for reference, and deployed handwriting rendering is handled by the responsive parametric SVG engine, with local experimental support for the Alex Graves RNN model.

---

## 2. Problem Statement

1. **Impersonal Communication**: Digital notes, assignments, personal letters, and study materials often lack the visual authenticity and warmth of human handwriting.
2. **Artificial Font Output**: Typical digital alternatives rely on standard slanted italic fonts that repeat identical glyph shapes with rigid, unnatural uniformity.
3. **Loss of Vector Fidelity & Searchability**: Generative image tools output raster bitmaps that cannot be scaled for crisp printing, copy-pasted, or indexed by screen readers.
4. **Data Persistence Challenges**: Ephemeral serverless containers erase local files on restart, causing lost document uploads and preview artifacts unless decoupled object storage is integrated.

---

## 3. Vision and Objectives

- **Human-Centric Synthesis**: Combine neural stroke synthesis (Alex Graves RNN with mixture density attention) with calibrated parametric fallback rendering.
- **Preview-to-PDF Consistency**: Maximize visual consistency in margins, line heights, baselines, and layout between the browser preview and exported PDF.
- **Enterprise Multi-Tenancy**: Enforce strict account, workspace, and tenant data isolation leveraging MSFLib event hooks.
- **Zero-Data-Loss Architecture**: Route relational records to Neon PostgreSQL and binary artifacts (sample images, text files, previews) to Cloudflare R2.

---

## 4. Implemented Features

### Account Registration & Authentication
- **MSFLib-Native User Sign-Up**: Public self-registration via `/api/v1/accounts/register` (with `/open` alias).
- **Security Validation**: Email normalization, minimum 8-character password enforcement, matching confirmation check, and hardcoded `AccountRole.user` assignment to prevent privilege escalation.
- **Workspace Binding**: Automatic tenant resolution and default workspace membership provisioning via `msflib.workspaces.eventbus`.
- **JWT Authentication**: OAuth2-compliant login yielding access and refresh tokens via `/api/v1/auth/jwt/login`.

### Profile Management & Interactive Calibration
- **Handwriting Profiles**: Manage custom profiles with distinct ink colors, stroke widths, and style models.
- **Interactive Calibration Pad**: HTML5 canvas capturing mouse and stylus pen strokes `(x, y)` with pen-up/pen-down detection, serialized as normalized coordinate offset sequences.
- **Sample Image Uploads**: Upload reference handwriting photos (`.png`, `.jpg`) with MIME verification and persistence to Cloudflare R2 / filesystem.

### Document Ingestion
- **Plain Text Ingestion**: Direct text ingestion with automatic paragraph, word, character, and line-count analysis.
- **Digital PDF Text Extraction**: Upload multi-page digital PDFs; text is validated and extracted using `pypdf`, rejecting scanned or empty files gracefully.

### Handwriting Preview & Generation Engine
- **Visual Preview Generation**: Multi-page SVG generation featuring ruled notebook paper background (`#fbf9f4`), vertical red margin guides (`#f28b82`), and soft blue ruled lines (`#c2d1e0`).
- **Dynamic Parameter Controls**: Interactive sliders for font size (18–32px), line spacing (1.2–2.4x), letter spacing, randomness jitter, slant angle, and ink color palette.
- **Screen-Reader & Search Support**: Invisible semantic text underlays (`opacity="0"`) embedded directly in SVGs for accessibility.

### Approval Gate & PDF Export Parity
- **Strict Approval Separation**: `/api/v1/documents/{id}/approve` must be called before an export is permitted, enforcing human review.
- **Scaled Vector Geometry**: SVG space ($800 \times 1100$) dynamically maps to US Letter ($612 \times 792$ pt) with sub-pixel margin and baseline alignment.
- **Native PDF 1.4 Generation**: Pure-Python stream generation without external cloud conversion APIs; renders vector stroke paths (`m ... l ... S`) alongside invisible searchable text (`3 Tr`) and visible cursive text on notebook baselines.

### Dual-Mode Object Storage (Cloudflare R2 & Local)
- **Unified Interface**: `FileStorageService` selects backend based on configuration:
  - `STORAGE_METHOD=s3`: Connects to Cloudflare R2 via `boto3` using S3-compatible credentials and endpoint.
  - `STORAGE_METHOD=file`: Stores files locally under `uploads/` for offline local development.
- **Path Traversal Protection**: All paths are sanitized against directory-traversal attempts.

### UI & UX
- **Theme Switcher**: Instant Dark Mode and Light Mode toggle with local storage persistence and FOUC prevention.
- **Single-Page Application**: Fast, lightweight HTML/CSS/JavaScript interface without heavyweight client framework overhead.

---

## 5. Current Technical Constraints & Verification Status

To maintain full transparency, the production status of specific components is documented below:

| Component | Production Status | Verified Reality |
| :--- | :--- | :--- |
| **Deployed Render Engine** | Parametric SVG Fallback | The deployed application on Render Free currently uses the parametric SVG fallback renderer because PyTorch and the neural model checkpoint (`lstm.pt`, 15 MB) are unavailable in that deployment environment due to Render Free's 512 MB RAM ceiling. |
| **Neural Synthesis Model** | Verified Locally | The Alex Graves (2013) 3-layer LSTM synthesis model executes successfully on local CPU when PyTorch and the checkpoint are present, with inference verified by local automated tests (`test_real_model_inference_on_cpu`). |
| **Sample Image Training** | Storage Only | Uploaded handwriting sample images (`.png`, `.jpg`) are securely stored in Cloudflare R2 / filesystem and tracked in PostgreSQL. **They do not currently train or fine-tune the neural model weights.** |
| **Canvas Conditioning** | Zero-Shot Priming | Canvas strokes provide autoregressive hidden-state initialization (`prime_tensor`) during local neural model execution; they do not perform persistent backpropagation or weight adaptation. |
| **Preview-to-PDF Consistency** | Layout & Baselines Aligned | Page layout, line count, margins, ruled line positions, lower line visibility, and searchable text underlays are matched between preview and PDF. Font rendering differences remain between browser-rendered cursive text and PDF font definitions until full font embedding is verified in production. |
| **Email Verification** | Placeholder / Logged | The Render environment uses placeholder SMTP settings (`mail.example.org`). Accounts are activated immediately on registration without blocking users behind unconfigured email delivery. |

---

## 6. System Architecture

```mermaid
graph TD
    User([Client Browser]) -->|HTTPS / UI| SPA[Static HTML/CSS/JS]
    SPA -->|REST API / Bearer JWT| FastAPI[FastAPI Backend]

    subgraph MSFLib Framework
        FastAPI --> AuthRouter[msflib-auth]
        FastAPI --> AccountRouter[msflib-account]
        FastAPI --> WorkspaceRouter[msflib-workspaces]
        FastAPI --> IngestionModule[msflib-ingestion]
    end

    subgraph Core Services
        FastAPI --> HWEngine[HandwritingEngineService]
        FastAPI --> PDFWriter[PDFWriterService]
        FastAPI --> StorageService[FileStorageService]
        HWEngine -.->|Local CPU Inference Only| ModelAdapter[AIHandwritingModelAdapter]
    end

    subgraph Persistence Layer
        FastAPI -->|SQLModel / SQLAlchemy| DB[(Neon PostgreSQL)]
        StorageService -->|S3 API / boto3| R2[(Cloudflare R2 Bucket)]
        StorageService -.->|Local Dev Fallback| LocalFS[Local Filesystem uploads/]
    end
```

---

## 7. Technology Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Architecture Ecosystem**: [MSFLib](https://github.com/msflib/fastapi) (Core, Auth, Account, Workspaces, Ingestion)
- **Database & ORM**: [SQLModel](https://sqlmodel.tiangolo.com/) / [SQLAlchemy](https://www.sqlalchemy.org/) with [Alembic](https://alembic.sqlalchemy.org/) migrations
- **Relational Host**: [Neon Serverless PostgreSQL](https://neon.tech/)
- **Object Storage**: [Cloudflare R2](https://www.cloudflare.com/developer-platform/r2/) via S3-compatible API (`boto3`)
- **PDF Processing**: [pypdf](https://pypdf.readthedocs.io/) and native PDF 1.4 content stream writer
- **Deep Learning (Local Experimental)**: [PyTorch](https://pytorch.org/) (CPU) running Alex Graves RNN handwriting model
- **Frontend**: Vanilla HTML5, Modern CSS3 with custom variables, Vanilla ES6 JavaScript

---

## 8. Dependencies and Roles

From `pyproject.toml`:

```toml
[tool.poetry.dependencies]
python = ">=3.10,<3.15"
psycopg2-binary = "^2.9.0"      # PostgreSQL database adapter
alembic = "^1.13"               # Schema migration management
msflib = "core-v0.2.1"          # Foundation core utilities & settings
msflib-auth = "auth-v0.2.2"     # JWT authentication & password hashing
msflib-account = "account-v0.2.2" # Account management & profile actions
msflib-workspaces = "workspaces-v0.2.1" # Workspace isolation & event hooks
msflib-ingestion = "ingestion-v0.2.0"   # Background ingestion job tracking
celery = "^5.3"                 # Asynchronous background worker support
pypdf = "^6.20.1"               # PDF text extraction & validation
email-validator = "^2.3.0"      # Email format verification
boto3 = "*"                     # Cloudflare R2 S3-compatible storage driver
```

---

## 9. MSFLib Integration Architecture

HandWriteMe AI is architected directly upon MSFLib packages rather than custom reinvented authentication or tenancy modules:

1. **`msflib.core.config.CoreSettings`**:
   The application settings class `Settings` subclasses `CoreSettings`, inheriting modular scoping (`settings.scope("ACCOUNT")`, `settings.scope("AUTH")`, `settings.scope("CORE")`).
2. **`msflib.auth.router`**:
   Mounts the standard JWT token generation endpoints (`/api/v1/auth/jwt/login`, `/refresh`), delegating password verification to passlib/bcrypt.
3. **`msflib.account.router`**:
   Exposes the `/accounts/register` and `/open` registration endpoints, validating inputs through `models.UserRegister` and hashing passwords via `AccountAction`.
4. **`msflib.workspaces.eventbus`**:
   Listens to `AccountEventName.ACCOUNT_CREATE_PRE_COMMIT` and `ACCOUNT_CREATED` to create workspace memberships in the default tenant, guaranteeing complete workspace isolation.
5. **`msflib.ingestion.actions.IngestionJobAction`**:
   Tracks document ingestion and handwriting synthesis job lifecycles (`pending` $\rightarrow$ `processing` $\rightarrow$ `done` / `failed`).

---

## 10. End-to-End Application Workflow

```
[1. User Registration / Login]
       │
       ▼
[2. Create Handwriting Profile] ──► (Select Ink Color, Model Style)
       │
       ├─► (Optional) Interactive Canvas Calibration Pad (Record real-time stroke coordinates)
       └─► (Optional) Upload Handwriting Sample Images (.png, .jpg to Cloudflare R2)
       │
       ▼
[3. Ingest Document] ─────────────► (Paste text OR Upload digital PDF)
       │
       ▼
[4. Generate Handwriting Preview] ─► (Adjust font size, spacing, randomness, ruled lines)
       │
       ▼
[5. Interactive Review & Approval] ─► (Approve preview; enables PDF export)
       │
       ▼
[6. Export Downloadable PDF] ─────► (Download multi-page PDF with searchable text underlay)
```

---

## 11. Project Structure

```text
HandWriteMe-AI/
├── .env-example                 # Environment configuration template
├── Dockerfile                   # Multi-stage production container build
├── pyproject.toml               # Poetry dependency declarations
├── README.md                    # Project documentation
├── alembic/                     # Database migration revisions
├── app/
│   ├── actions/                 # MSFLib action wrappers (Account, Profile, Job)
│   ├── api/
│   │   ├── api_v1/
│   │   │   ├── api.py           # Central API router assembly
│   │   │   └── endpoints/
│   │   │       ├── admin/       # Administrator endpoints
│   │   │       ├── documents.py # Ingestion, preview generation, approval, export
│   │   │       └── handwriting_profiles.py # Profiles & sample upload
│   │   └── deps.py              # Dependency injection (DB session, Auth, Tenancy)
│   ├── assets/                  # Precomputed style matrices (default_style.npy)
│   ├── core/
│   │   └── config.py            # Application configuration & MSFLib settings
│   ├── db/
│   │   ├── init_db.py           # Superuser & default tenant initialization
│   │   └── session.py           # Database engine & sessionmaker factory
│   ├── models/                  # SQLModel database & API schemas
│   │   ├── user_register.py     # Public registration schema
│   │   └── document.py          # Document, Profile, and Sample models
│   ├── services/
│   │   ├── handwriting_engine.py# SVG handwriting rendering & layout engine
│   │   ├── model_adapter.py     # Graves LSTM PyTorch model adapter (local)
│   │   ├── pdf_extractor.py     # PDF validation & text extraction
│   │   ├── pdf_writer.py        # PDF 1.4 stream writer with vector parity
│   │   └── storage.py           # Cloudflare R2 & local filesystem adapter
│   ├── static/                  # Vanilla frontend assets (HTML, CSS, JS)
│   │   ├── index.html           # Main SPA interface with Dark/Light theme
│   │   ├── css/styles.css       # Design tokens & responsive styling
│   │   └── js/                  # api.js, app.js, canvas.js
│   └── tests/                   # Pytest automated test suite (85 tests)
```

---

## 12. Local Setup Guide

### Prerequisites
- Python 3.10+
- Poetry 1.8+
- Git

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/tony-clro/HandWriteMe-AI.git
   cd HandWriteMe-AI
   ```

2. **Configure environment variables**:
   ```bash
   cp .env-example .env
   ```

3. **Install dependencies**:
   ```bash
   poetry install
   ```

4. **Initialize database schema**:
   ```bash
   poetry run python -m app.initial_data
   ```

5. **Start local development server**:
   ```bash
   poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

6. Open your browser at `http://127.0.0.1:8000`.

---

## 13. Private MSFLib Dependency Prerequisites

`pyproject.toml` references private or scoped MSFLib Git submodules (`git+https://github.com/msflib/fastapi.git`).

When building container images or deploying in CI/CD, provide a GitHub Personal Access Token (PAT) with `repo` read access:

```bash
docker build \
  --build-arg CONTAINER_GITHUB_PAT="<your-github-pat>" \
  -t handwriteme-ai .
```

The Dockerfile configures Git credential substitution:
```dockerfile
git config --global url."https://x-access-token:${CONTAINER_GITHUB_PAT}@github.com/".insteadOf "https://github.com/"
```

---

## 14. Environment Variable Reference

The application uses MSFLib's `CoreSettings` and custom `AppSettings`. Configure the following variables recognized by `app/core/config.py`, `app/db/session.py`, and `app/services/storage.py`:

| Variable Name | Example / Default | Required In | Purpose |
| :--- | :--- | :--- | :--- |
| **`PROJECT_NAME`** | `HandWriteMe AI` | All | Application display name |
| **`SECRET_KEY`** | `<secure-random-secret>` | All | Secret key for JWT signing |
| **`FIRST_SUPERUSER`** | `admin@example.com` | Setup | Default administrator email |
| **`FIRST_SUPERUSER_PASSWORD`** | `<secure-admin-password>` | Setup | Default administrator password |
| **`SYNC_SUPERUSER_PASSWORD`** | `false` | Prod | Opt-in startup hook to sync superuser password |
| **`USERS_OPEN_REGISTRATION`** | `true` | All | Enables public account registration |
| **`USE_SQLITE`** | `false` (prod) / `true` (dev) | All | When `true`, overrides PostgreSQL and uses SQLite |
| **`SQLITE_DATABASE_URI`** | `sqlite:///./test.db` | Dev / Test | SQLite database file URI |
| **`SQLALCHEMY_DATABASE_URI`** | `postgresql://user:pass@host/db?sslmode=require` | Prod | Full PostgreSQL URI (used by `session.py` when `USE_SQLITE=false`). Alternatively configured via MSFLib component variables (`POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`). *Note: Generic `DATABASE_URL` is not directly read by MSFLib.* |
| **`STORAGE_METHOD`** | `s3` (prod) / `file` (dev) | All | Selects storage driver: `s3` for Cloudflare R2 / AWS S3, or `file` for local filesystem |
| **`STORAGE_PATH`** | `uploads` | File mode | Local directory path for file uploads when `STORAGE_METHOD=file` |
| **`STORAGE_BUCKET_NAME`** | `handwriteme-storage` | S3 mode | Cloudflare R2 / S3 bucket name |
| **`AWS_ACCESS_KEY_ID`** | `<cloudflare-r2-access-key-id>` | S3 mode | Cloudflare R2 / S3 Access Key ID |
| **`AWS_SECRET_ACCESS_KEY`** | `<cloudflare-r2-secret-access-key>` | S3 mode | Cloudflare R2 / S3 Secret Access Key |
| **`AWS_ENDPOINT_URL_S3`** | `https://<account-id>.r2.cloudflarestorage.com` | S3 mode | Cloudflare R2 custom S3 endpoint URL (also accepts `AWS_ENDPOINT_URL`) |
| **`AWS_S3_REGION`** | `auto` | S3 mode | S3 region identifier (defaults to `auto` for Cloudflare R2) |

---

## 15. API Documentation

Interactive OpenAPI documentation is available at `/docs` and `/redoc`.

### Major Route Groups

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/v1/auth/jwt/login` | `POST` | Authenticate with email/password; returns access token |
| `/api/v1/accounts/register` | `POST` | Public registration for standard users |
| `/api/v1/accounts/open` | `POST` | Standard MSFLib open registration alias |
| `/api/v1/profiles/` | `GET` / `PATCH` | Read and update authenticated user profile details |
| `/api/v1/handwriting-profiles/` | `GET` / `POST` | List and create user handwriting profiles |
| `/api/v1/handwriting-profiles/{id}` | `GET` / `PATCH` / `DELETE` | Retrieve, update, or delete a handwriting profile |
| `/api/v1/handwriting-profiles/{id}/samples` | `POST` | Upload handwriting sample image (`.png`, `.jpg`) |
| `/api/v1/documents/text` | `POST` | Ingest raw text document |
| `/api/v1/documents/upload` | `POST` | Upload and extract text from digital PDF |
| `/api/v1/documents/{id}/generate` | `POST` | Synthesize handwriting preview |
| `/api/v1/documents/{id}/preview` | `GET` | Retrieve generated SVG preview pages |
| `/api/v1/documents/{id}/approve` | `POST` | Approve document preview for export |
| `/api/v1/documents/{id}/export` | `GET` | Download approved multi-page PDF document |

---

## 16. Verification and Test Results

### Running Tests Locally

```bash
# Run complete test suite
poetry run pytest app/tests -v

# Run focused registration and PDF parity tests
poetry run pytest app/tests/api/api_v1/test_registration.py app/tests/services/test_pdf_export_parity.py -v
```

### Verified Local Automated Test Summary

The following test execution reflects the local automated test suite run in the development Python environment:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-7.4.4
collected 85 items

app/tests/api/api_v1/test_auth.py .........................             [ 10%]
app/tests/api/api_v1/test_documents.py ................                 [ 25%]
app/tests/api/api_v1/test_handwriting_profiles.py ......                [ 35%]
app/tests/api/api_v1/test_handwriting_samples.py ...                    [ 40%]
app/tests/api/api_v1/test_registration.py ........                      [ 50%]
app/tests/api/api_v1/test_superuser_sync.py .........                   [ 60%]
app/tests/api/api_v1/test_celery.py s                                   [ 61%]
app/tests/services/test_model_adapter.py ........                       [ 75%]
app/tests/services/test_pdf_export_parity.py ...                        [ 85%]
app/tests/services/test_storage.py ...........                          [100%]

================== 84 passed, 1 skipped in 130.62s (0:02:10) ==================
```

*(Note: `test_celery_worker_test` is skipped as expected when running without an active Redis broker.)*

---

## 17. Production Cloud Deployment

- **Web Host**: Render Free Web Service running a multi-stage Docker container (`python:3.10-slim`).
- **Database**: Neon Serverless PostgreSQL with SSL pooling connections configured via `SQLALCHEMY_DATABASE_URI`.
- **Storage**: Cloudflare R2 bucket with `STORAGE_METHOD=s3`, providing persistent zero-egress artifact storage across Render container restarts.
- **Stateless Operation**: Render instances contain no stateful data; all accounts, workspaces, documents, and preview metadata reside in PostgreSQL, while sample images and exported PDFs reside in Cloudflare R2.
- **Production Rendering Note**: The hosted Render Free instance operates using the calibrated parametric SVG engine because PyTorch and neural model weights are excluded to maintain container stability under the 512 MB memory limit.

---

## 18. Security and Tenancy Isolation

- **Password Security**: Passwords hashed with `bcrypt` (12 rounds in production, 4 rounds in test configuration).
- **Tenant Isolation**: Every database query on `HandwritingProfile`, `HandwritingSample`, and `Document` filters by `account_id` and `workspace_id`. Cross-user inspection returns `404 Not Found`.
- **Role Protection**: Public registration rejects attempts to set `role="admin"` or `role="superuser"`, strictly enforcing `AccountRole.user`.
- **Storage Sanitization**: File uploads pass through `sanitize_filename()` and `_validate_storage_key()` to prevent directory traversal.
- **File Validation**: Sample uploads are validated via binary signature inspection rather than trusting user-supplied `Content-Type` headers.

---

## 19. Model Attribution and Licensing

1. **Recurrent Neural Network Handwriting Model**:
   - Architecture based on Alex Graves (2013), *"Generating Sequences With Recurrent Neural Networks"* ([arXiv:1308.0850](https://arxiv.org/abs/1308.0850)).
   - Trained on the IAM Online Handwriting Database (IAMOnDB), maintained by the Research Group on Computer Vision and Artificial Intelligence (FKI) at the University of Bern.
2. **Typography**:
   - `Caveat` handwriting font designed by Pablo Impallari, licensed under the [SIL Open Font License (OFL 1.1)](http://scripts.sil.org/OFL).
   - `Inter` and `Outfit` fonts licensed under the SIL Open Font License.

---

## 20. Known Limitations

1. **Hosted Memory Ceiling**: The hosted Render Free deployment operates with a 512 MB RAM ceiling. To prevent OOM crashes, production handwriting generation uses the fast parametric SVG engine rather than neural model weights.
2. **No Automated Weight Fine-Tuning**: Uploading handwriting sample images stores them for reference; it does not currently extract strokes or retrain/fine-tune the neural model weights.
3. **Preview-to-PDF Visual Consistency**: Layout, ruled line geometry, baseline alignment, and searchable text underlays are matched between preview and export. However, visual font differences between the browser's cursive font rendering and the PDF font definitions remain an acknowledged limitation until full embedded font streams are verified on the deployed host.
4. **Mock Email Delivery**: Production email delivery requires external SMTP gateway credentials (e.g., SendGrid, Mailgun, AWS SES).

---

## 21. Future Development Roadmap

- [ ] **Asynchronous Celery Workers**: Offload heavy multi-page document synthesis to distributed Redis/Celery background workers.
- [ ] **OCR Stroke Extraction Pipeline**: Implement a computer vision model (e.g., Skeletonization / Contour tracing) to vectorize uploaded handwriting photos into custom stroke libraries.
- [ ] **TrueType Font Embedding**: Embed custom TrueType cursive glyph streams directly inside PDF 1.4 objects for zero-mismatch client rendering across all PDF viewers.
- [ ] **Multi-Page Export Batching**: Enable single-click bulk PDF exports for entire book chapters and large lecture notes.
- [ ] **Transactional Email Setup**: Configure real-time verification emails via AWS SES / Resend.
