# VigilantEye — FYP Demo Runbook

Short walkthrough for supervisors / evaluators. Password for all demo users: **`Demo@123`**.

---

## 0. Start the stack (before the demo)

**Terminal A — backend**

```powershell
cd "D:\BS CS\Vigilant Eye\backend"
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

**Terminal B — frontend**

```powershell
cd "D:\BS CS\Vigilant Eye\frontend"
npm run dev
```

Open: **http://127.0.0.1:5173**  
API docs (optional): **http://127.0.0.1:8000/docs**

Seed users + cameras (safe to re-run):

```powershell
cd "D:\BS CS\Vigilant Eye\backend"
.\venv\Scripts\Activate.ps1
python seed_all_demo.py
```

---

## 1. Demo accounts

| Role | Email | What to show |
|------|--------|----------------|
| Invigilator | `invigilator@demo.com` | Live Monitoring, detections, create case, evidence |
| HOD | `hod@demo.com` | Forward case, audit trail |
| DEC | `dec@demo.com` | Investigate / forward |
| Exam Department | `examdept@demo.com` | Forward to committee, result holds |
| UFM Committee | `ufm@demo.com` | APPROVE / REJECT |
| Student | `student@demo.com` | Own cases + clarification |

Login page: click a role card to **sign in** (password `Demo@123`).

**Student portal link:** cases for roll **`DEMO001`**. Create Case defaults to this roll when present.

---

## 2. Happy-path story (≈ 10–12 minutes)

### A. Invigilator — live detect → case

1. Login as **invigilator@demo.com** (one-click on login page)
2. Dashboard → **Live Monitoring** (or Quick Action)
3. Click **Demo: sample clip + detect**  
   - LIVE tile shows MJPEG + YOLO boxes  
   - Persist writes confirmed UFM labels to DB  
   - Alternate: **Demo: webcam** if a laptop camera is available
4. Open **Detections & Alerts** → **Create draft case** (or File case)  
   - Auto SNAPSHOT/CLIP from persist attaches when drafting  
5. On Create Case: type full name + **I certify…** digital sign-off  
6. Student: **DEMO001**, exam **CS101**, violation matching detection  
7. Optional: **Evidence Library** → upload a small image; use **Open file** on Case Detail  

**Talking point:** Case starts as **PENDING**; HOD is notified in-portal (and EMAIL_MOCK / SMTP if configured). Live video is backend MJPEG — not browser-native WebRTC. Sign-off is typed name + ack (not PKI).

### B. Student — clarification

1. Logout → login **student@demo.com**
2. **UFM Cases** → only DEMO001 cases
3. Open case → **Submit Clarification** (10+ characters)

### C. HOD → DEC → Exam Dept → UFM

| Step | Login as | Action | New status |
|------|----------|--------|------------|
| 0 | `hod@demo.com` | Open case (optional) | `UNDER_REVIEW` |
| 1 | `hod@demo.com` | **FORWARD** + sign-off | `DEC_REVIEW` |
| 2 | `dec@demo.com` | **FORWARD** + sign-off | `EXAM_DEPARTMENT_REVIEW` |
| 3 | `examdept@demo.com` | **FORWARD** + sign-off | `UFM_COMMITTEE_REVIEW` |
| 4 | `ufm@demo.com` | **APPROVE** (or REJECT) + sign-off | `APPROVED` / `REJECTED` |

On **APPROVE**: result hold (HELD / BLOCKED) → show **Result Control** → optional **Release**.

### D. Audit Trail

As HOD / DEC / Exam / UFM → **Audit Trail** for `CASE_CREATED`, `CASE_SIGNED`, `CLARIFICATION_SUBMITTED`, `CASE_REVIEW_*`, `RESULT_HOLD_CREATED`.

---

## 3. Optional offline AI CLI

If live detect is slow on CPU:

```powershell
cd "D:\BS CS\Vigilant Eye"
.\backend\venv\Scripts\Activate.ps1
python ai/save_confirmed_to_db.py --source ai/samples/phone_under_desk.jpg --camera-id 1
```

Then refresh **Detections & Alerts**.

**Honest line:** custom UFM training may still be in progress on CPU; detector falls back to COCO / last `best.pt`. Phones/watches can be missed. Production RTSP fleet + WebRTC = future.

---

## 4. Role dashboards (30-second tour)

| Role | Highlight |
|------|-----------|
| Invigilator | Live Monitoring CTA + detections + my open cases |
| HOD / DEC / Exam / UFM | Queue KPIs + charts |
| Student | Cases + clarification CTA |
| Reports | KPIs + **Export cases CSV** (PDF = FUTURE) |
| Live Monitoring | MJPEG live tiles (webcam / clip / RTSP) |

---

## 5. Done vs future

### In this build

- Auth + RBAC (JWT)
- UFM case workflow with role actions + digital sign-off (name/ack)
- Auto evidence (snapshot/clip) from confirmed detections
- Evidence upload + Open file
- Portal notifications + optional SMTP / EMAIL_MOCK
- Student clarification
- Result hold on approve + release
- Audit log
- Live Monitoring (MJPEG + optional YOLO + persist)
- Enriched cases (student / exam / room)
- Reports CSV export
- Role-based React portal

### Still future / limited

- Production multi-camera WebRTC grid
- Campus SSO / WebSockets push
- Strong custom YOLO (needs finished GPU train; COCO/`best.pt` fallback OK)
- PKI signatures / full SIS / PDF print engine

See [SCOPE_COVERAGE.md](SCOPE_COVERAGE.md) for the full protocol map.

---

## 6. If something breaks mid-demo

| Symptom | Quick fix |
|---------|-----------|
| Login fails | `python seed_all_demo.py`; password `Demo@123` |
| No cameras on Monitoring | `python seed_demo_cameras.py` or `seed_all_demo.py` |
| Student sees 0 cases | Case must use roll **DEMO001** |
| Empty Create Case dropdowns | Seed cameras (includes CS101) or create exam in Master Data |
| Sample clip won’t open | Confirm `ai/samples/sample_exam_clip.mp4` exists |
| Audit 403 | Use HOD/DEC/Exam/UFM — not invigilator/student |
| Frontend / API errors | Backend `:8000`, frontend `127.0.0.1:5173` |

---

## 7. Closing sentence

> VigilantEye shows an end-to-end institutional UFM pipeline: live AI-assisted monitoring into detections, invigilator case filing, student clarification, multi-role review, automatic result hold, and a full audit trail — with production video mesh and stronger custom ML called out as next steps.
