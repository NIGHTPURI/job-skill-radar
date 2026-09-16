# Roadmap V2 — 작게 검증하고 계속 사용할 수 있게

상태: Phase 0·1A·1B·1C·2A·2B·2C·2D·3A 완료. **Phase 3B는 시작하지 않았다.** 아래 단계별 완료 기록이 과거 제안보다 우선한다.
근거는 [REFACTORING_AUDIT.md](REFACTORING_AUDIT.md), 목표 경계는 [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md)에 있다.

## 공통 완료 조건

- 각 단계는 독립적인 리뷰·되돌리기가 가능한 변경으로 나눈다. 구조 변경과 새 기능은 같은 변경에 묶지 않는다.
- 기존 sample CLI, unittest, sample/DB 대시보드 흐름을 계속 사용할 수 있어야 한다. 의도적 결과 변경은 전후 fixture와 사용자 설명을 남긴다.
- 영속 구조를 바꾸기 전 실제 사용 DB를 복사·백업하고 migration·복원 테스트를 한다. 코드 revert만으로 DB가 되돌아간다고 가정하지 않는다.
- 테스트는 기본적으로 외부 API·키 없이 실행한다. 실 API 검증은 별도 opt-in이고, 미실행 사항은 기록한다.
- 새로운 모델·폴더는 실제 사용하는 단계에만 도입한다. 제품 기능을 위해 필요한 정도로만 구조를 정리한다.
- 샘플은 실데이터와 구별하며, 알 수 없는 정보를 확정된 미충족으로 표현하지 않는다.

## Phase 0 — 감사와 기준선 (이번 작업)

**목표·동기**: 추정이 아닌 코드·실행 근거로 현재 능력과 한계를 확인한다.

**대상**: 저장소 전체 읽기; 새 문서 3개만 작성.

**범위**: 런타임·의존성·스키마·규칙·API parser·테스트·기존 문서 검토. production/test 코드 변경 없음.

**검증**: 기존 unittest 4개 통과, sample CLI 성공, 순수 함수/메모리 DB 경계 probe. UI 의존성 부재로 UI 실행 미검증; 실 API도 미검증.

**완료 기준**: 사실/권고/미검증을 구분한 감사, 작은 목표 구조, 단계별 로드맵 작성. git diff에 요청된 문서만 남음.

**의존성**: 없음. **위험**: 합성 데이터 결과를 실 API 품질이나 시장 대표성으로 일반화하지 않아야 한다.

## Phase 1A — 회귀 테스트만 먼저 보강

**목표·동기**: 동작을 바꾸기 전에 현재 결과와 결함을 재현 가능하게 한다. 기존 테스트는 포함 여부·행 개수 중심이다.

**예상 파일**: tests/test_core.py, tests/test_storage.py, 새 test_normalizer.py, test_work24_client.py, test_pipeline.py, test_config.py, tests/fixtures/work24/.

**범위**:

- 샘플 분석 결과·추천 점수·fallback·동점 순서의 기준선.
- 추출 경계, 직무 우선순위, 정제 손실, source 충돌, 중복 저장의 현행 동작 특성 테스트.
- XML 성공/결측/오류와 mocked HTTP 파라미터·timeout·pagination.
- 환경 로더 상태 격리, 임시 DB 경로와 연결 종료 검증.
- 의존성 설치가 허용된 환경에서 UI sample/DB smoke 실행 절차를 기록한다.

**필수 테스트**: 추가 테스트 자체가 현재 코드에서 의미 있게 실행되고 기존 4개도 통과해야 한다. 결함 재현 특성 테스트는 올바른 제품 동작으로 오해되지 않게 이름과 설명을 붙인다.

**완료 기준**: 외부 키·네트워크 없이 주요 계약을 검증하고, 이후 의도적 변경에서 바꿀 기대값을 식별할 수 있다. production code는 그대로다.

**의존성**: Phase 0 승인 후. **위험**: 현재 결함을 영구 요구사항으로 고정하거나 필요 이상으로 테스트를 구현 세부에 결합하는 것.

