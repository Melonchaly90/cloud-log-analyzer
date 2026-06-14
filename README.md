 # 🖥️ Secure Cloud Log Analyzer 

 📌 Okais Rasool (2023-ag-9660) 


**CS-508 Cloud Computing — MapReduce + Neon DB + Railway**

A production-ready web application that processes large `.log` files using a pure-Python MapReduce engine, with IAM-based access control, cloud database persistence, and automated CI/CD via GitHub → Railway.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Online Web Portal (Flask)               │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │   IAM    │  │  MapReduce  │  │   Neon DB / SQLite│   │
│  │  Layer   │  │   Engine    │  │   (PostgreSQL)    │   │
│  └──────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────┘
          ↑ GitHub Actions CI/CD ↑
          └────── Railway Deployment ──────┘
```

---

## ✨ Features

| Component | Implementation |
|-----------|---------------|
| **Web Portal** | Flask + Jinja2 + Chart.js dashboard |
| **MapReduce** | Pure Python parallel engine (Split→Map→Shuffle→Reduce) |
| **Security** | IAM with PBKDF2 password hashing, RBAC (admin/viewer) |
| **Database** | Neon DB (Postgres) in production; SQLite fallback locally |
| **Secrets** | All credentials via environment variables — zero hard-coded secrets |
| **Deployment** | Railway with auto-deploy from GitHub `main` branch |
| **Audit Trail** | Every login, logout, and upload is logged |

---

## 🔄 MapReduce Pipeline

```
Raw .log file
     │
     ▼
┌─────────┐     Split file into N chunks of 500 lines each
│  SPLIT  │     using math.ceil(total_lines / chunk_size)
└─────────┘
     │
     ▼
┌─────────┐     Process each chunk concurrently with ThreadPoolExecutor
│   MAP   │     Emit: (HTTP_404, 1), (HOUR_14, 1), (METHOD_GET, 1)
└─────────┘
     │
     ▼
┌─────────┐     Group all values by identical keys
│ SHUFFLE │     defaultdict(list) → sorted dict
└─────────┘
     │
     ▼
┌─────────┐     sum(values) per key → final counts
│ REDUCE  │     Output: { HTTP_404: 312, HOUR_14: 894, ... }
└─────────┘
```

---

## 🚀 Quick Start (Local)

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/cloud-log-analyzer.git
cd cloud-log-analyzer
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY
```

### 3. Run

```bash
python app.py
# Visit http://localhost:5000
```

### 4. Generate a test log file

```bash
python generate_sample_log.py
# Creates sample_access.log with 5000 lines — upload via the portal
```

**Default credentials:**
- Admin: `admin` / `Admin@1234`
- Viewer: `viewer` / `Viewer@1234`

---

## ☁️ Deploy to Railway

### Step 1: Set up Neon DB

1. Go to [neon.tech](https://neon.tech) → create a free account
2. Create a new project → copy the **Connection String** (starts with `postgresql://`)

### Step 2: Deploy

1. Push this repository to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Under **Variables**, add:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_PASSWORD=YourSecureAdminPass!
VIEWER_PASSWORD=YourSecureViewerPass!
```

5. Railway auto-deploys — your live URL appears in the dashboard.

### Step 3: Auto-deploy

Every `git push origin main` triggers a fresh Railway deployment automatically. No manual steps required.

---

## 📁 Project Structure

```
cloud-log-analyzer/
├── app.py                   # Flask application & routes
├── requirements.txt         # Python dependencies
├── Procfile                 # Railway/Render process definition
├── railway.toml             # Railway deployment config
├── .env.example             # Environment variable template (no secrets)
├── .gitignore               # Excludes .env and *.db from git
├── generate_sample_log.py   # Test log file generator
│
├── mapreduce/
│   ├── __init__.py
│   └── engine.py            # Split→Map→Shuffle→Reduce implementation
│
├── auth/
│   ├── __init__.py
│   └── iam.py               # IAM: authentication + RBAC
│
├── db/
│   ├── __init__.py
│   └── database.py          # Neon DB / SQLite abstraction layer
│
└── templates/
    ├── base.html            # Shared layout + navbar
    ├── login.html           # IAM login page
    ├── dashboard.html       # Main dashboard
    ├── upload.html          # Log file upload + progress
    ├── results.html         # Charts + MapReduce analytics
    ├── history.html         # All past analyses
    └── audit.html           # Admin-only audit log
```

---

## 🔐 Security Architecture

### Identity & Access Management (IAM)
- Passwords hashed with **PBKDF2-HMAC-SHA256** (260,000 iterations)
- Constant-time comparison via `hmac.compare_digest` (prevents timing attacks)
- **Role-based access control**: Admin (full access) vs Viewer (read + upload only)
- Audit log captures every login, logout, and file upload event

### Secrets Management
- **Zero** hard-coded credentials anywhere in the codebase
- All secrets injected via Railway environment variables at container start
- `.env` is listed in `.gitignore` — never committed to version control
- `.env.example` contains only placeholder values for documentation

---

## 📊 Analytics Output

After processing, the dashboard shows:
- **HTTP error breakdown** (4xx / 5xx) with counts and severity tags
- **Hourly traffic chart** — identify peak load periods
- **HTTP method distribution** — GET/POST/PUT/DELETE doughnut chart
- **Top 10 source IPs** with request share bars
- **MapReduce execution trace** — chunks, parallel workers, total events

---

## 🔧 Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Flask session signing key (generate randomly) |
| `DATABASE_URL` | ✅ Production | Neon DB PostgreSQL connection string |
| `ADMIN_PASSWORD` | Optional | Overrides default admin password |
| `VIEWER_PASSWORD` | Optional | Overrides default viewer password |
| `SQLITE_PATH` | Optional | Local dev SQLite path (default: `log_analyzer.db`) |
| `PORT` | Auto | Set by Railway automatically |

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, Flask 3.0
- **WSGI Server**: Gunicorn
- **Database**: Neon DB (PostgreSQL via psycopg2) / SQLite (dev)
- **Parallel Processing**: `concurrent.futures.ThreadPoolExecutor`
- **Frontend**: Jinja2 templates, Chart.js 4, Font Awesome 6
- **Hosting**: Railway
- **Version Control**: GitHub
