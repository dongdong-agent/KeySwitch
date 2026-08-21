# KeySwitch 🔑

> **API 키 관리자** — 각 앱에 Provider의 키를 독립적으로 지정하고, 사용량이 소진되면 우선순위에 따라 자동 전환합니다.
> **Pi(AI 코딩 어시스턴트) + DeepSeek V4 Flash**로 엔드투엔드 개발되었습니다.

🌐 언어 : [简体中文](README.md) · [English](README.en.md) · [Français](README.fr.md) · **한국어**

---

## 이게 뭔가요

KeySwitch는 이런 문제를 해결합니다: 여러 AI Provider의 여러 API 키를 서로 다른 앱(Pi, Codex, OpenChatCut, WorkBuddy 등)에서 사용하는데, 키의 할당량이 소진되면 매번 각 앱의 설정을 손으로 고쳐야 합니다.

KeySwitch가 이를 자동화합니다:

- **앱별 독립 설정** — 어떤 Provider와 키를 쓸지 지정
- **백그라운드 주기 검사** — 사용 중인 키의 사용량을 확인하고, 임계값에 도달하면 다음 사용 가능한 키로 자동 전환
- 키 하나가 전환되면 **그 키를 쓰는 모든 앱이 함께 전환**됩니다 — 일일이 수정할 필요가 없습니다

Rust / Tauri 2 재작성 버전(Python 버전 `L:\00-projects\apikey-switcher` 대체).

---

## ✨ 기능

- **왼쪽 내비게이션 + 오른쪽 작업 영역**(OneWork 스타일, 보라색 테마): 개요 / 키 매트릭스 / Provider / 키 풀 / 앱 / 설정
- **앱별 매핑**: 앱 × Provider 표, 각 셀에 자체 키 드롭다운. "저장 및 적용"은 변경된 셀만 기록(쓰기 전 자동 백업)
- **스마트 전환**: 백그라운드 타이머가 사용 중인 키의 사용량을 확인하고, 임계값(기본 100%)에서 우선순위가 가장 높은 사용 가능한 키로 자동 전환, 그 키를 쓰는 모든 앱을 함께 전환
  - **3차원 판정**: 롤링 / 주간 / 월간 — **어느 하나라도** 임계값 도달 시 키 소진으로 판정
  - **크로스 Provider 폴백**: 같은 Provider에 사용 가능한 키가 없으면 `prefer_providers` 순서대로 다른 Provider로 폴백(예: opencode-go 우선, DeepSeek 예비)
  - **쿼리 실패 보호**: 사용량 쿼리가 실패한(403/네트워크) 키는 전환 후보에서 제외됩니다. 사용 중인 키가 쿼리에 실패하면 **이번 라운드에서 쿼리에 성공한** 키로 전환(같은 Provider 우선, 없으면 크로스 Provider), 사용 가능한 대상이 전혀 없을 때만 현재 상태를 유지합니다
- **우선순위 정렬**: 키 풀에서 ↑↓로 재정렬(목록 순서 = 우선순위)
- **셀프 서비스 관리**: UI에서 Provider, API 키, 앱을 직접 추가/삭제
- **키 편집**: Provider / 식별자 / 값 / 메모 / 추천 링크 / 보상 금액 변경; 크로스 Provider 이동 시 앱 매핑 자동 동기화
- **식별자 마스킹**: 이메일 등 식별자는 편집 모드가 아닐 때 `앞4자***@도메인`으로 표시, 편집 시 전체 표시
- **사용량 시각화**: 개요 카드에 롤링/주간/월간 3개 진행 바 + 각 차원의 리셋 카운트다운(`X일 X시간 후 리셋`)
- **시스템 트레이**: 왼쪽 클릭/메뉴로 메인 창 열기, 메뉴에 사용량 스냅샷 + 스마트 전환 상태 표시; 창 닫기 = 트레이로 숨김(종료 아님)
- **사용량 감지**: opencode-go `/usage`(percent), DeepSeek `/user/balance`(balance)

---

## 📦 설치

릴리스 설치 프로그램(Windows)을 다운로드하세요:

| 형식 | 파일 | 비고 |
|---|---|---|
| NSIS 설치 프로그램 | `KeySwitch_0.3.1_x64-setup.exe` | 더블 클릭 설치, 제거 프로그램 포함 |
| MSI 패키지 | `KeySwitch_0.3.1_x64_en-US.msi` | 기업 배포용 |

설치 후 시스템 트레이에 상주합니다.

---

## 🚀 빠른 시작

> 처음 사용 시 아래 순서대로 진행하면 약 5분이면 설정됩니다.

1. **(선택) Python 버전에서 마이그레이션**: `python tools/migrate_config.py`로 기존 설정을 한 번에 가져옵니다.
2. **Provider 추가**: "Provider" 페이지 → 이름, `base_url`, 사용량 유형(`percent` 백분율 / `balance` 잔액) 입력.
3. **키 추가**: "키 풀" 페이지 → 식별자, 키 값, 선택적으로 메모/추천 링크/보상 입력; ↑↓로 우선순위 조정.
4. **앱 추가**: "앱" 페이지 → 어댑터 선택 → 매개변수 입력 → 이 앱에서 각 Provider가 쓸 키 지정.
5. **저장 및 적용**: "키 매트릭스" 페이지에서 앱 × Provider 표 확인 → "저장 및 적용" 클릭(변경된 셀만 기록, 자동 백업).
6. **스마트 전환 활성화**: "개요" 페이지 → 임계값/검사 간격/선호 Provider 순서 설정 → 활성화.

이후 트레이 상주 백그라운드 검사기가 알아서 처리합니다. 전환 후에는 **해당 앱을 재시작**해야 새 키가 적용됩니다(아래 주의사항 참조).

---

## 🔌 지원 어댑터(8종)

KeySwitch는 "어댑터"로 키를 각 앱의 실제 설정 위치에 기록합니다:

| 어댑터 | 대상 앱/위치 | 필수 매개변수 |
|---|---|---|
| `pi` | Pi 도구(`~/.pi/agent/auth.json`) | 없음 |
| `env_var` | Windows 사용자 환경 변수 | `env`(변수명, 기본 `OPENCODE_GO_API_KEY`) |
| `openchatcut` | OpenChatCut(`.env.local`) | 없음 |
| `workbuddy` | WorkBuddy(`models.json`) | 없음 |
| `codex` | Codex(codex-router secret 파일) | 없음 |
| `file_json` | 임의 JSON 설정 파일 | `path` + `key_path`(점 경로, 예: `opencode-go.key`) |
| `file_env` | 임의 `KEY=VALUE` 파일(.env 계열) | `path` + `key_name`(기본 `API_KEY`) |
| `file_regex` | 임의 파일 정규식 치환 | `path` + `pattern`(캡처 그룹 1개) + `replacement`(기본 `\1{key}\2`) |

---

## 🔄 스마트 전환 메커니즘

- **트리거**: 타이머가 30초마다 틱하고, `interval_min`(기본 5분)에 따라 검사 여부를 결정합니다. 사용 중인 키는 롤링/주간/월간 **어느 하나라도** `trigger_percent`(기본 100%) 이상이면 소진으로 판정합니다.
- **전환 대상**: 같은 Provider 내에서 키 풀 우선순위(목록 순서)로 첫 번째 사용 가능한 키 선택; 없으면 `prefer_providers` 순서대로 크로스 Provider 폴백.
- **일관성**: 키가 전환되면 `mapping`에서 그 키를 참조하는 모든 앱이 함께 전환됩니다.
- **오전환 방지**: 쿼리에 실패한(403/네트워크) 키는 전환 후보에서 항상 제외됩니다(죽은 키로 전환 방지). 사용 중인 키가 쿼리에 실패하면 이번 라운드에서 쿼리에 성공한 키로 전환(같은 Provider 우선, 없으면 크로스 Provider), 사용 가능한 대상이 없을 때만 현재 상태를 유지합니다.
- **로그**: 각 자동 검사는 `%APPDATA%\KeySwitch\auto-switch.log`에 한 줄씩 기록되어 타이머가 돌고 있는지 확인할 수 있습니다.

---

## ⚙️ 설정 파일

- 경로: `%APPDATA%\KeySwitch\config.toml`(UI가 자동 기록, 수동 편집도 가능)
- 주요 섹션:

