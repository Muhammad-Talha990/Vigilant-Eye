"""Phase 22 — read-only data integrity audit. Does not modify data."""

from __future__ import annotations

import json
from sqlalchemy import text
from database import engine


def q(conn, sql: str):
    return conn.execute(text(sql)).fetchall()


def main() -> None:
    issues: list[dict] = []
    with engine.connect() as conn:
        tables = [r[0] for r in q(conn, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")]
        print("TABLES", tables)

        # Duplicate emails
        rows = q(
            conn,
            "SELECT lower(email), COUNT(*), array_agg(id) FROM users GROUP BY lower(email) HAVING COUNT(*) > 1",
        )
        issues.append(
            {
                "issue": "duplicate_emails",
                "count": len(rows),
                "table": "users",
                "ids": [list(r[2]) for r in rows],
                "safe_auto_fix": False,
            }
        )

        # Invalid roles
        rows = q(
            conn,
            """
            SELECT id, email, role FROM users
            WHERE role NOT IN (
              'ADMINISTRATOR','STUDENT','INVIGILATOR','HOD','DEC',
              'EXAM_DEPARTMENT','UFM_COMMITTEE'
            )
            """,
        )
        issues.append(
            {
                "issue": "invalid_user_roles",
                "count": len(rows),
                "table": "users",
                "ids": [r[0] for r in rows],
                "safe_auto_fix": False,
            }
        )

        # Students pointing at missing users
        rows = q(
            conn,
            """
            SELECT s.id, s.student_id, s.user_id FROM students s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.user_id IS NOT NULL AND u.id IS NULL
            """,
        )
        issues.append(
            {
                "issue": "students_orphan_user_fk",
                "count": len(rows),
                "table": "students",
                "ids": [r[0] for r in rows],
                "safe_auto_fix": False,
            }
        )

        # Duplicate student_id / user_id
        for col in ("student_id", "user_id"):
            if col == "user_id":
                sql = f"SELECT {col}, COUNT(*), array_agg(id) FROM students WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1"
            else:
                sql = f"SELECT {col}, COUNT(*), array_agg(id) FROM students GROUP BY {col} HAVING COUNT(*) > 1"
            rows = q(conn, sql)
            issues.append(
                {
                    "issue": f"duplicate_students_{col}",
                    "count": len(rows),
                    "table": "students",
                    "ids": [list(r[2]) for r in rows],
                    "safe_auto_fix": False,
                }
            )

        # Cases → missing student/exam/reporter
        for label, sql in [
            (
                "cases_missing_student",
                "SELECT c.id, c.case_number FROM ufm_cases c LEFT JOIN students s ON s.id=c.student_id WHERE s.id IS NULL",
            ),
            (
                "cases_missing_exam",
                "SELECT c.id, c.case_number FROM ufm_cases c LEFT JOIN exams e ON e.id=c.exam_id WHERE e.id IS NULL",
            ),
            (
                "cases_missing_reporter",
                "SELECT c.id, c.case_number FROM ufm_cases c LEFT JOIN users u ON u.id=c.reported_by WHERE u.id IS NULL",
            ),
        ]:
            rows = q(conn, sql)
            issues.append(
                {
                    "issue": label,
                    "count": len(rows),
                    "table": "ufm_cases",
                    "ids": [r[0] for r in rows],
                    "safe_auto_fix": False,
                }
            )

        # Evidence orphans
        for label, sql in [
            (
                "evidence_missing_case",
                "SELECT id FROM evidence WHERE case_id IS NOT NULL AND case_id NOT IN (SELECT id FROM ufm_cases)",
            ),
            (
                "evidence_missing_camera",
                "SELECT id FROM evidence WHERE camera_id IS NOT NULL AND camera_id NOT IN (SELECT id FROM cameras)",
            ),
            (
                "evidence_missing_uploader",
                "SELECT id FROM evidence WHERE uploaded_by IS NOT NULL AND uploaded_by NOT IN (SELECT id FROM users)",
            ),
            (
                "evidence_orphan_detection_id",
                "SELECT id FROM evidence WHERE detection_id IS NOT NULL AND detection_id NOT IN (SELECT id FROM detections)",
            ),
        ]:
            rows = q(conn, sql)
            issues.append(
                {
                    "issue": label,
                    "count": len(rows),
                    "table": "evidence",
                    "ids": [r[0] for r in rows],
                    "safe_auto_fix": False,
                }
            )

        # Reviews / clarifications / notifications / result_controls / audit
        checks = [
            (
                "reviews_missing_case",
                "case_reviews",
                "SELECT id FROM case_reviews WHERE case_id NOT IN (SELECT id FROM ufm_cases)",
            ),
            (
                "reviews_missing_reviewer",
                "case_reviews",
                "SELECT id FROM case_reviews WHERE reviewer_id NOT IN (SELECT id FROM users)",
            ),
            (
                "clarifications_missing_case",
                "clarifications",
                "SELECT id FROM clarifications WHERE case_id NOT IN (SELECT id FROM ufm_cases)",
            ),
            (
                "notifications_missing_user",
                "notifications",
                "SELECT id FROM notifications WHERE user_id NOT IN (SELECT id FROM users)",
            ),
            (
                "notifications_missing_case",
                "notifications",
                "SELECT id FROM notifications WHERE case_id IS NOT NULL AND case_id NOT IN (SELECT id FROM ufm_cases)",
            ),
            (
                "result_controls_missing_case",
                "result_controls",
                "SELECT id FROM result_controls WHERE case_id NOT IN (SELECT id FROM ufm_cases)",
            ),
            (
                "result_controls_missing_student",
                "result_controls",
                "SELECT id FROM result_controls WHERE student_id NOT IN (SELECT id FROM students)",
            ),
            (
                "audit_missing_user",
                "audit_logs",
                "SELECT id FROM audit_logs WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)",
            ),
            (
                "detections_missing_camera",
                "detections",
                "SELECT id FROM detections WHERE camera_id IS NOT NULL AND camera_id NOT IN (SELECT id FROM cameras)",
            ),
            (
                "detections_missing_student",
                "detections",
                "SELECT id FROM detections WHERE student_id IS NOT NULL AND student_id NOT IN (SELECT id FROM students)",
            ),
            (
                "cameras_missing_room",
                "cameras",
                "SELECT id FROM cameras WHERE room_id NOT IN (SELECT id FROM exam_rooms)",
            ),
            (
                "exams_missing_room",
                "exams",
                "SELECT id FROM exams WHERE room_id NOT IN (SELECT id FROM exam_rooms)",
            ),
            (
                "duplicate_case_numbers",
                "ufm_cases",
                "SELECT case_number, COUNT(*), array_agg(id) FROM ufm_cases GROUP BY case_number HAVING COUNT(*) > 1",
            ),
            (
                "duplicate_result_control_per_case",
                "result_controls",
                "SELECT case_id, COUNT(*), array_agg(id) FROM result_controls GROUP BY case_id HAVING COUNT(*) > 1",
            ),
        ]
        for label, table, sql in checks:
            rows = q(conn, sql)
            if "array_agg" in sql.lower():
                ids = [list(r[2]) for r in rows]
            else:
                ids = [r[0] for r in rows]
            issues.append(
                {
                    "issue": label,
                    "count": len(rows),
                    "table": table,
                    "ids": ids[:50],
                    "safe_auto_fix": False,
                }
            )

        # Counts
        counts = {}
        for t in tables:
            counts[t] = q(conn, f"SELECT COUNT(*) FROM {t}")[0][0]

        # Real accounts
        reals = q(
            conn,
            """
            SELECT id, email, role, is_active FROM users
            WHERE lower(email) IN (
              'm69121848@gmail.com',
              'alonekingabdullah110@gmail.com',
              '232514abdullah@gmail.com',
              '232514@students.au.edu.pk'
            )
            ORDER BY id
            """,
        )

        # FK list from information_schema
        fks = q(
            conn,
            """
            SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name,
                   rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints rc
              ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public'
            ORDER BY 1,2
            """,
        )

    print("COUNTS", json.dumps(counts))
    print("REAL_ACCOUNTS", [(r[0], r[1], r[2], r[3]) for r in reals])
    print("FK_COUNT", len(fks))
    for fk in fks:
        print("FK", fk)
    print("ISSUES")
    for iss in issues:
        if iss["count"]:
            print(json.dumps(iss))
    clean = [i for i in issues if i["count"] == 0]
    dirty = [i for i in issues if i["count"] > 0]
    print(f"SUMMARY clean={len(clean)} dirty={len(dirty)}")
    if not dirty:
        print("NO_DATA_INTEGRITY_ISSUES_FOUND")


if __name__ == "__main__":
    main()
