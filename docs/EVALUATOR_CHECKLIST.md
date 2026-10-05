# VigilantEye — Evaluator Checklist

Print or keep open during the viva. Password: **`Demo@123`**.  
Detailed steps: [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) · Scope map: [SCOPE_COVERAGE.md](SCOPE_COVERAGE.md) · Overview: [../README.md](../README.md)

---

## Setup

| # | Check | Pass |
|---|--------|------|
| 1 | Backend `uvicorn` on :8000 | ☐ |
| 2 | Frontend on http://127.0.0.1:5173 | ☐ |
| 3 | `python seed_all_demo.py` run | ☐ |
| 4 | Login with any demo account | ☐ |

---

## Story path

| # | Check | Pass |
|---|--------|------|
| 5 | Live Monitoring demo clip → confirmed detection | ☐ |
| 6 | Auto SNAPSHOT (and optional CLIP) on detection | ☐ |
| 7 | Draft case from detection OR create with sign-off | ☐ |
| 8 | Case shows student name/roll + exam/room | ☐ |
| 9 | Student sees case + notification → clarification | ☐ |
| 10 | HOD→DEC→Exam→UFM with signed reviews | ☐ |
| 11 | On APPROVE: result hold appears | ☐ |
| 12 | Evidence **Open file** works | ☐ |
| 13 | Reports **Export cases CSV** | ☐ |
| 14 | Audit Trail shows create / sign / review / hold | ☐ |

---

## Scope honesty

| # | Check | Pass |
|---|--------|------|
| 15 | Live Monitoring = MJPEG (not WebRTC mesh) | ☐ |
| 16 | Sign-off = typed name + ack (not PKI) | ☐ |
| 17 | Email = SMTP or EMAIL_MOCK (not required for demo) | ☐ |
| 18 | YOLO honest (custom / COCO fallback) | ☐ |
| 19 | SSO / SIS / PDF engine = FUTURE | ☐ |

---

## Demo accounts (quick)

`invigilator@` · `hod@` · `dec@` · `examdept@` · `ufm@` · `student@` — all `@demo.com`