```toml
[auto_switch]
enabled = true          # 스마트 전환 활성화
interval_min = 5        # 검사 간격(분)
trigger_percent = 100   # 트리거 임계값(%)
prefer_providers = ["opencode-go", "deepseek"]  # 크로스 Provider 폴백 순서(선택)

[providers.opencode-go]
base_url = "https://api.opencode.ai"
usage_type = "percent"  # percent | balance
```

- 키별 선택 필드: `note`, `promo_url`, `reward`.
- 앱(`targets`)별 선택 필드: `label`, `adapter`, 어댑터 매개변수(`env`/`path`/`key_path`/`key_name`/`pattern`/`replacement`), `mapping`.

---

## 🛠 기술 스택 & 개발 방식

| 계층 | 기술 |
|---|---|
| 프론트엔드 | React 18 + TypeScript + Vite(`src/`) |
| 백엔드 | Rust + Tauri 2(`src-tauri/`) |
| 설정 | TOML(`%APPDATA%\KeySwitch\config.toml`) |

> **개발 방식**: 이 프로젝트는 **Pi(AI 코딩 어시스턴트) + DeepSeek V4 Flash**로 엔드투엔드 개발되었으며, 각 계층에서 "첫 원리 + 대립적 검토" 공학 방법론을 적용했습니다.

---

## 🧪 개발 & 빌드

```bash
# 의존성 설치
npm install
# 프론트엔드 개발(핫 리로드)
npm run tauri dev
# 프론트엔드 타입 체크
npx tsc --noEmit
# 백엔드 빌드 + 단위 테스트
cd src-tauri && cargo build && cargo test
# 패키징(NSIS / MSI)
npx tauri build
```

설치 프로그램 출력:

- `src-tauri\target\release\bundle\nsis\KeySwitch_0.3.1_x64-setup.exe`
- `src-tauri\target\release\bundle\msi\KeySwitch_0.3.1_x64_en-US.msi`

> 앱 아이콘 원본은 저장소 루트의 `app-icon.svg`(보라색 배경의 금색 키)입니다. 수정 후 `npx tauri icon app-icon.svg`로 모든 플랫폼 아이콘을 재생성하세요.

---

## ⚠️ 주의사항(교훈)

1. **새 opencode-go 키는 중국 호스팅 모델 opt-in 필요**: 일부 새 계정은 deepseek-v4-flash 호출 시 `403 RegionError`가 발생합니다 — 오류의 workspace 링크(`opencode.ai/workspace/<id>/go`)를 브라우저에서 열어 동의하세요.
2. **전환 후 앱 재시작 필요**: KeySwitch는 설정 파일/사용자 환경 변수를 수정합니다. **이미 실행 중인 프로세스**(PI / DSH / 앱)는 시작 시 로드한 이전 키를 유지하므로, 재시작해야 새 키가 적용됩니다.
3. **Tauri 인자 이름 규칙**: `invoke` 매개변수는 camelCase(백엔드 `key_id` ↔ 프론트엔드 `keyId`); **명령 반환 필드는 snake_case**(프론트엔드는 `weekly_reset`을 써야 함, `weeklyReset` 아님) — 방향이 반대이니 혼동하지 마세요.
4. **사용량 API가 실제 한도와 다를 수 있음**: opencode-go의 `/usage` 백분율이 실제 사용 가능을 보장하지 않으며(429/403 가능) Cloudflare가 간헐적으로 차단합니다. KeySwitch는 이번 라운드에서 쿼리에 실패한(403/네트워크) 키를 전환 후보에서 제외하고, 사용 중인 키가 쿼리에 실패하면 쿼리에 성공한 키로 전환(같은 Provider 우선, 없으면 크로스 Provider)하며, 사용 가능한 대상이 없을 때만 현재 상태를 유지합니다.
5. **WebView 저장소에 설정을 두는 앱(예: DSH)**: provider/key가 내부 leveldb에 있어 파일처럼 수정할 수 없습니다 — 해당 앱 UI에서 직접 추가하세요.

---

## 📄 라이선스

[MIT](LICENSE) © 2026 DongDong

## 🔗 저장소

GitHub: [dongdong-agent/KeySwitch](https://github.com/dongdong-agent/KeySwitch)(main 브랜치)
