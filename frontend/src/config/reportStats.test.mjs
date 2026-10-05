/**
 * Node built-in tests for reportStats (no Vitest/Jest added).
 * Run: node --test src/config/reportStats.test.mjs
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  UNKNOWN_NOT_RECORDED,
  departmentWiseStats,
  semesterWiseStats,
} from "./reportStats.js";

describe("departmentWiseStats", () => {
  it("splits two departments", () => {
    const rows = departmentWiseStats([
      { id: 1, student_department: "CS" },
      { id: 2, student_department: "EE" },
    ]);
    assert.deepEqual(
      Object.fromEntries(rows.map((r) => [r.label, r.count])),
      { CS: 1, EE: 1 }
    );
  });

  it("counts multiple cases in the same department", () => {
    const rows = departmentWiseStats([
      { student_department: "CS" },
      { student_department: "CS" },
      { student_department: "CS" },
      { student_department: "EE" },
    ]);
    assert.equal(rows.find((r) => r.label === "CS").count, 3);
    assert.equal(rows.find((r) => r.label === "EE").count, 1);
  });

  it("handles missing department without crashing", () => {
    const rows = departmentWiseStats([
      { student_department: null },
      { student_department: "" },
      { student_department: "   " },
      {},
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].label, UNKNOWN_NOT_RECORDED);
    assert.equal(rows[0].count, 4);
  });
});

describe("semesterWiseStats", () => {
  it("splits two semesters", () => {
    const rows = semesterWiseStats([
      { exam_semester: "Fall 2025" },
      { exam_semester: "Spring 2026" },
    ]);
    assert.deepEqual(
      Object.fromEntries(rows.map((r) => [r.label, r.count])),
      { "Fall 2025": 1, "Spring 2026": 1 }
    );
  });

  it("counts multiple cases in the same semester", () => {
    const rows = semesterWiseStats([
      { exam_semester: "Fall 2025" },
      { exam_semester: "Fall 2025" },
      { exam_semester: "Spring 2026" },
    ]);
    assert.equal(rows.find((r) => r.label === "Fall 2025").count, 2);
    assert.equal(rows.find((r) => r.label === "Spring 2026").count, 1);
  });

  it("handles missing semester without crashing", () => {
    const rows = semesterWiseStats([
      { exam_semester: null },
      { exam_semester: undefined },
    ]);
    assert.equal(rows[0].label, UNKNOWN_NOT_RECORDED);
    assert.equal(rows[0].count, 2);
  });

  it("empty input yields empty stats", () => {
    assert.deepEqual(departmentWiseStats([]), []);
    assert.deepEqual(semesterWiseStats(null), []);
  });
});
