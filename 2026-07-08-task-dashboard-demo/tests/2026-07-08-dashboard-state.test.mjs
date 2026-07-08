import assert from "node:assert/strict";
import {
  calculateMetrics,
  updateTaskStatus,
  getRiskSummary,
} from "../2026-07-08-task-dashboard-state.mjs";

const sampleTasks = [
  {
    id: "task-1",
    title: "데모 아이디어 확정",
    status: "완료",
    dueInDays: 1,
    riskLevel: "낮음",
  },
  {
    id: "task-2",
    title: "대시보드 UI 구현",
    status: "진행 중",
    dueInDays: 2,
    riskLevel: "보통",
  },
  {
    id: "task-3",
    title: "보안 점검",
    status: "위험",
    dueInDays: 0,
    riskLevel: "높음",
  },
  {
    id: "task-4",
    title: "촬영 시나리오 작성",
    status: "검토",
    dueInDays: 5,
    riskLevel: "낮음",
  },
];

function testInitialMetrics() {
  const metrics = calculateMetrics(sampleTasks);

  assert.equal(metrics.total, 4);
  assert.equal(metrics.completed, 1);
  assert.equal(metrics.completionRate, 25);
  assert.equal(metrics.riskCount, 1);
  assert.equal(metrics.dueThisWeek, 4);
  assert.deepEqual(metrics.byStatus, {
    "대기": 0,
    "진행 중": 1,
    "검토": 1,
    "위험": 1,
    "완료": 1,
  });
}

function testStatusUpdateRecalculatesRiskAndCompletion() {
  const updated = updateTaskStatus(sampleTasks, "task-3", "완료");
  const metrics = calculateMetrics(updated);
  const originalTask = sampleTasks.find((task) => task.id === "task-3");
  const updatedTask = updated.find((task) => task.id === "task-3");

  assert.equal(originalTask.status, "위험");
  assert.equal(updatedTask.status, "완료");
  assert.equal(updatedTask.riskLevel, "낮음");
  assert.equal(metrics.completed, 2);
  assert.equal(metrics.completionRate, 50);
  assert.equal(metrics.riskCount, 0);
}

function testRiskSummaryOnlyIncludesActiveRisks() {
  const summary = getRiskSummary(sampleTasks);

  assert.equal(summary.length, 1);
  assert.equal(summary[0].id, "task-3");
  assert.match(summary[0].reason, /마감|위험/);
}

function testEmptyMetricsAreStable() {
  const metrics = calculateMetrics([]);

  assert.equal(metrics.total, 0);
  assert.equal(metrics.completed, 0);
  assert.equal(metrics.completionRate, 0);
  assert.equal(metrics.riskCount, 0);
  assert.equal(metrics.dueThisWeek, 0);
}

testInitialMetrics();
testStatusUpdateRecalculatesRiskAndCompletion();
testRiskSummaryOnlyIncludesActiveRisks();
testEmptyMetricsAreStable();

console.log("dashboard-state tests passed");
