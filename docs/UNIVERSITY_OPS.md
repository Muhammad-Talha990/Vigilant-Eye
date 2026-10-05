# University operational workflow (Phase 23)

## Authentication (unchanged)

Google authenticates identity. VigilantEye `users.role` authorizes access.
Unknown Google emails receive **403**. `@students.au.edu.pk` does **not** auto-register.

## Role responsibilities

| Role | Operational focus |
|------|-------------------|
| ADMINISTRATOR | Users, roles, access, student directory, admin audit, system info — **not** UFM operations |
| INVIGILATOR | Monitoring (authorized), detections, report cases |
| HOD | Exam setup, case review (HOD stage), result context |
| DEC | DEC review queue (no live monitoring control) |
| EXAM_DEPARTMENT | Exam setup, mid-pipeline review, result holds/releases |
| UFM_COMMITTEE | Final approve/reject |
| STUDENT | Own cases, clarification, notifications |

## Exam setup workflow

1. Create **Exam Room** (HOD / Exam Dept).
2. Register **Camera** for that room (webcam / RTSP / sample file).
3. **Schedule Exam** (course, date, start/end; end must be after start).
4. Open exam detail:
   - **Enroll** students (optional roster). Empty roster = open (any student may be used on a case). Non-empty roster = case filing requires enrollment.
   - **Assign** invigilators (INVIGILATOR users only). Assignment is operational metadata; staff list visibility remains role-based.
5. Room cameras appear on exam detail for monitoring readiness.

## UFM lifecycle

Detection/incident → case (PENDING) → HOD/DEC/Exam Dept/UFM reviews → APPROVED/REJECTED → result hold on approve → release by Exam Dept.

Concurrency: case reviews use row locks (`FOR UPDATE`).
Clarification: one submission per student per case.
Draft-from-detection: refused if that detection is already linked to a case.

## Notifications

Portal notifications for case create/status, draft, clarification, result hold/release, detection alerts.
Email is optional; SMTP failure does not roll back DB actions.

## Supported monitoring sources

- Webcam (`webcam:0`)
- RTSP / IP camera URLs
- Approved sample file under `ai/samples/`

Real RTSP production readiness depends on campus network and camera availability — not claimed from sample/webcam tests alone.

## Limitations

- Invigilator assignment does not yet hide other exams from invigilators (visibility remains institutional staff scope).
- No SIS integration for result holds.
- RETURN review actions reset toward `PENDING` (existing workflow).
- Live RTSP reliability is environment-dependent.
