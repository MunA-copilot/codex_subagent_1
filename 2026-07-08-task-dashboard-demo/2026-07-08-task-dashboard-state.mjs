export const STATUS_ORDER = ["대기", "진행 중", "검토", "위험", "완료"];

export const sampleTasks = [
  {
    id: "task-1",
    title: "서브에이전트 데모 아이디어 확정",
    owner: "기획자",
    status: "완료",
    priority: "높음",
    dueInDays: 1,
    riskLevel: "낮음",
    nextAction: "선택된 방향을 촬영 흐름에 반영",
  },
  {
    id: "task-2",
    title: "작업 관리 대시보드 UI 구현",
    owner: "개발자",
    status: "진행 중",
    priority: "높음",
    dueInDays: 2,
    riskLevel: "보통",
    nextAction: "카드 상태 변경과 KPI 갱신 연결",
  },
  {
    id: "task-3",
    title: "공개 저장소 보안 점검",
    owner: "보조 개발자",
    status: "위험",
    priority: "높음",
    dueInDays: 0,
    riskLevel: "높음",
    nextAction: "비밀값, 백업 ZIP, 공개 범위 재확인",
  },
  {
    id: "task-4",
    title: "90초 촬영 시나리오 정리",
    owner: "평가자",
    status: "검토",
    priority: "보통",
    dueInDays: 5,
    riskLevel: "낮음",
    nextAction: "가장 강한 장면을 3개로 압축",
  },
  {
    id: "task-5",
    title: "첫 화면 시각 밀도 조정",
    owner: "디자이너",
    status: "대기",
    priority: "보통",
    dueInDays: 6,
    riskLevel: "낮음",
    nextAction: "KPI 숫자와 카드 변화가 잘 보이게 정리",
  },
  {
    id: "task-6",
    title: "GitHub 푸시 권한 확인",
    owner: "개발자",
    status: "진행 중",
    priority: "높음",
    dueInDays: 1,
    riskLevel: "보통",
    nextAction: "collaborator 초대 수락 뒤 푸시 재시도",
  },
];

export function isActiveRisk(task) {
  return (
    task.status !== "완료" &&
    (task.status === "위험" || task.riskLevel === "높음" || task.dueInDays <= 0)
  );
}

export function calculateMetrics(tasks) {
  const byStatus = Object.fromEntries(STATUS_ORDER.map((status) => [status, 0]));

  for (const task of tasks) {
    if (Object.hasOwn(byStatus, task.status)) {
      byStatus[task.status] += 1;
    }
  }

  const total = tasks.length;
  const completed = byStatus["완료"];
  const riskCount = tasks.filter(isActiveRisk).length;
  const dueThisWeek = tasks.filter((task) => task.dueInDays >= 0 && task.dueInDays <= 7).length;
  const completionRate = total === 0 ? 0 : Math.round((completed / total) * 100);

  return {
    total,
    completed,
    completionRate,
    riskCount,
    dueThisWeek,
    byStatus,
  };
}

export function updateTaskStatus(tasks, taskId, status) {
  if (!STATUS_ORDER.includes(status)) {
    throw new Error(`Unknown status: ${status}`);
  }

  return tasks.map((task) => {
    if (task.id !== taskId) {
      return task;
    }

    const riskLevel =
      status === "완료" ? "낮음" : status === "위험" ? "높음" : task.riskLevel;

    return {
      ...task,
      status,
      riskLevel,
    };
  });
}

export function getRiskSummary(tasks) {
  return tasks.filter(isActiveRisk).map((task) => ({
    id: task.id,
    title: task.title,
    owner: task.owner,
    reason:
      task.dueInDays <= 0
        ? "마감일이 임박했고 위험 상태입니다."
        : "위험도가 높아 추가 확인이 필요합니다.",
  }));
}

export function getActivityMessage(previousTask, nextTask) {
  if (!previousTask || !nextTask) {
    return "작업 상태가 업데이트되었습니다.";
  }

  return `${nextTask.title}: ${previousTask.status}에서 ${nextTask.status}로 변경`;
}