## Phase 1B — 기존 경계와 결과 계약 정리

**완료 기록 (2026-09-16)**: 런타임 dict 호환성을 유지하는 TypedDict `JobPosting`/`AnalysisResult`와 공유 필드 목록을 추가했다. dataclass 강제 변환은 하지 않았다. DB 연결 수명은 storage의 path 함수, 데이터 소스 선택·공통 수집 루프는 pipeline으로 모았다. optional db_path/collector로 테스트 경계를 명시했다. 기존 95개와 추가 17개를 합쳐 112개 중 107개 통과·기존 예상 실패 5개다. 스키마·taxonomy·추천 계산 및 알려진 결함은 그대로다. 실제 구조는 TARGET_ARCHITECTURE.md의 구현 현황을 따른다.

**목표·동기**: 기능·결과를 유지하며 dict 필드 중복과 UI의 소스 선택 결합을 줄인다.

**예상 파일**: models.py, pipeline.py, app.py, normalizer.py, analyzer.py, storage.py, 관련 tests.

**범위**:

- 먼저 JobPosting/AnalysisResult 등 현재 쓰는 모델만 도입한다. 필요하면 경계 adapter로 기존 반환 형식을 잠시 유지한다.
- DB 우선/빈 DB의 sample 정책을 application 함수로 이동하고 app의 표시·캐시는 유지한다.
- DB 경로와 collector를 테스트에서 명시할 수 있게 한다. 범용 DI는 도입하지 않는다.
- 수집 루프 중복을 작은 helper로 정리한다. 점수·taxonomy·schema·예외 정책은 이 단계에서 바꾸지 않는다.
- storage 추출 제거는 정합성 정책과 맞물리므로 Phase 2에서 수행한다.

**필수 테스트**: 1A 전체, old/new 분석 결과 동등성, CLI 출력·UI smoke, 정상·실패 연결 종료.

**완료 기준**: 점수·직무·공고 수가 같고 core가 Streamlit 없이 동작한다. 공고·분석 결과의 필수 필드가 한 곳에서 정의된다.

**의존성**: 1A. **위험**: 전면 dataclass 전환으로 범위가 커지는 것. 공고 모델→분석 결과→UI adapter를 별도 리뷰 단위로 나눈다.

## Phase 1C — 저장 무결성 완료 (2026-09-16)

기존 `985d7e0` 구현을 재검토하고 검증했다. `(source, posting_id)` 복합 PK, source별 중복 제거, 공고·기술의 원자적 교체, FK/CASCADE, identity 검증, `user_version=1`, v0 이전·파일 백업·실패 rollback·재실행 및 재연결, created_at 보존, 결측 경력 정규화 멱등성이 구현되어 있다. 추가 운영 코드 수정은 필요하지 않았다.

