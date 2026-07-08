import {
  STATUS_ORDER,
  calculateMetrics,
  getActivityMessage,
  getRiskSummary,
  sampleTasks,
  updateTaskStatus,
} from "./2026-07-08-task-dashboard-state.mjs";

let tasks = structuredClone(sampleTasks);
let selectedTaskId = tasks[1].id;
let activity = [
  "기획자, 평가자, 개발자, 보조 개발자, 디자이너가 각각 산출물을 작성했습니다.",
  "메인 스레드가 역할별 결과를 작업 관리 대시보드 데모로 통합했습니다.",
];

const statusMeta = {
  "대기": { label: "대기", className: "status-waiting" },
  "진행 중": { label: "진행 중", className: "status-doing" },
  "검토": { label: "검토", className: "status-review" },
  "위험": { label: "위험", className: "status-risk" },
  "완료": { label: "완료", className: "status-done" },
};

const agentNotes = [
  {
    role: "기획자",
    summary: "화면 변화가 선명한 데모 후보를 확장했습니다.",
    tone: "idea",
  },
  {
    role: "평가자",
    summary: "작업 관리 대시보드를 가장 영상 친화적인 후보로 판단했습니다.",
    tone: "score",
  },
  {
    role: "개발자",
    summary: "정적 HTML/CSS/JS와 테스트 파일 중심의 구현 경로를 제안했습니다.",
    tone: "build",
  },
  {
    role: "보조 개발자",
    summary: "상태 계산 테스트, 공개 저장소 점검, ZIP 공개 위험을 확인했습니다.",
    tone: "risk",
  },
  {
    role: "디자이너",
    summary: "상단 KPI와 칸반 변화가 3초 안에 보이도록 정리했습니다.",
    tone: "design",
  },
];

function getSelectedTask() {
  return tasks.find((task) => task.id === selectedTaskId) ?? tasks[0];
}

function setText(selector, value) {
  document.querySelector(selector).textContent = String(value);
}

function createElement(tagName, options = {}) {
  const element = document.createElement(tagName);

  if (options.className) {
    element.className = options.className;
  }

  if (options.text !== undefined) {
    element.textContent = options.text;
  }

  return element;
}

function renderMetrics() {
  const metrics = calculateMetrics(tasks);

  setText("[data-total]", metrics.total);
  setText("[data-completion]", `${metrics.completionRate}%`);
  setText("[data-risk-count]", metrics.riskCount);
  setText("[data-due-week]", metrics.dueThisWeek);

  const progressBar = document.querySelector("[data-progress-bar]");
  progressBar.style.width = `${metrics.completionRate}%`;
  progressBar.setAttribute("aria-valuenow", String(metrics.completionRate));

  const progressLabel = document.querySelector("[data-progress-label]");
  progressLabel.textContent = `완료 ${metrics.completed}/${metrics.total}`;

  for (const status of STATUS_ORDER) {
    const node = document.querySelector(`[data-status-count="${status}"]`);
    if (node) {
      node.textContent = metrics.byStatus[status];
    }
  }
}

function renderBoard() {
  const board = document.querySelector("[data-board]");
  board.replaceChildren();

  for (const status of STATUS_ORDER) {
    const column = createElement("section", {
      className: `board-column ${statusMeta[status].className}`,
    });
    column.setAttribute("aria-label", `${status} 작업`);

    const header = createElement("div", { className: "column-header" });
    header.append(
      createElement("span", { text: status }),
      createElement("strong", {
        text: String(tasks.filter((task) => task.status === status).length),
      }),
    );
    column.append(header);

    const statusTasks = tasks.filter((task) => task.status === status);
    if (statusTasks.length === 0) {
      column.append(createElement("p", { className: "empty-column", text: "작업 없음" }));
    }

    for (const task of statusTasks) {
      column.append(createTaskCard(task));
    }

    board.append(column);
  }
}

