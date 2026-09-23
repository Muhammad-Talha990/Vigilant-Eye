# VigilantEye

AI-assisted **Unfair Means (UFM)** detection and institutional review portal for Air University (FYP submission build).

Invigilators monitor live feeds → confirmed detections auto-capture evidence → cases with digital sign-off → students clarify → HOD / DEC / Exam Dept / UFM Committee review → approved cases auto-hold results — with portal notifications (optional SMTP / EMAIL_MOCK) and a full audit trail.

**Demo steps:** [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) · **Scope map:** [docs/SCOPE_COVERAGE.md](docs/SCOPE_COVERAGE.md) · **Checklist:** [docs/EVALUATOR_CHECKLIST.md](docs/EVALUATOR_CHECKLIST.md)

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React + Vite + Tailwind + React Router |
| Backend | FastAPI + SQLAlchemy + JWT + bcrypt |
| Database | PostgreSQL |
| AI | Ultralytics YOLO → `detections` + auto evidence |

---

## Repository layout

```text
backend/     FastAPI API, models, auth, workflow, uploads
frontend/    UFM Web Portal (role dashboards)
ai/          Detector scripts, samples, annotated outputs
docs/        Demo runbook, mockups
```

---

## Quick start

### 1. Database

Create a PostgreSQL database named `vigilant_eye` and put credentials in `backend/.env` (do not commit secrets):

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/vigilant_eye
JWT_SECRET=your-long-random-secret
JWT_EXPIRE_MINUTES=480
```

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed_all_demo.py
uvicorn main:app --reload
```

API: http://127.0.0.1:8000 · Docs: http://127.0.0.1:8000/docs

`seed_all_demo.py` creates demo users (DEMO001 link), room A-101, webcam + sample-clip cameras, and exam CS101.

### 3. Frontend

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

Portal: http://127.0.0.1:5173

`frontend/.env`:

```env
VITE_API_URL=http://127.0.0.1:8000
```

---

## Demo accounts

Password for all: **`Demo@123`**

| Role | Email |
|------|--------|
| Invigilator | `invigilator@demo.com` |
| HOD | `hod@demo.com` |
| DEC | `dec@demo.com` |
| Exam Department | `examdept@demo.com` |
| UFM Committee | `ufm@demo.com` |
| Student | `student@demo.com` |

Student portal is linked to roll **`DEMO001`**. Create cases against that student to demo clarifications.

---

## Core workflow (one line)

`PENDING` → (staff open) `UNDER_REVIEW` → HOD FORWARD → `DEC_REVIEW` → DEC FORWARD → `EXAM_DEPARTMENT_REVIEW` → Exam FORWARD → `UFM_COMMITTEE_REVIEW` → APPROVE/REJECT → hold on approve.

Create case and each review require **digital sign-off** (typed full name + acknowledgment checkbox).

---

## Evaluator checklist

Use during a viva / demo. Tick as you go. Prefer [docs/EVALUATOR_CHECKLIST.md](docs/EVALUATOR_CHECKLIST.md).

### Environment

- [ ] Backend running (`uvicorn`) without errors  
- [ ] Frontend opens at http://127.0.0.1:5173  
- [ ] Login works with a demo account  

### Invigilator

- [ ] Dashboard loads with live KPIs  
- [ ] Live Monitoring demo clip produces a confirmed detection + auto evidence  
- [ ] Create Case / draft case for **DEMO001** with sign-off  
- [ ] Evidence **Open file** works on Case Detail  

### Student

- [ ] `student@demo.com` sees only DEMO001 cases (+ notification)  
- [ ] Clarification submits and appears on case detail  
- [ ] Help & Support page opens  

### Review chain

- [ ] HOD can **FORWARD** (with sign-off) from PENDING / UNDER_REVIEW  
- [ ] DEC → Exam → UFM with signed reviews  
- [ ] UFM can **APPROVE** or **REJECT**  

### Aftermath

- [ ] APPROVED case creates a result **HELD** / transcript **BLOCKED**  
- [ ] Exam/UFM can **Release** a hold  
- [ ] Reports CSV export downloads  
- [ ] Audit Trail shows create / sign / review / clarification / hold  

### Honesty check (submission scope)

- [ ] Live Monitoring shown as MJPEG (webcam / sample clip / RTSP URL), not WebRTC mesh  
- [ ] Sign-off described as typed name + ack (not PKI)  
- [ ] Email = SMTP optional / EMAIL_MOCK otherwise  
- [ ] YOLO described honestly (custom train and/or COCO fallback)  
- [ ] SSO / SIS / PDF engine = FUTURE (see SCOPE_COVERAGE)  

---

## Prototype vs future

| In this submission | FUTURE |
|--------------------|--------|
| JWT auth + RBAC | SSO / campus IdP |
| Case workflow + digital sign-off (name/ack) | PKI / cryptographic e-sign |
| Auto SNAPSHOT/CLIP + manual evidence | Cloud evidence vault / CDN |
| Portal notifications + SMTP / EMAIL_MOCK | SMS / WebSockets push |
| Student clarification (DEMO001 link) | Full SIS binding |
| Result hold / release | ERP grade integration |
| Audit log | Advanced forensics export |
| Reports KPIs + CSV | PDF print engine |
| Live MJPEG + YOLO → detections | Multi-cam WebRTC, stronger custom ML |

---

## Useful commands

```powershell
# Full demo seed (users + cameras + CS101)
cd backend
.\venv\Scripts\Activate.ps1
python seed_all_demo.py
python migrate_submission_features.py

# Smoke tests
pytest -q

# Frontend production build check
cd frontend
npm run build
```

Optional email (otherwise logs `EMAIL_MOCK`):

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=noreply@example.com
SMTP_USE_TLS=true
```

AI scripts live under `ai/` (`train_yolo.py`, `save_confirmed_to_db.py`; Live Monitoring uses the API).

---

## Authors

Student FYP team — Air University. Built with Cursor as a development assistant; authors own the project and demo.