전체 140개 중 136개 통과·예상 실패 4개이며 일반 실패와 오류는 없다. migration 13개와 persistence integrity 15개가 모두 통과하고 샘플 CLI 결과도 유지된다. 상세 기록은 [테스트 기준선](TEST_BASELINE.md#phase-1c-재개-검증-2026-09-16), 최종 저장 계약은 [데이터 설계](02_data_design.md#phase-1c-현재-영속-계약)를 따른다.

아래 Phase 2는 원래 계획이다. identity·migration·최신 본문/기술 일관성은 Phase 1C에서 먼저 완료했으므로 재구현하지 않는다. surrogate ID, SQL 리소스 폴더, storage 밖으로 추출 이동은 현재 구현의 필수 조건이 아니다. 관측 이력·snapshot 등 남은 범위는 후속 작업 전에 다시 확정한다. Phase 2는 시작하지 않았다.

## Phase 2A — Skill Taxonomy and Extraction Reliability 완료 (2026-09-16)

사용자가 지정한 현재 Phase 2A는 기술 taxonomy·alias·추출·canonicalization 개선이다. 아래 원래 Phase 2/3의 번호와 범위보다 이 기록을 우선한다. 기존 저장 무결성은 Phase 1C에서 완료했으며 다시 구현하지 않았다.

- Python `skill_taxonomy.py`로 canonical·alias·유지보수 category를 분리했다. 기존 31개를 보존하고 필수 backend 39개 전체를 포함한 총 59개를 지원한다.
- 구두점/Unicode/한글 조사 경계, 짧은 약어·수량 보호, 가장 긴 명시적 근거 우선, 결정적 출력, 미등록 사용자 기술 보존을 구현했다. 자세한 정책은 [데이터 설계](02_data_design.md#phase-2a-기술-taxonomy와-추출-계약)를 따른다.
- 검증: 전체 171개 중 169 통과·무관한 예상 실패 2, 일반 실패/오류 0. 추출 파일 42개, canonicalization 9개, 소비 경로 통합 5개, migration 13개, persistence integrity 15개 모두 통과. 샘플 CLI 결과 동일, diff 공백 검사 통과.
- schema/migration/identity/저장 의미, 직무 분류, 추천 점수, UI는 변경하지 않았다. 기존 v1 DB의 기술 행을 자동 backfill하지 않는다.
- Phase 2B는 미시작이다. backend fallback, 부분 문자열 분류, Docker/Kafka 등의 기술 하나로 직무를 결정하는 현행 규칙 및 개선된 추출이 그 규칙에 미치는 영향은 후속 검토사항이다.

## Phase 2B — Role Taxonomy and Classification Reliability 완료 (2026-09-16)

현재 사용자 지정 Phase 2B는 역할 taxonomy와 결정적 규칙 기반 분류다. 과거 저장 일관성 계획의 같은 번호와 구분한다.

- `role_classifier.py`에서 Backend/Frontend/Full-stack/Data Analyst/BI/Data Engineer/ML·AI/DevOps·Cloud/Unknown의 9개 역할을 정의했다. 기존 4개 canonical label과 analyzer import 경로는 유지한다.
- 명시적 제목 → 업무·도메인 → 기술 조합 → 미분류 순서다. 구체적인 복합 구문이 내부의 일반 구문보다 우선하며, 같은 단계의 독립적인 충돌은 미분류로 처리한다. Full-stack은 명시적 근거가 있어야 한다.
- 단일 Docker/AWS/Java/SQL/Python으로 직무를 확정하지 않는다. mobile/retail/email 부분 문자열 오분류와 데이터 분석가 기본 fallback을 제거했다. 경력무관 결함은 role이 아닌 career 정제 문제이므로 유지했다.
- 전체 210개 중 208 통과·예상 실패 2, 일반 실패/오류 0. classifier 34개, analyzer 17개, 추출 42개, migration 13개, persistence integrity 15개 통과. 샘플 CLI 결과 동일, 공백 검사 통과.
- 기존 UI는 공유 역할 목록으로 확장된다. 추천 공식과 foundation은 바꾸지 않았으며 새 역할의 빈도·fallback 동작을 검증했다. schema/migration/identity/저장 의미 및 Phase 2A 기술 taxonomy·추출기는 변경하지 않았다.
- [분류 계약](02_data_design.md#phase-2b-역할-taxonomy와-분류-계약)과 [검증 기록](TEST_BASELINE.md#phase-2b-검증-2026-09-16)을 따른다. Phase 2C는 미시작이며 추천 fallback·설명·새 역할/미분류 선택 정책 등 남은 제품 범위는 별도 요청 후 확정한다.

## Phase 2C — Recommendation Reliability and Explainability 완료 (2026-09-16)

현재 사용자 지정 범위는 학습 추천의 의미·역할 근거·fallback·정렬·설명 개선이다.
아래 과거 Phase 2C 수집 관측 계획을 구현한 것이 아니다.

- 임의의 foundation 가산 점수를 제거했다. 목표 역할의 실제 기술 언급 건수와 기초 지식을
  분리하고 TypedDict로 순위·건수·역할 공고 수·기초 여부·근거 출처·설명을 반환한다.
- 8개 구체적 역할에 작은 기초 목록을 정의했다. 전체 빈도 fallback은 없으며 역할 데이터가
  없으면 기초 후보만, 미분류·미지원 역할은 빈 목록을 반환한다.
- 정렬은 역할 빈도 → 기초 여부 → canonical 이름으로 결정적이다. 보유 별칭 제외를 유지하고
  비양수 limit을 빈 목록으로 고쳤다. 합격 확률·적합도·백분율은 계산하지 않는다.
- 전체 222개 중 221 통과·예상 실패 1, 일반 실패/오류 0. 추천 24, analyzer 17,
  classifier 34, extraction 42, migration 13, persistence integrity 15, skill integration 5개 통과.
  샘플 CLI는 집계를 유지하고 추천 순위·근거만 변경했다. git diff --check와 문법 검사 통과.
- UI는 기존 배치를 유지하면서 점수를 순위로 바꾸고 데이터 부족·미분류 안내를 추가했다.
  Streamlit/Plotly 부재로 실제 화면은 미검증이다. KD-08 경력무관 예상 실패는 유지했다.
- [추천 계약](02_data_design.md#phase-2c-학습-추천-계약)과 [검증 기록](TEST_BASELINE.md#phase-2c-검증-2026-09-16)을 따른다.
  schema/migration/identity/저장·분류·추출 의미를 바꾸지 않았다. 공고별 매칭과 Phase 3는 미시작이다.

## Phase 2D 완료 기록 — Career Normalization Cleanup (2026-09-16)

경력무관을 경력보다 먼저 판정하여 무관으로 정규화하고, 결측은 미상으로 유지한다.
신입/경력 혼합 표현은 같은 이름의 문자열 범주로 보존한다. 여섯 canonical 값과
정제·저장 왕복 멱등성을 검증했다. 기존 KD-08 테스트를 정상 회귀 테스트로 전환했다.
전체 226개 모두 통과·예상 실패 0이며 샘플 CLI 출력은 동일하다.
운영 변경은 normalize_career뿐이고 저장·migration·추출·분류·추천·UI는 변경하지 않았다.
[경력 계약](02_data_design.md#phase-2d-경력-정규화-계약)과
[검증 기록](TEST_BASELINE.md#phase-2d-검증-2026-09-16)을 따른다. Phase 3는 미시작이다.

## Phase 3A 완료 기록 — Work24 Detail Ingestion (2026-09-16)

중단된 미커밋 구현을 보존하고 공식 상세 수집·원문 저장을 마쳤다. 아래 원래 Phase 3/4B 제안의
번호보다 이 사용자 지정 범위가 우선한다. 기존 기능을 처음부터 재작성하지 않았다.

- 공식 상세 endpoint/필수 인자, XML 계층·선택 필드·identity 검증, UTC fetched_at,
  nullable 원문과 결정적인 keywords, 안전한 통신/파싱 오류를 구현·검증했다.
- schema v2 posting_details는 복합 PK/FK/CASCADE다. v1의 공고·기술·created_at을 그대로
  보존하는 추가 이전, v0의 기존 변환 후 v2 도달, fresh/v2 재개방, 사전 백업·복원·실패 rollback을 검증했다.
- 성공 refresh는 최신 관측을 교체하고 실패는 이전 상세를 보존한다. 20건 중 19건 성공·1건 실패,
  한 identity당 한 요청, HTTP 중 DB 연결·write transaction 부재를 테스트했다.
- 기존 목록 전용 함수·CLI는 유지한다. `--with-details`의 부분 실패는 저장된 성공 결과와
  실패 건수를 보고하고 exit 2를 반환한다. KD-09 오류 XML의 빈 목록 오인도 해결했다.
- 전체·집중 테스트와 샘플 CLI 결과는 [검증 기록](TEST_BASELINE.md#phase-3a-검증-2026-09-16)을 따른다.
  상세 필드·백업명·오류 범주·refresh 정책은 [데이터 계약](02_data_design.md#phase-3a-상세-원문과-schema-v2-계약)에 있다.
- 추출·분류·추천·경력 정규화는 유지한다. 상세 원문은 아직 기술 추출에 사용하지 않는다.
  필수/우대·자격 해석, LLM, job-fit, 프로필·북마크·지원 추적은 이번 범위에 없다.
- 실 API smoke는 하지 않았다. 실제 키 권한·응답 변종·요청 한도는 후속 실환경 검증 사항이다.
  TTL·재시도·snapshot·영속 실패 이력·상세 UI는 도입하지 않았다. Phase 3B는 미시작이다.

## 원래 Phase 2 계획 — 저장 일관성과 수집 관측 기반 (과거 제안)

**목표·동기**: 오래된 본문과 누적 기술의 불일치를 먼저 해결하고 이후 개인 기록을 연결할 안정적인 공고 identity를 마련한다.

**예상 파일**: storage.py, migrations.py, migrations/*.sql, pipeline.py, models.py, storage/migration/pipeline tests.

**범위**:

- 2A: schema version과 백업·migration 경로, 내부 ID와 UNIQUE(source, external_id)를 도입한다. 기존 공고와 기술 참조를 보존한다.
- 2B: 동일 공고 재수집 시 원문·추출 결과를 같은 기준으로 갱신한다. 추출은 application에서 수행하고 storage에는 결과를 전달한다.
- 2C: 수집 run 범위, observed_at, content hash, 최소 snapshot을 남긴다. 원문/정규화 값과 등록일/관측일을 분리한다.
- 읽기 때 schema 보장·commit을 하는 숨은 동작을 정리한다. 샘플/실데이터 조회 범위를 구분한다.
- 스키마 이관과 갱신 정책 변경은 각각 리뷰한다. UI에는 신규/갱신/동일/실패 수의 의미를 명확히 전달한다.

**필수 테스트**: 구 schema fixture→migration→조회, 반복 migration, 실패 rollback, source ID 충돌, 중복 내용 재수집, 변경 snapshot, 삭제된 기술의 최신 결과 반영, FK, timezone, 백업 복원.

**완료 기준**: 공고 본문과 최신 기술이 같은 snapshot을 가리킨다. 기존 DB에서 정상 이관되고 실패 시 복구할 수 있다. 샘플 seed와 실 수집이 분석 범위상 구분된다.

**의존성**: 1A/1B. **위험**: ID 이관 오류·원문 저장량 증가·모든 재수집을 새 공고로 계산하는 오류. 기본 데이터 보존과 명시적 dedup 정책을 우선한다.

## 원래 Phase 3 — 기술·직무 범위 확대 (과거 제안)

**목표·동기**: backend 등 일반 개발 공고를 데이터 직무로 강제 분류하는 현재 한계를 해소한다.

**예상 파일**: taxonomy/skills.json, taxonomy/roles.json, skill_extractor.py, role_classifier.py, analyzer.py, recommender.py, app.py, sample fixtures/tests.

**범위**:

- 3A: 기존 31개 taxonomy를 데이터 파일로 옮기되 결과를 보존한다. 파일 정합성과 버전 검증을 추가한다.
- 3B: 요청된 backend 22개 전체를 지원하고 문장부호·한글·alias 경계를 개선한다. 기존 데이터/AI 기술은 유지한다.
- 3C: 7개 목표 역할과 Unknown을 추가한다. BI 호환 정책, 제목 우선순위, 모호성·근거를 명시한다.
- 새 직무의 foundation을 근거 없이 복제하지 않는다. 추천의 역할 범위와 fallback을 명확히 표시하고 기존 가산 계산과 구별한다.

**필수 테스트**: 모든 요청 backend 기술 positive fixture, Java/JavaScript 등 negative fixture, 문장 끝 기술, 중복 alias, parent/child 기술 집계, 역할별 명시 제목·복합·unknown·오분류, 기존 데이터 직군 회귀.

**완료 기준**: 각 직군을 규칙과 근거로 구별하고 미확정은 Unknown으로 남긴다. 바뀐 직무 분포·추출 수를 전후 비교할 수 있다. 규칙 버전별 재분석이 가능하다.

**의존성**: 1B 및 2의 재분석/정합성 기반. **위험**: 포괄 alias가 오탐을 늘리거나 직무 변경이 과거 수요 변화처럼 보이는 것. fixture 평가와 version 표시로 구분한다.

## Phase 4A — 수동 공고 등록과 상세 열람

**목표·동기**: Work24 상세 API의 제약과 무관하게 실제 취업 준비 공고를 등록하고 읽을 수 있게 한다.

**예상 파일**: app.py, pipeline.py, models.py, normalizer.py, storage.py, 수동 등록 tests.

**범위**: 제목·회사·URL·본문과 선택 metadata 입력, 충돌 없는 manual ID, 수정 snapshot, 상세 보기·클릭 가능한 원문 링크. 본문 확보 여부를 표시한다. URL을 입력했다고 임의로 사이트를 수집하지 않는다.

**필수 테스트**: 최소 필드·빈 본문·긴 본문·수정·반복 저장·출처 구분, 앱 재시작 후 보존, URL 표시 smoke.

**완료 기준**: API 키 없이 실제 공고를 등록·수정·재열람할 수 있고 raw text가 보존된다.

**의존성**: 2; 직무 범위는 3 적용 권장. **위험**: 같은 URL 공고를 자동 병합하거나 본문 없는 공고를 완전한 데이터로 취급하는 것.

## Phase 4B — Work24 상세 수집과 실패 처리

**목표·동기**: 목록 조합 문자열을 실제 본문으로 착각하지 않게 하고 수집 실패가 기존 공고 열람을 막지 않게 한다.

**예상 파일**: work24_client.py, pipeline.py, models.py, app.py, collect_work24.py, HTTP/XML fixtures/tests, API 계약 문서.

**범위**:

- 먼저 공식 명세·키 권한·상세 endpoint·필드·페이지/요청 제한을 확인하고 계약을 기록한다.
- 상세 접근이 가능할 때 목록→상세 경로를 구현한다. 불가능하면 list_only 상태와 수동 보완을 유지하고 이 조건부 기능은 보류 사실을 표시한다.
- API 오류 응답과 정상 빈 결과 구분, 제한된 재시도/백오프, 요청 timeout, 페이지 종료 기준, 부분 성공 수집 결과, key redaction.
- 이전 저장 데이터를 계속 표시하면서 수집 실패를 안내한다. 신규/갱신/실패를 구분한다.

**필수 테스트**: 성공·본문 누락·API error XML·잘못된 XML·timeout·HTTP failure·재시도 소진·페이지 종료·키워드 중복·부분 성공, secret 미노출. 실 API는 별도 opt-in 검증.

**완료 기준**: 원문 provenance와 detail 상태를 확인할 수 있고 실패에도 앱의 기존 DB 열람이 가능하다. 상세 미확보 공고를 완전한 요건 공고로 취급하지 않는다.

**의존성**: 2, 4A fallback 경로 권장. **위험**: 외부 API 권한/필드가 기대와 다름. 확인 전 상세 필드를 가정하지 않는다.

## Phase 4C — 요건 추출과 데이터 품질 표시

**목표·동기**: 단순 기술 언급을 필수 역량으로 잘못 계산하지 않게 한다.

**예상 파일**: requirement_extractor.py, models.py, skill_extractor.py, pipeline.py, storage.py/migration, 상세 UI, fixtures/tests.

**범위**: 섹션 규칙으로 responsibilities/required/preferred/unspecified 구분, 기술·비기술 요건의 원문 근거, 연차·학력·지역·고용형태·급여의 원문과 해석 상태. 해석 불가를 unknown으로 남긴다. 처음부터 모든 형식을 파싱하려 하지 않는다.

**필수 테스트**: 수동 검토된 다양한 공고 fixture, 섹션 없는 본문, 부정·우대·필수 혼합, 줄바꿈/HTML 유래 텍스트, 결측·연차 범위, 재처리 버전.

**완료 기준**: UI에서 추출 요건과 원문 근거를 대조할 수 있고 미수집/미해석/확인된 없음이 구분된다. 작은 평가 세트의 오류 사례를 기록한다.

**의존성**: 3 + 4A(4B가 제공되면 함께 사용). **위험**: 잘못된 섹션 분류가 점수의 신뢰도를 훼손함. 애매한 결과를 확정하지 않는다.

## Phase 5 — 로컬 프로필과 선호 저장

**목표·동기**: 매번 입력하는 보유 기술·목표 직무를 지속 데이터로 만든다.

**예상 파일**: models.py, storage.py/migrations, pipeline.py, app.py, profile tests.

**범위**: 단일 프로필, canonical user skills, 복수 target roles, 지역·고용형태·경력 관련 제약과 선호의 구분, profile revision, 수정 UI. 숙련도는 의미를 정의할 수 있을 때만 추가한다. 로그인/다중 사용자 기능은 제외한다.

**필수 테스트**: 저장/수정/재실행, alias 정규화, unknown skill 처리, 미입력과 제약 없음 구분, profile revision, migration.

**완료 기준**: 앱을 다시 실행해도 설정이 유지되고 수동/수집 공고와 같은 기술·직무 ID 체계를 사용한다.

**의존성**: 2/3; 4와 별도 리뷰 가능. **위험**: 모든 선호를 강제 조건으로 취급하거나 숙련도를 검증된 능력으로 간주하는 것.

## Phase 6 — 설명 가능한 공고 비교

**목표·동기**: 시장 빈도 추천과 구별되는 개인별 공고 적합도 결과를 제공한다.

**예상 파일**: matcher.py, models.py, pipeline.py, app.py, 선택적 match persistence, tests/fixtures.

**범위**:

- 6A: 점수에 앞서 required/preferred별 일치·미보유·판단불가와 제약 검토를 표시한다.
- 6B: 검토 가능한 규칙 문서에서 가중치·분모·결측 처리·반올림·constraint 처리·버전을 확정한 뒤 숫자를 추가한다.
- 점수마다 구성 항목·원문 근거·사용 profile revision/posting snapshot을 표시한다. 근거가 부족하면 점수 보류와 이유를 반환한다.
- 합격 확률 표현은 금지하고 기존 학습 추천 점수와 명칭을 분리한다.

**필수 테스트**: 정확한 계산 예시, empty/unknown, required vs preferred, 조건 충족/미충족/판단불가, 입력 순서 독립성, 중복 요건, profile·공고 변경 시 재계산, 설명 합계와 점수 일치.

**완료 기준**: 사용자가 점수의 모든 기여 항목과 판단불가 항목을 확인할 수 있다. 수동 검토 fixture에서 기대한 비교와 일치하며 본문 부족을 낮은 적합도로 오인하지 않는다.

**의존성**: 4C/5. **위험**: 거짓 정밀도, 편향된 공고 추출. 숫자보다 근거 목록을 우선한다.

## Phase 7 — 관심 공고와 지원 관리

**목표·동기**: 분석 결과가 실제 취업 준비 행동과 연결되도록 한다.

**예상 파일**: models.py, storage.py/migrations, pipeline.py, app.py 또는 실제로 커지면 UI 파일 분리, tracking tests.

**범위**: 북마크, 지원 단계, 지원일, 메모, 단계 이력, 필터·원문 링크. 단계 목록은 사용자의 실제 흐름에 맞는 작은 기본값으로 시작한다. 자동 지원·외부 메시지 전송은 포함하지 않는다.

**필수 테스트**: 북마크 idempotency, 단계 전환/이력, 메모 persistence, 공고 갱신 후 참조 유지, 빈 상태, UI 저장 후 표시 일치.

**완료 기준**: 재실행 후 관심 공고와 지원 진행을 이어서 관리할 수 있다.

**의존성**: 2/4A/5. Phase 6 완료를 반드시 기다릴 필요는 없다. 승인된 구현 순서 안에서 독립 변경으로 앞당길 수 있다.

**위험**: 공고 재수집이 사용자 메모·상태를 덮어쓰는 것. 수집 데이터와 사용자 기록의 쓰기 경계를 분리한다.

## Phase 8 — 반복 관측 수요와 학습 우선순위

**목표·동기**: 현재 빈도와 증가 추세를 구별하고 내 gap에 실제 수요 근거를 더한다.

**예상 파일**: analyzer.py, recommender.py, storage queries, models.py, app.py, 시계열 fixtures/tests.

**범위**:

- 8A: 동일 source·role·키워드/수집 정책·기간에서 중복 없는 공고 분자/분모를 집계한다. 부분 실패·표본 부족·taxonomy 변경을 표시한다.
- 8B: 비교 가능한 기간의 빈도/비율 변화와 내 목표 공고 gap을 분리해 제시한 후, 명시적 계산 규칙으로 학습 우선순위를 연결한다.
- 반복 수집하지 않은 과거 기간을 복원한 것처럼 표시하지 않는다. sample은 실제 시장 추세에서 제외한다.
- 자동 스케줄러는 수동 반복 수집이 안정적으로 동작한 뒤 필요하면 추가한다.

**필수 테스트**: 동일 공고 반복 관측, 신규/변경/마감 공고 정책, 표본 0·작은 표본, 수집 실패·범위 변경, taxonomy version, 비율 분모, 계산 근거·추천 순서.

**완료 기준**: 추세 그래프와 추천마다 기간·출처·표본 수·계산식을 확인할 수 있다. 부족한 데이터에서는 증가 기술 추천을 보류한다.

**의존성**: 2의 관측 이력이 실제로 충분히 누적되어야 함; 3/5/6의 gap 계약. **위험**: 수집량 증가를 시장 수요 증가로 혼동하는 것. 일정만 지났다고 완료 처리하지 않는다.

## Phase 9 — 사용성·운영 정리

**목표·동기**: 지속적인 로컬 사용과 복구를 쉽게 한다. 앞 단계의 최소 오류 안내와 UX를 이 단계까지 미루지는 않는다.

**예상 파일**: app/UI, config.py, scripts/, requirements*, README.md, 기존 docs, tests, 필요 시 CI 설정.

**범위**: 실사용 피드백에 따른 화면·검색·필터 정리, cache revision, `.env` 갱신/실행 안내, DB backup/export/restore, 검증된 의존성 재현 방법, 쓰이지 않는 패키지 검토, 최소 자동 회귀 실행. 실제 UI 성능 측정 후 필요할 때만 조회 최적화.

**필수 테스트**: 깨끗한 환경의 설치·CLI·UI smoke, 키 없는 수동 사용, backup/restore, 외부 CLI 저장 후 캐시 갱신, 마이그레이션 포함 실행 안내 재현.

**완료 기준**: 다른 로컬 PC에서 문서대로 실행하고 데이터를 복구할 수 있다. 정상 사용·실패 복구 흐름과 미검증 환경을 문서로 확인할 수 있다.

**의존성**: 각 기능 단계; 운영상 작은 개선은 해당 단계에서 함께 수행 가능. **위험**: 배포·플랫폼 전환이 개인 사용 가치보다 앞서는 것.

## 바로 다음 작업 제안

**Phase 3A는 완료했다. Phase 3B는 시작하지 않는다.** 후속 요청에서 상세 원문을 사용할 범위와
해석 계약을 확정해야 한다. 원문·미수집·실패·선택 필드 결측을 구별하고, raw 경력과 normalized
career의 우선순위를 조용히 도입하지 않는다. 최초 DB 이전은 다른 writer를 중지한 상태에서
수행하고 백업·복원 절차는 데이터 설계를 따른다.

Phase 1C 저장 무결성, Phase 2A 추출, Phase 2B 분류, Phase 2C 추천 회귀 테스트가 현재 기준선이다. 추천은 학습 후보 순서이며 공고별 적합도가 아니다. 후속 소비자는 제거된 score 키 대신 명시적 근거 계약을 사용해야 한다. FastAPI/React/PostgreSQL 전환은 이 로드맵의 목표가 아니다.