function createTaskCard(task) {
  const card = createElement("article", {
    className: `task-card ${task.id === selectedTaskId ? "selected" : ""}`,
  });
  card.tabIndex = 0;
  card.dataset.taskId = task.id;

  const top = createElement("div", { className: "task-topline" });
  const owner = createElement("span", { className: "owner-pill", text: task.owner });
  const risk = createElement("span", {
    className: `risk-pill ${task.riskLevel === "높음" ? "high" : ""}`,
    text: task.riskLevel,
  });
  top.append(owner, risk);

  const title = createElement("h3", { text: task.title });
  const meta = createElement("p", {
    className: "task-meta",
    text: `우선순위 ${task.priority} · ${task.dueInDays === 0 ? "오늘 마감" : `${task.dueInDays}일 남음`}`,
  });

  const actions = createElement("div", { className: "status-actions" });
  for (const status of STATUS_ORDER) {
    const button = createElement("button", {
      className: task.status === status ? "active" : "",
      text: status,
    });
    button.type = "button";
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      changeStatus(task.id, status);
    });
    actions.append(button);
  }

  card.addEventListener("click", () => {
    selectedTaskId = task.id;
    render();
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectedTaskId = task.id;
      render();
    }
  });

  card.append(top, title, meta, actions);
  return card;
}

function renderDetail() {
  const task = getSelectedTask();
  const detail = document.querySelector("[data-detail]");
  detail.replaceChildren();

  const heading = createElement("h2", { text: task.title });
  const meta = createElement("p", {
    className: "detail-meta",
    text: `${task.owner} 담당 · ${task.status} · 위험도 ${task.riskLevel}`,
  });
  const nextAction = createElement("p", {
    className: "next-action",
    text: task.nextAction,
  });
  const quickActions = createElement("div", { className: "detail-actions" });

  for (const status of STATUS_ORDER) {
    const button = createElement("button", {
      className: task.status === status ? "active" : "",
      text: status,
    });
    button.type = "button";
    button.addEventListener("click", () => changeStatus(task.id, status));
    quickActions.append(button);
  }

  detail.append(heading, meta, nextAction, quickActions);
}

function renderRiskPanel() {
  const riskList = document.querySelector("[data-risk-list]");
  const risks = getRiskSummary(tasks);
  riskList.replaceChildren();

  if (risks.length === 0) {
    riskList.append(createElement("li", { className: "all-clear", text: "활성 위험 없음" }));
    return;
  }

  for (const risk of risks) {
    const item = createElement("li");
    item.append(
      createElement("strong", { text: risk.title }),
      createElement("span", { text: `${risk.owner} · ${risk.reason}` }),
    );
    riskList.append(item);
  }
}

function renderAgents() {
  const list = document.querySelector("[data-agent-list]");
  list.replaceChildren();

  for (const note of agentNotes) {
    const item = createElement("li", { className: `agent-note ${note.tone}` });
    item.append(
      createElement("strong", { text: `${note.role} 서브에이전트` }),
      createElement("span", { text: note.summary }),
    );
    list.append(item);
  }
}

function renderActivity() {
  const list = document.querySelector("[data-activity]");
  list.replaceChildren();

  for (const message of activity.slice(0, 4)) {
    list.append(createElement("li", { text: message }));
  }
}

function changeStatus(taskId, status) {
  const previousTask = tasks.find((task) => task.id === taskId);
  tasks = updateTaskStatus(tasks, taskId, status);
  const nextTask = tasks.find((task) => task.id === taskId);
  selectedTaskId = taskId;
  activity = [getActivityMessage(previousTask, nextTask), ...activity];
  render();
}

function render() {
  renderMetrics();
  renderBoard();
  renderDetail();
  renderRiskPanel();
  renderAgents();
  renderActivity();

  if (window.lucide) {
    window.lucide.createIcons({ attrs: { "stroke-width": 1.5 } });
  }
}

document.querySelector("[data-reset]").addEventListener("click", () => {
  tasks = structuredClone(sampleTasks);
  selectedTaskId = tasks[1].id;
  activity = ["샘플 데이터가 초기 상태로 돌아갔습니다.", ...activity];
  render();
});

render();
