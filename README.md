# codex_subagent_1
코덱스 서브에이전트 첫 프로젝트 

## 포함된 산출물

- `2026-07-08-codex-subagent-demo-kit`: Codex 서브에이전트 역할 정의, 실행 프롬프트, 영상 구성안
- `2026-07-08-task-dashboard-demo`: 서브에이전트 결과를 통합해 보여주는 작업 관리 대시보드 데모
- `.codex/agents`: 기획자, 평가자, 개발자, 보조 개발자, 디자이너 서브에이전트 설정

## 대시보드 데모 실행

```powershell
py -3 -m http.server 8787
```

브라우저에서 엽니다.

```text
http://127.0.0.1:8787/2026-07-08-task-dashboard-demo/2026-07-08-task-dashboard.html
```

## 검증

```powershell
node 2026-07-08-task-dashboard-demo\tests\2026-07-08-dashboard-state.test.mjs
```
