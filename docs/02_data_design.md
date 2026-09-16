# 데이터 설계

## Phase 7B 실행 이력·schema v4 (2026-09-17)

7A의 비영속 실행 한계를 대체한다. `discovery_runs`는 run_id TEXT PK, source=work24,
profile_revision, UTC started_at/completed_at, completed/partial/failed status, report JSON이다.
report에는 검색 계획/예산/집계/안전한 실패 category가 있으며 인증키·예외 문자열·응답 본문은 없다.
`discovery_run_postings`는 PK(run_id,source,posting_id), was_new 0/1, queries JSON을 저장한다.
run FK는 DELETE CASCADE, 공고 복합 FK는 DELETE RESTRICT다. 과거 소속/집계가 공고 삭제로
조용히 달라지는 것을 막는다. 수동 공고 FK/상세 CASCADE는 기존 그대로다. 삭제 UI는 없다.

NEW는 이 실행 저장 직전 같은 identity가 로컬 DB에 없었다는 뜻이다. 고용주 등록일이나 오늘
게시 여부가 아니다. BEGIN IMMEDIATE 안에서 신규 판정→공고/상세→실행/소속을 원자적으로
저장한다. 멤버십 저장 실패도 전체 rollback한다. HTTP는 그 전에 끝나며 동시 수집이 먼저
저장한 identity는 KNOWN이다. 회원가입/전체 프로필 복사/시장 snapshot/파생 요건 저장은 없다.
latest는 completed_at DESC, run_id DESC로 결정한다. 이력 조회는 기본20·최대100 실행이다.
공고는 identity당 한 행이고 실행 소속은 실행당 한 행이다. 실행 기록은 의도적으로 누적된다.
현재 상세와 현재 프로필을 사용한 비교는 과거 실행 당시의 비교 snapshot이 아니다.

v3→v4는 두 테이블/최근 완료 index만 추가한다. fresh/v0/v1/v2/v3→v4와 v4 재개방을 지원한다.
기존 공고·기술·raw 상세·profile revision/preferences·created_at/fetched_at은 보존한다.
v0 기술 재구성은 기존 정책을 유지한다. 파일 이전 전에 pre-v4-from-vN-고유값.bak을 만들고
실패 시 중단, 마지막 DDL 실패는 schema/version/data 모두 rollback한다. fresh/memory/current
DB는 백업하지 않고 기존 백업을 덮어쓰지 않는다. 이전 앱/다른 writer 종료 후 첫 실행한다.


## Phase 7A 자동 검색 코어 (2026-09-17)

사용자 정의 Phase 7은 자동 공고 발견이며 과거 지원 추적 번호를 대체한다. schema v3 유지,
추출기 v2·시장 analyzer/recommender·raw 상세 계약은 변경하지 않는다.
DiscoveryPlan은 status/target_roles/queries(keyword,target_roles), DiscoveryRun은 UUID,
UTC 시작/종료, profile_revision, 계획·요청 예산·성공/실패/재사용/미수집 수와 공고 소속을 갖는다.
소속에는 source/posting_id, 발견한 모든 queries, was_new가 있다. 7A 반환 실행은 아직 영속화하지
않고 공고·성공 상세만 원자적으로 저장한다. 7B에서 실행 이력을 추가할 예정이다.

질의는 기존 canonical 직무 순서로 합치고 중복 제거한다. 보유 기술·선호/필수 지역은 검색
필터로 사용하지 않는다. 기술 gap과 지역 정보가 부족한 후보를 검색 단계에서 숨기지 않기 위함이다.
검색어는 keyword 문자열이며 공백/언어의 정확한 검색 엔진 의미·실제 recall은 검증하지 않았다.

| 직무 | 검색어 |
|---|---|
| 데이터 분석가 | 데이터 분석, data analyst |
| 데이터 엔지니어 | 데이터 엔지니어, 데이터 파이프라인 |
| ML 엔지니어 | 머신러닝, AI 엔지니어 |
| BI 분석가 | BI 개발, BI 분석 |
| 백엔드 엔지니어 | 백엔드, 서버 개발 |
| 프론트엔드 엔지니어 | 프론트엔드, frontend |
| 풀스택 엔지니어 | 풀스택, fullstack |
| DevOps / 클라우드 엔지니어 | DevOps, 클라우드 엔지니어 |

최대 16질의, 기본 질의당 1페이지×20건·상세20회. 허용 상한은 2페이지×50건·상세50회로
전체 목록 최대32회+상세50회다. 공식 rate limit이라는 뜻이 아닌 앱 자체 예산이다.
[공식 목록 API 안내](https://www.work24.go.kr/cm/e/a/0110/selectOpenApiSvcInfo.do?fullApiSvcId=000000000000000000000000000000)의
기존 L/keyword/startPage/display 요청 계약을 재사용한다. 순차 요청이며 재시도는 없다.
질의 도중 페이지가 실패하면 그 질의는 실패로 처리하고 다른 질의 결과는 보존한다.
실패는 안전한 category만 남기며 URL/authKey/응답 본문/예외 문자열은 넣지 않는다.

성공 상세는 기본 재사용한다. 새 공고→상세 없는 기존 공고→명시적 refresh 기존 상세 순으로
예산을 배분하고 각 우선순위 안에서는 질의/응답 순서를 유지한다. 중복 identity 상세 호출은
최대1회다. 실패도 예산을 소모하며 예산 미수집은 details_deferred로 별도 표시한다.
모든 HTTP는 DB 연결 없이 수행한다. 마지막 짧은 transaction에서 신규 여부를 직전 존재 여부로
판정하고 공고/성공 상세를 함께 저장한다. 실패 상세는 기존 원문을 교체하지 않는다.
completed는 모든 질의/시도 상세 성공(빈 결과 허용), partial은 일부 요청 실패,
failed는 모든 질의 실패다. 예산에 따른 의도적 미수집은 partial 실패가 아니다.


## Phase 6A 설명 가능한 공고 비교 (2026-09-17)

현재 완료 범위는 Phase 4A·5·6A다. 아래 이전 기록의 미시작 문구는 당시 경계다.
`matcher.compare_profile_to_requirements(profile, extraction, posting_role=...)`는 순수 함수다.
HTTP·SQLite·UI 상태·LLM을 사용하지 않고 입력을 수정하지 않는다. 결과도 입력 근거와 별개
객체로 반환한다. 점수·비율·확률·후보 순위·전체 적합/부적합 verdict는 없다.

`JobComparison`은 profile_revision, extractor_version, source/posting_id, detail_fetched_at,
quality_status와 required/preferred/responsibilities/groups/review/conditions를 갖는다.
posting_role/role_alignment는 목표 직무 포함 여부만 표시하며 요건 판정을 바꾸지 않는다.
현재 검토한 extractor version 2 계약만 허용하고 새 의미 버전은 검토 없이 소비하지 않는다.

| 근거 | 프로필 등록 | 미등록 |
|---|---|---|
| 독립 required | matched | profile_missing |
| 독립 preferred | matched_preferred | profile_missing_preferred |
| responsibility | profile_has | profile_not_listed |
| unspecified | 판단 필요 근거 | 판단 필요 근거 |

미등록은 실제로 모른다는 주장이 아니다. 부정/미분류 근거는 required gap으로 승격하지 않는다.
독립 분류는 **independent 근거 안에서** 기존 required > preferred > responsibility > unspecified
우선순위를 적용한다. all_of/any_of 근거만 있는 기술은 독립 결과 목록에 다시 넣지 않는다.
원문 검토 화면도 같은 projection으로 그룹 중복 표시를 피한다. 그룹과 별도로 있는 진짜 독립
근거는 유지한다. 예: required all_of(Java,SQL) + 독립 Java preferred는 그룹 하나와 우대 항목
하나이며 Java를 독립 required로 승격하지 않는다. 원래 추출 결과 자체는 변경하지 않는다.

all_of는 전부 등록=satisfied, 일부=partially_satisfied, 전부 미등록=not_satisfied_from_profile.
any_of는 하나 이상 등록=satisfied, 전부 미등록=not_satisfied_from_profile이며 부분 충족 상태는
없다. 각 그룹에 등록/미등록 구성원, requirement_type, 원문 evidence를 보존한다. preferred
그룹은 우대이지 필수 위반이 아니다. unspecified 그룹은 보유 기술이 있어도 unknown이며
responsibility 그룹은 context_only다. 반복 원문 위치는 그대로 유지하고 논리식을 축약하지 않는다.

서로 다른 분류의 근거, 긍정·부정 공존, 미분류/미매핑 근거는 review에 별도로 노출한다.
기술 결과에는 약한 근거와 그룹 근거까지 원래 전체 provenance가 남는다. 서로 다른 문장 간
논리적 충돌을 자동 해결하지 않으며, 대표 분류와 원문을 함께 검토해야 한다.
네 quality_status는 그대로 전달한다. 상세 없음/요건 근거 미검출/미분류 상태는 정보 부족이지
완벽한 일치가 아니다. 빈 required 목록에도 성공 verdict를 만들지 않는다.

비기술 조건 중 프로필이 선언한 지역만 제한적으로 비교한다. work_region 원문 전체를 trim한
값이 정확한 단일 지원 시·도 label일 때만 판단한다. 예: 서울/부산은 비교 가능하지만
서울 강남구, 서울 또는 경기, 재택, 미제공은 unknown이다. substring/통근/지리 추론은 없다.
필수 지역은 satisfied/not_satisfied/unknown, 선호 지역은 preference_match/preference_mismatch/
unknown이며 동시에 설정돼도 별도 결과다. 경력·학력·고용 형태와 미설정 조건은 raw와 unknown을
보존한다. 기존 normalized career만으로 사용자의 연차·학위·취업 자격을 추정하지 않는다.

pipeline.load_posting_comparison은 저장 프로필과 선택 공고의 원문을 읽고 연결을 모두 닫은 뒤
추출/비교한다. 결과는 영속화하지 않는다. profile revision·성공 상세 갱신·수동 본문 수정 후
조회하면 최신 결과를 재계산하며 실패 refresh/비교 오류는 원문이나 프로필을 지우지 않는다.
**schema v3 유지, v4 없음, extractor v2 유지**. 시장 analyzer/recommender 규칙도 그대로다.

UI의 ‘내 프로필과 비교’에서 필수/우대/업무/그룹/판단 필요/기타 조건과 정확한 근거를 확인한다.
그룹은 단일 조건으로 표시하며 ‘실제로 기술을 모른다’고 표현하지 않는다. 실공고 추출 정확도는
아직 측정하지 않았고 비교는 저장된 자기 선언과 제한된 규칙 근거에 의존한다. Phase 6B는 없다.

## Phase 5 로컬 프로필·schema v3 (2026-09-17)

현재 schema는 **v3**다. 아래 v2 설명은 이전 단계 당시 기록이며 공고/raw 계약 자체는 유지한다.
개인 프로필은 공고와 다른 수명의 데이터라 기존 공고 행에 넣지 않고 singleton `user_profile`
테이블 하나를 추가했다. singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER
NOT NULL CHECK(revision>=1), owned_skills/target_roles/preferred_regions/required_regions의
NOT NULL JSON 배열 TEXT 네 개다. 계정·사용자 ID·프로필 이력·ORM은 없다.

보유 기술은 기존 canonicalize_skills를 재사용한다. 알려진 alias는 통합하고 미지원 기술은
원래 철자로 보존·표시한다. 목표 직무는 Unknown을 제외한 기존 역할에서 하나 이상 선택한다.
네 목록은 의미상 집합으로 정렬·중복 제거한다. 순서·중복·알려진 alias 변경은 revision을 바꾸지
않고, 의미가 바뀌면 원자적으로 1 증가한다. 최초 저장은 1이다. 동시 저장은 SQLite write lock으로
직렬화하며 마지막으로 저장한 전체 프로필이 현재값이다. 미지원 기술의 철자 변경은 별도 변경이다.

지역 **선호**와 **필수 조건**은 독립 목록이다. 각 목록의 복수 값은 그중 한 지역, 빈 목록은
해당 선택/제약을 선언하지 않은 상태다. 지원 시·도 label만 받는다. 공고 지역을 fuzzy 변환하거나
통근·재택·지역 포함 관계를 추측하지 않는다. 고용 형태·연차·학위 조건은 이번 프로필에 없다.
향후 비교는 원문에 정확한 단일 시·도명이 있을 때만 확정하고 나머지는 unknown이어야 한다.

v2→v3는 프로필 테이블만 추가하고 공고·기술·상세·created_at·fetched_at을 재작성하지 않는다.
fresh→v3, v0→v1→v2→v3, v1→v2→v3, v2→v3를 한 migration transaction으로 지원한다.
v0의 기술 재구성 정책은 기존 그대로다. 마지막 DDL 실패까지 이전 schema/data/version으로
rollback한다. 알 수 없는 기존 user_profile 테이블은 덮어쓰지 않고 거절한다.

파일 이전 전에 `<DB>.pre-v3-from-vN-<unique>.bak`을 SQLite backup API로 만든다. from-vN은
백업에 들어 있는 schema다. 실패하면 migration을 중단하고 새 불완전 파일만 제거한다.
fresh/in-memory/current v3는 migration 백업이 없고 재시도도 기존 백업을 덮어쓰지 않는다.
최초 이전은 다른 writer/이전 앱을 종료한 뒤 수행한다. v2 앱으로 되돌릴 때는 v3 DB를 그대로
열지 말고 앱을 모두 종료한 상태에서 이전 백업의 복사본을 복구·검증해야 한다.

pipeline.load_profile/save_profile → profile_storage 경계를 사용한다. validation·alias 정규화는
순수 profile 모듈에 있다. UI는 ‘내 프로필’에서 저장/재시작/수정하며 SQL을 실행하지 않는다.
시장 학습 추천은 저장 프로필을 초기 입력으로만 사용하고 임시 수정은 프로필에 저장하지 않는다.
시장 집계 캐시는 DB 경로도 key에 포함한다. 원문·요건 추출기 v2·그룹·시장 추천 규칙은 그대로다.

## Phase 4A 수동 공고 계약 (2026-09-17)

최신 기능은 수동 등록·목록·상세·수정이다. 아래 이전 Phase의 미구현 표시는 당시 기록이다.
`manual` source와 UUID identity를 사용하며 같은 제목/회사도 별도 공고다. 생성 시 충돌을 거절하고
수정은 기존 manual identity만 허용한다. Work24 소유 공고는 수정 API와 UI 모두에서 보호한다.
필수 입력은 company/title/body, 선택 입력은 URL·지역·경력·학력·마감일 원문이다.
본문은 description에 넣지 않고 posting_details.job_content에 공백·줄바꿈까지 보존한다.
선택 원문은 해당 detail 필드에 두고 목록의 지역/경력만 기존 정규화를 사용한다. 미입력 상세는
None/빈 keywords이며 Work24 전용 값을 생성하지 않는다. manual의 fetched_at은 HTTP 관측이
아닌 성공한 로컬 원문 capture/update UTC 시각이다. created_at과 identity는 수정해도 유지한다.

schema v2를 그대로 쓴다. 저장 경계가 schema 확인 후 BEGIN IMMEDIATE로 존재/충돌 검사와
공고·기술·상세 쓰기를 한 transaction으로 묶는다. 상세 실패는 부모/기술 변경까지 rollback한다.
조회는 한 read snapshot에서 목록·상세를 읽고 연결 종료 후 기존 버전 2 추출기로 재계산한다.
삭제·스크래핑·추출 규칙 변경·파생 저장은 추가하지 않았다.

시장 dashboard는 load_market_analysis로 source=work24만 집계하고 없으면 ‘샘플’로 표시한다.
기존 load_db_analysis도 manual은 제외하며 선택적 sources whitelist를 받는다. 범용 순수
analyzer/recommender 규칙은 그대로다. 저장 공고 목록은 수동/고용24/샘플을 출처와 함께 보여준다.
UI는 원문·네 품질 상태·네 분류·any_of/all_of·근거/위치를 표시한다. 빈 required를 요건 부재로
표현하지 않고 any_of는 ‘또는 — 하나 이상’의 단일 조건으로 표시한다.

## Phase 3C 요건 의미 보강·평가 계약

2026-09-17 완료. 아래 Phase 3B 기록 중 접속·대안·제목·추출기 버전 설명은 이 절이 대체한다.
원문 저장, 기존 네 분류, 필드별 의미, 비기술 조건과 시장 분석 경계는 유지한다.
**높은 재현율보다 높은 정밀도를 우선**하며 모호한 표현은 unspecified로 남긴다.
`REQUIREMENT_EXTRACTOR_VERSION = 2`: 평가 도구 추가가 아니라 실제 분류 의미 변경 때문에 올렸다.

### 제한된 나열과 그룹

`RequirementExtraction.groups`와 `RequirementGroup`을 추가했다. 그룹은 `relation`(all_of/any_of),
canonical `skills`, 그룹 전체의 `requirement_type`, 정확한 원문 `evidence` 하나를 갖는다.
각 RequirementEvidence에도 `relation`(independent/all_of/any_of)을 추가했다.
그룹 ID·중첩 논리식·점수·확률은 없다. 그룹 하나는 원문의 한 위치이며 반복 위치도 버리지 않는다.
그룹·근거는 필드/원문 순서, 구성원·기술 목록은 기존 taxonomy 순서다.

| 원문 | 개별 기술 요약 | 그룹 |
|---|---|---|
| Java required | Java required | 없음, independent 근거 |
| Java and SQL required | Java·SQL required | all_of / required |
| Java와 SQL 경험 필수 | Java·SQL required | all_of / required |
| Spring Boot, JPA, MySQL 경험 필수 | 세 기술 required | all_of / required |
| Python or Java required | 두 기술 unspecified | any_of / required |
| AWS 또는 GCP 경험자 우대 | 두 기술 unspecified | any_of / preferred |
| Java/Kotlin 중 하나 이상 | 두 기술 unspecified | any_of / unspecified |

기존 taxonomy의 기술명/alias만으로 구성된 나열과 제한된 접속사·공동 단서가 **행 전체에 맞을 때**
처리한다. and/및/와/과/쉼표의 명확한 공동 단서는 all_of, or/또는/혹은/중 하나는 any_of다.
슬래시는 `중 하나` 등 대안 단서가 있어야 선택 관계를 확정한다. `Java/SQL required`는 모호하므로
unspecified다. 복합 AND/OR, 괄호 중첩, 여러 술어, 미지원 기술이 섞인 대안은 그룹을 만들지 않는다.
대안 문장은 쉼표로 잘라 앞부분만 독립 필수로 승격하지 않는다. 미해석 대안이 있는 행 전체를
미분류로 남길 수 있으므로 명확한 다른 조각까지 누락되는 보수적 한계가 있다.

all_of 그룹은 명시적 공동 필수/우대 단서가 있을 때 만든다. 제목/필드만으로 분류한 일반 목록은
기존 독립 근거 계약을 유지한다. `Java required, Python`처럼 각각의 조각에 단서가 있는 문장은
공동 나열 문법에 맞지 않아 Python으로 필수 의미가 퍼지지 않는다. keywords는 언제나 검색
메타데이터이며 그룹을 생성하지 않는다. 우대 필드의 명확한 대안은 그룹에만 preferred를 적용한다.

any_of 구성원의 해당 근거는 **requirement_type=unspecified, rule=alternative_member**다.
그룹의 근거에는 실제 공동 분류와 explicit_required/explicit_preferred/section_heading/
preferred_field 등의 규칙이 남는다. 같은 원문 위치로 연결해 검토할 수 있다.
따라서 기존 개별 기술 목록만 읽어도 대안을 여러 독립 mandatory 기술로 오독하지 않는다.
미래 소비자는 선택 조건을 놓치지 않도록 반드시 groups도 읽어야 한다.

독립 근거 집계는 required > preferred > responsibility > unspecified를 유지한다.
예를 들어 `Java or Kotlin required`와 별도의 `Java preferred`가 있으면 Java 요약은 preferred,
Kotlin은 unspecified이며 required any_of 그룹은 별도로 보존된다. 같은 조각의 필수/우대 충돌은
우선순위로 강제 해소하지 않는다. 독립 긍정·부정 근거의 논리적 일관성까지 해결하지 않으므로
대표 분류 외에 모든 근거를 함께 검토해야 한다.

### 부정·제목·provenance

기존 명백한 부정(not required/not necessary/필수가 아님/필수가 아닙니다/요구하지 않음/
요구하지 않습니다/없어도 지원 가능 등)은 unspecified를 유지한다. 명확한 기술 나열에 걸린
지원 부정 표현은 쉼표 앞 기술까지 함께 미분류로 남긴다. 이를 긍정 그룹으로 만들지 않는다.
제한된 완전 일치 부정 제목 `Not required`, `Not necessary`, `필수가 아님`, `필수가 아닙니다`,
`요구하지 않음`, `요구하지 않습니다`는 이전 필수 섹션을 중립으로 끊는다.
일반 문장의 부정은 다음 행의 새 섹션을 추측하지 않으며 일반 언어의 모든 활용형을 해석하지 않는다.

`Qualifications`를 필수 제목 목록에 추가하고 `**Preferred:**`, `[Qualifications]:` 같은
완전한 wrapper 안팎의 콜론을 허용했다. blank line·bullet·연속 공백·CRLF 처리는 원문을 바꾸지
않는다. 임의 prose를 제목으로 확대 해석하지 않는다. `SQL 사용 가능자`는 명시적 능력 조건,
`SQL 사용 업무`는 업무 표현으로 구별한다.

source_field/source_index, evidence_text, evidence_start/end, section_heading/section_start,
rule은 모두 유지한다. 그룹·개별 근거에서 `source[start:end] == evidence_text`를 검사한다.
정규화된 복사본의 offset을 원문 offset으로 가장하지 않는다. raw 상세·fetched_at을 덮어쓰지 않는다.

### 품질·재처리·검증 범위

네 quality_status 이름은 바꾸지 않았다. `requirements_extracted`에는 분류된 기술 **또는 그룹**이
하나 이상 있는 경우를 포함한다. 따라서 모든 개별 기술이 unspecified여도 명시적 required
any_of가 있으면 이 상태다. unspecified 그룹만 있으면 미분류 상태다. 상세 없음과 근거 미검출은
여전히 다르며 빈 required 목록을 고용주의 필수 요건 부재로 해석하면 안 된다.

파생 persistence는 필요하지 않아 도입하지 않았다. **schema v2 유지, migration 없음**.
저장된 같은 원문·taxonomy·추출기 버전으로 결정적으로 재계산한다. 기존 DB 종료 후 조회 API와
inspect CLI가 추가 그룹을 그대로 반환한다. 실패한 HTTP refresh는 기존 raw를 유지하고,
추출 실패는 전파되며 raw나 이전 결과를 지우지 않는다. 수집·시장 analyzer·role classifier·
recommender·경력 정규화·UI에는 변경이 없다. 매칭·프로필·LLM·Phase 4는 시작하지 않았다.

기존 18개를 유지한 수동 검토 합성 corpus 60개로 검증한다. v1은 40/60사례·128/144분류 일치,
필수 오탐 3건이었고 v2는 60/60·144/144·13/13그룹 일치, 필수/우대 오탐 0건이다.
[기준선·최종 클래스별 fixture 지표와 재현법](TEST_BASELINE.md#phase-3c-검증-2026-09-17)을 따른다.
**합성 fixture precision/recall/F1이며 실공고·시장·운영 정확도가 아니다.** 별도 holdout도 아니다.
실 Work24 smoke는 수행하지 않았고 네트워크·API 키는 자동 검증에 필요 없다.

중첩 논리, 복잡한 부정·예외, 문장 간 참조, 임의 제목, HTML/표, 알려지지 않은 동의어는 여전히
지원 범위 밖이다. Elixir 등 taxonomy 밖 기술은 canonical로 추가하지 않으며 기술을 모르는
대안에서 알려진 구성원만으로 그룹을 축소하지 않는다. 전체 실공고에서 누락/오탐이 없다는
보장은 없다. 미래 매칭 전에 대표성 있는 별도 corpus와 그룹/미분류/충돌 소비 정책이 필요하다.

## Phase 3B 구조화 요건과 데이터 품질 계약

이 절은 Phase 3B 완료 당시 기록이며 변경된 의미는 위 Phase 3C 계약을 따른다.

2026-09-17 기준. `requirement_extractor.extract_requirements(detail)`은 저장/파싱된 상세 원문
또는 `None`을 받는 순수 함수다. 입력을 수정하지 않고 HTTP·SQLite·UI·환경·현재 시각을
사용하지 않는다. Work24 raw evidence의 모든 저장 필드는 유지한다. 기존 시장 분석과
새 요구사항 추출은 별도 결과이며, 공고별 매칭·사용자 점수·LLM은 구현하지 않았다.

### 분류와 필드별 범위

| 분류 | 의미와 판정 근거 |
|---|---|
| required | 명시적인 자격/필수 섹션 또는 같은 원문 조각의 필수·required·mandatory·must have 단서 |
| preferred | 우대 섹션/필드 또는 우대·preferred·nice to have·경험이 plus라는 단서 |
| responsibility | 업무 섹션 또는 개발·운영·관리·배포·구축·유지보수/build/develop/maintain/operate/deploy/manage 동작 |
| unspecified | 기술은 있지만 위 근거가 없거나 부정·조건·충돌·범위가 불명확함 |

`required`는 지원자가 이미 기술을 보유해야 한다는 명시적 맥락이다. `job_content`에 있다는
이유만으로 부여하지 않는다. `responsibility`도 사전 보유 의무를 뜻하지 않는다.
단순 `경험`/experience만으로 업무나 필수를 추론하지 않는다. `반드시`는 경험·역량·지식·능력·
보유·숙지와 함께, `필요합니다`는 경험·역량·지식·이해·능력과 함께 쓰인 경우만 필수 단서다.
`plus`는 경험 또는 `is a plus` 맥락이어야 한다. 회의·지원서·서류·이력서·면접 등의 의무와
기술 보유 의무가 섞이면 보수적으로 unspecified다.

| 출처 필드 | 처리 |
|---|---|
| job_content | 섹션/문장 단서로 분류. 기본 unspecified |
| preferred_conditions, other_preferred_conditions | 기본 preferred. 명시적 필수·업무·중립 섹션은 우선하며 부정·모호성은 unspecified |
| certificate, computer_skill | 기본 unspecified. 명시적 단서만 분류. 기술로 매핑되지 않는 원문도 검토 근거로 보존 |
| other_information | 본문과 같은 제한된 규칙. 기본 unspecified |
| keywords | 검색 메타데이터. 항목에 required라는 단어가 있어도 항상 unspecified |
| raw_career_condition, education, employment_type, work_region | 아래 비기술 조건 계약. 기술 추출에는 사용하지 않음 |
| 그 밖의 상세 필드 | raw 저장만 유지. 급여·URL·복리후생·접수방법 등에서 기술 요건을 만들지 않음 |

기술 검출은 기존 `extract_skills`와 59개 canonical taxonomy를 그대로 사용한다.
springboot→Spring Boot, postgres→PostgreSQL, k8s→Kubernetes 등 alias와 긴 겹침 우선 정책을
재사용한다. Spring Boot→Spring/MVC/Security, JPA→Hibernate, AWS→Docker 등의 추론은 없다.

### 작은 섹션 파서와 단서 범위

행 전체 또는 콜론 앞 label이 다음 목록과 정확히 일치할 때만 섹션이다. 영어 대소문자와
연속 공백을 정리해 비교하되 원문은 바꾸지 않는다.

- 필수: 자격요건, 지원자격, 필수요건, 필수사항, 필수, Requirements, Required, Required skills, Must have.
- 우대: 우대사항, 우대조건, 우대, Preferred, Preferred skills, Nice to have, Nice-to-have.
- 업무: 주요업무, 담당업무, 업무내용, Responsibilities, Duties.
- 중립: 기술스택, 사용 기술, Tech stack, Technologies, 복리후생, 혜택, 전형절차, 회사소개, Benefits, About us.

`[제목]`, `【제목】`, `**제목**`, Markdown # 제목, 번호·일부 bullet, `:`/`：`를 지원한다.
빈 줄은 상태를 유지하고 다른 제목은 상태를 바꾼다. 모르는 장식 제목·콜론 label·HTML/표 형식은
기존 필수/우대 범위를 중립으로 끊는다. 기술이 포함된 알 수 없는 제목은 기술 언급을 버리지 않는다.
일반 문장의 Requirements/주요업무라는 단어만으로 다음 줄까지 섹션 상태를 만들지 않는다.
필드가 바뀌면 모든 섹션 상태를 초기화한다.

각 행을 쉼표·세미콜론·문장부호 뒤 공백으로 나눈다. 분류는 **그 조각 안**의 단서만 사용한다.
따라서 `Java required, Python`의 Python은 unspecified다. `Required skills: Java, Python`은
명시적인 섹션 범위라 둘 다 required다. 콜론 없는 `Must have Java, Python`에서는 Java만 required다.
이는 문법적 나열 범위를 넓게 추정하지 않기 위한 의도적인 누락이다.

판정 순서는 부정 → 불확실성 → 같은 조각의 필수/우대 충돌 → 비기술 의무/대안·복합 범위 모호성
→ 명시 필수/우대 → 섹션 → 우대 필드 → 업무 동작 → 단순 언급이다.
부정은 필수 아님/필수가 아닙니다/요구하지 않음/없어도/불필요/경험 무관, not required,
do not require, no experience required, without experience, optional 등의 제한된 패턴이다.
부정은 긍정 요건을 생성하지 않으며 `unspecified`와 `negated` 규칙 코드로 근거를 남긴다.
질문·인용·조건·여부/미정/검토/협의, required와 preferred의 동시 단서는 확정하지 않는다.
or/또는/중 하나 같은 대안은 개별 필수 조건으로 바꾸지 않는다. 여러 기술과 명시 단서를
and/및 등으로 연결한 복합 조각도 적용 범위가 모호하면 unspecified다.

### provenance와 집계

결과 `RequirementExtraction`에는 `extractor_version=1`, source/posting_id,
`detail_fetched_at`, `quality_status`, `skills`, `unclassified_evidence`, `conditions`가 있다.
`detail_fetched_at`은 입력에 있으면 그대로 복사하고 파서 원문처럼 없으면 None이다.
새 관측 시각이나 confidence/점수는 만들지 않는다.

각 SkillRequirement는 canonical `skill`, 대표 `requirement_type`, 전체 `evidence` 목록을 갖는다.
각 근거에는 source_field, keywords의 source_index(나머지 None), evidence_text,
evidence_start/end, section_heading/section_start, 해당 근거 자체의 requirement_type, rule이 있다.
offset은 **입력 필드 문자열의 Python 문자 slice**이며 byte/XML/기술명 위치가 아니다.
keywords에서는 해당 항목 내부의 offset이다. `field[start:end] == evidence_text`가 성립한다.
섹션 제목도 원문 그대로와 시작 위치를 남기므로 제목 기반 분류 이유를 검토할 수 있다.

대표 분류는 독립 근거 사이에서 **required > preferred > responsibility > unspecified**다.
같은 조각의 상충 단서를 이 우선순위로 강제 해소하지 않는다. 반복 행·다른 필드·중복 keyword는
각기 다른 위치 근거로 모두 남는다. 한 조각 안에서 같은 기술/alias가 반복되면 그 전체 조각을
한 근거로 남긴다. 서로 다른 긍정/부정 근거가 있으면 대표값만으로 충돌을 판단하지 말고
근거 목록을 함께 확인해야 한다.

기술 출력은 기존 taxonomy 순서, 근거는 명시한 필드 순서와 원문 위치 순서다. dict 입력 순서나
set 순회에 의존하지 않는다. `unclassified_evidence`는 qualification 단서가 있지만 canonical
기술로 매핑되지 않은 문장, 모호/부정 문장, 자격·컴퓨터 활용·keyword의 미매핑 내용을 보존한다.
그 안의 requirement_type은 문맥 분류일 수 있으며 기술 해석을 완료했다는 뜻이 아니다.
이미 기술에 연결된 unspecified 근거는 각 기술의 evidence에 있어 별도 목록에 중복하지 않는다.

### 품질과 비기술 조건

| quality_status | 의미 |
|---|---|
| detail_not_fetched | 전달/저장된 성공 상세가 현재 없음 |
| detail_fetched_but_no_requirement_evidence | 지원하는 필드·규칙에서 기술/요건 근거를 관측하지 못함 |
| requirements_extracted | 하나 이상의 기술에 required/preferred/responsibility 근거가 있음 |
| requirement_evidence_present_but_unclassified | unspecified 기술, 미매핑 요건, 또는 비기술 조건 원문은 있지만 위의 기술 분류가 없음 |

`requirements_extracted`에도 미분류·미매핑 근거가 함께 있을 수 있다. 어느 상태도 공고 전체의
완전성 보증이 아니다. 특히 required 기술이 비었다고 **고용주의 필수 기술이 없다**고 해석하면 안 된다.
taxonomy 밖의 기술 이름만 있는 문장은 단서까지 없으면 검출되지 않을 수 있다.

조건 4개는 source_field/raw_text/status/normalized_value로 반환한다. 상태는 missing,
not_interpreted, normalized다. 정확한 경력 범주(신입, 경력, 무관, 경력무관, 관계없음,
신입/경력 등 제한된 완전 일치 표현)만 기존 normalize_career에 전달한다.
예: 원문 경력무관을 그대로 두고 파생 normalized_value=무관을 반환한다.
경력 3년 이상 같은 연차·복합 조건, 학력·고용형태·근무지는 원문과 미해석 상태만 유지한다.
숫자 연차·학위·위치 제한·급여 기준은 생성하지 않고 기존 목록 career/region도 덮어쓰지 않는다.

### 저장 결정·재처리·application 경계

파생 요건은 **영속화하지 않는다**. 현재는 단일 공고 검토이며 순수 재계산으로 충분하고,
독립 SQL 조회나 매칭용 반복 집계 소비자는 아직 없다. 원문이 이미 보존되므로 이 단계에서
파생 cache·추가 transaction·version별 stale row를 만들 필요가 없다. schema는 **v2** 그대로이며
storage/migrations/백업 정책에 변경이 없다.

`pipeline.load_posting_requirements(source, posting_id, db_path=...)`는 상세 path reader가
연결을 닫은 뒤 순수 추출한다. 기존 schema-on-read 동작은 유지한다. 수집 중 자동 추출은 하지
않으며 기존 Phase 3A 수집 결과·실패 보존 계약을 바꾸지 않는다. 성공 refresh 후 조회는 최신
원문에서 재계산하고, 실패 refresh 후 조회는 보존된 원문에서 같은 결과를 반환한다.
추출 오류는 호출자에게 전파하며 빈 성공 결과로 바꾸지 않는다. DB와 이전 반환 객체는 손대지 않는다.

`REQUIREMENT_EXTRACTOR_VERSION = 1`은 전체 결과와 그 안의 근거에 공통 적용된다.
같은 원문·현재 taxonomy·규칙 버전에서는 같은 결과다. 재호출은 새 결과를 만들며 이전 요건을
누적하지 않는다. 향후 규칙/taxonomy 변경으로 출력 의미가 바뀌면 version 갱신을 검토해야 한다.
자동 version migration framework나 별도 taxonomy 복제는 없다.

검토용 CLI는 `python -B scripts/inspect_requirements.py --source work24 --posting-id ID --db-path PATH`다.
JSON으로 네 범주·원문 근거·품질·비기술 조건을 확인한다. HTTP·키가 필요 없으며 누락 상세도
명시적인 상태로 반환한다. 실패는 비정상 종료로 드러난다. Streamlit 화면은 변경하지 않았다.
기존 analyzer/recommender의 시장 언급 수·분모·추천은 그대로다.

### 지원 한계

일반 한국어 문법·복잡한 부정 범위·인용/가정·문장 사이 대명사·서식 없는 알 수 없는 제목은
완전히 해석하지 않는다. HTML/표를 해석하거나 임의 제목을 추측하지 않는다. 한 조각 안에서
서로 다른 대상을 수식하는 단서, 장문 조건·예외·대안 그룹은 오분류/누락 여지가 있다.
`Java and SQL required`처럼 실제로 둘 다 필수인 문장도 보수적으로 미분류될 수 있다.
섹션 밖 `Java experience essential`처럼 등록하지 않은 동의어는 unspecified다.
합성 평가 세트 통과는 실공고 정확도/재현율 보증이 아니다. 미래 매칭 전에 별도 수동 검토
코퍼스와 미분류·충돌 처리 정책이 필요하다. Phase 4 이상은 시작하지 않았다.

## Phase 3A 상세 원문과 schema v2 계약

2026-09-16 Phase 3A 완료 당시 기록. 아래 raw 저장 계약은 유지하며 현재의 파생 추출은 위 Phase 3B 계약을 따른다.

### 공식 API 경계와 원문 의미

[고용24 공식 상세 API 안내](https://m.work24.go.kr/cm/e/a/0110/selectOpenApiSvcInfo.do?fullApiSvcId=000000000000000000000000000000%5E000000000000000000000000000001%5E000000000000000000000000000003)의
요청 URL·필수 인자·출력 계층을 확인했다. GET endpoint는
`https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210D01.do`이며,
`authKey`, `wantedAuthNo`, `callTp=D`, `returnType=XML`, `infoSvc=VALIDATION`을 URL encode한다.
timeout은 30초, UTF-8(BOM 허용)로 해독한다. 자동 재시도는 없다.

`parse_posting_detail`은 `wantedDtl/wantedAuthNo`와 단일 `wantedDtl/wantedInfo`를 읽어
`DetailEvidence` dict를 반환한다. 이 함수는 I/O·시각 생성·요건 해석을 하지 않는다.
`fetch_posting_detail`이 요청 identity와 응답 identity를 비교한 뒤 성공한 경우에만
UTC ISO 8601 `fetched_at`을 붙여 `PostingDetail`을 반환한다. 이는 게시일·원문 수정일이
아닌 **성공적으로 관측한 시각**이다. 두 계약은 런타임 dict를 유지하는 TypedDict다.

문자열 앞뒤 padding만 제거한다. `job_content`의 내부 줄바꿈·들여쓰기·빈 줄은 보존하고,
XML escape/CDATA는 텍스트로 읽는다. 선택 태그의 누락·빈 문자열·공백은 `None`이다.
`keywords`는 `keywordList/srchKeywordNm`을 문서 순서대로 읽고 빈 값만 제외한다.
중복과 대소문자를 유지하며 기술명 통합·쉼표 분할·정렬을 하지 않는다. 누락은 `[]`다.
유효 identity와 빈 `wantedInfo`는 선택 정보가 없는 성공 응답이다. `wantedInfo` 자체가
없거나 오류 응답인 경우와 구별하며 실패를 빈 상세로 바꾸지 않는다.

### 선택 저장 필드

`source`, `posting_id`, 아래 nullable TEXT 20개, `keywords`, `fetched_at`을 저장한다.

| 저장 필드 | wantedInfo 태그 |
|---|---|
| job_content | jobCont |
| employment_type | empTpNm |
| raw_career_condition | enterTpNm |
| education | eduNm |
| foreign_language | forLang |
| major | major |
| certificate | certificate |
| computer_skill | compAbl |
| preferred_conditions | pfCond |
| other_preferred_conditions | etcPfCond |
| selection_method | selMthd |
| receipt_method | rcptMthd |
| submit_documents | submitDoc |
| other_information | etcHopeCont |
| work_region | workRegion |
| work_hours | workdayWorkhrCont |
| welfare | etcWelfare |
| salary_condition | salTpNm |
| closing_at | receiptCloseDt |
| detail_url | dtlRecrContUrl |

`empchargeInfo`의 채용부서·전화·팩스, 대표자·회사 재무·회사 주소 등 `corpInfo`, 첨부파일,
지하철 세부 코드·중복 제목·각종 분류 코드는 상세 테이블에 저장하지 않는다. 원본 XML 전체,
인증 URL·키·응답 본문을 실패 메시지에 저장하지 않는다. 선택한 자유 텍스트 안의 개인정보를
자동 판별·삭제하는 기능은 없으며, 구조화된 연락처 필드를 수집하지 않는 범위다.

### schema v2와 이전

`PRAGMA user_version=2`. `job_postings`와 `posting_skills`의 기존 열·복합 identity·`created_at`은
유지한다. 신규 `posting_details`는 `PRIMARY KEY (source, posting_id)`와
`FOREIGN KEY (source, posting_id) REFERENCES job_postings(source, posting_id) ON DELETE CASCADE`를
갖는다. surrogate ID는 없다. identity·keywords·fetched_at은 NOT NULL이며 keywords는 JSON 배열 TEXT다.
각 연결에서 FK를 켠다. 다른 source의 같은 ID는 독립적이며 부모 삭제는 해당 상세·기술만 지운다.

- fresh DB는 세 테이블과 v2를 한 transaction에서 생성한다.
- v1→v2는 상세 테이블만 추가한다. 공고·기술·created_at을 재작성·재추출하지 않는다.
  기존 데이터 변경을 거절하는 trigger를 설치한 테스트에서도 이전이 성공한다.
- v0→v2는 기존 v0→v1 복합 키 변환 후 상세 테이블을 추가하는 단일 transaction이다.
  모든 공고 필드·created_at을 보존한다. 기술은 **기존 Phase 1C 정책 그대로** 보존된 본문에서
  재구성한다. 본문과 일치하는 기술은 유지하고 orphan·오래된 누적 기술을 정리하며 원본은 백업한다.
  이는 v1 기술의 정확한 보존 정책과 다르다.
- 마지막 DDL·FK 검증·version 기록 중 실패해도 원래 schema/data/version으로 rollback한다.
  v2 재개방은 layout 확인만 수행하며 데이터 변경·추가 백업을 하지 않는다.

파일 DB의 이전 작업 전에 SQLite backup API로 같은 디렉터리에
`<DB>.pre-v2-from-v0-<고유값>.bak` 또는 `<DB>.pre-v2-from-v1-<고유값>.bak`을 만든다.
`pre-v2`는 v2 이전 전, `from-vN`은 백업 안에 든 schema다. 백업 실패는 이전을 중단하고
이번에 만든 불완전 백업만 제거한다. 기존 백업은 덮어쓰지 않으며 재시도마다 새 파일을 만든다.
fresh/in-memory DB와 이미 v2인 DB에는 이전 백업을 만들지 않는다.
복원은 모든 writer를 중지하고 백업을 별도 파일로 복사해 확인한다. 복사본을 현재 앱으로 열면
다시 이전한다. 백업 시점과 write lock 획득 사이 동시 쓰기까지 일치시키는 설계는 아니므로
최초 이전은 다른 writer를 중지한 상태로 수행한다.

### 저장·갱신·부분 실패

`save_posting_details`는 identity, UTC timestamp, 선택 문자열과 문자열 목록을 검증한 뒤
SAVEPOINT로 전체 상세 배치를 upsert한다. 실패 시 해당 배치만 rollback하고 caller의 기존
transaction은 보존한다. 두 path wrapper는 성공·실패 모두 연결을 닫는다.
`load_posting_detail`의 `None`은 성공한 상세 저장 이력이 없다는 의미다.

명시적인 상세 수집은 수집된 identity마다 매번 갱신한다. TTL·자동 재시도·이력 snapshot은 없다.
성공한 최신 응답이 전체 상세를 교체하므로 이번 응답에 없는 선택 필드는 NULL이 된다.
동일 내용이어도 새 성공 시각이면 fetched_at이 바뀐다. 실패한 갱신은 이전 상세와 fetched_at을
그대로 유지한다. 수집 실패를 삭제·빈 상세 저장으로 표현하지 않는다.

`collect_work24_with_details_to_db`의 순서는 목록 수집 → 기존 정제·복합 identity 중복 제거
→ 목록 배치 저장·연결 종료 → 상세 HTTP → 성공 상세 저장·연결 종료의 반복이다.
HTTP 중에는 SQLite 연결이나 write transaction을 보유하지 않는다.
한 실행에서 같은 복합 identity는 첫 목록 표현을 유지하고 상세 요청은 최대 한 번이다.
20건 중 상세 1건이 실패해도 목록 20건·성공 상세 19건은 저장하고 나머지 요청을 계속한다.
기존 상세가 있으면 그대로 남는다. DB 오류·프로그래밍 오류까지 네트워크 부분 실패로 숨기지 않는다.

`CollectionResult`는 중복 제거 후 목록 수 `collected`, 신규 identity 수 `new_postings`,
성공 저장/갱신 수 `details_saved`, `detail_failures`를 반환한다. 각 `DetailFailure`는
source/posting_id와 안전한 범주 `reason`만 갖는다. 실패 이력은 별도 DB 테이블에 영속화하지 않는다.

### 오류·CLI·기존 분석 호환

오류는 `transport_error`, `invalid_encoding`, `malformed_xml`, `unexpected_structure`,
`missing_detail`, `missing_identity`, `identity_mismatch`, `api_error` 등으로 구분한다.
명시적 error 요소나 errorCode/errorCd의 값은 방어적으로 인식하며 공식 오류 코드 체계를
정의했다고 주장하지 않는다. 알 수 없는 응답 계층은 거절한다. 예외에는 URL·키·본문을 넣지 않고,
통신/파싱 원래 예외의 traceback 연결을 억제한다. 임의 오류 문자열은 `request_error`로 제한한다.

목록의 정상 빈 root/wantedRoot는 빈 목록으로 남고, HTML·오류·예상 밖 계층은 실패다.
namespace 목록도 읽는다. KD-09는 이 경계에서 수정했다. 목록 실패 예외는 기존 원래 HTTP/ParseError
대신 안전한 Work24Error로 바뀌지만 목록 수집 함수의 인자·list/int 반환·요청 횟수는 유지한다.

`python -B scripts/collect_work24.py --keyword SQL`은 기존 목록 전용 경로다.
`--with-details`를 추가해야 상세를 요청한다. 성공은 exit 0, 키 부재/목록 Work24 실패는 exit 1,
상세 부분 실패는 성공 결과를 보존하고 성공·실패 건수와 실패 identity/범주를 출력한 뒤 exit 2다.
exit 2는 전체 rollback을 뜻하지 않는다.

상세 원문·우대조건·자격·keywords는 아직 기술 추출에 전달하지 않는다.
기존 `description`은 목록 title+industry+career 요약 의미를 유지한다. 상세로 덮어쓰지 않는다.
정규화된 `career`의 경력무관→무관 정책과 상세 `raw_career_condition`의 원문 경력무관을 함께 보존한다.
상세-목록 우선순위는 추가하지 않았다. 기술 추출·역할 분류·추천은 기존 입력·동작 그대로다.
필수/우대 기술 추출·자격 해석·LLM·공고 매칭·프로필·북마크·지원 관리는 구현하지 않았다.

## Phase 2D 경력 정규화 계약

2026-09-16 기준. 아래 정책이 이전 단계의 경력무관 결함·경력 정제 설명을 대체한다.
`career`는 기존 문자열 필드를 유지하며 모델·스키마·migration은 변경하지 않는다.

| 입력 | canonical 값 | 의미 |
|---|---|---|
| None, 빈 문자열, 공백, 미상 | 미상 | 정보 없음. 경력 제한이 없다는 뜻이 아님 |
| 신입 | 신입 | 신입 범주 |
| 경력, 경력 1년, 경력 3년 이상 | 경력 | 경력 범주. 연차 숫자는 별도로 추론·생성하지 않음 |
| 무관, 경력무관, 경력 무관, 관계없음, 경력 관계없음 | 무관 | 명시된 경력 제한 없음 |
| 신입/경력, 경력/신입, 신입 및 경력, 신입·경력 | 신입/경력 | 두 범주가 함께 명시됨 |
| 기타, 미지원 표현(intern, Experienced 등) | 기타 | 기존 미지원 표현 처리 유지 |

판정은 결측 → 무관/관계없음 포함 → 신입과 경력 모두 포함 → 신입 → 경력 → 기타 순서다.
`신입/경력 무관`처럼 제한 없음이 명시되면 무관을 우선한다. 혼합 표현을 신입 하나로
축약하던 동작은 신입/경력으로 변경했다. 여섯 canonical 값과 지원 입력의 반복 정규화,
clean_posting 반복 적용, 임시 SQLite 저장·재조회·재분석의 멱등성을 테스트했다.

이 함수는 경력 범주 문자열을 정리하는 기존 규칙의 작은 수정이다. 상세 본문의 부정문·복합
조건이나 최소 연차를 해석하는 모델이 아니며, 기존 연차 문자열을 경력으로 축약하는 범위는
유지한다. 저장소의 Work24 XML fixture는 합성 자료이고 경력/공백 값을 담고 있다.
실 API의 모든 경력 표현을 지원한다고 주장하지 않는다.

기존 DB를 자동 수정하거나 backfill하지 않는다. 원문 경력무관/혼합 표현이 남아 있으면
application의 재정제 결과에 반영되지만, 이미 경력/신입으로 축약되어 저장된 값은 원래
의미를 추정 복원할 수 없다. 모델·저장 identity·역할 분류·기술 추출·추천·UI는 그대로다.

## Phase 1C 현재 영속 계약

Phase 1C 당시 기록. 공고·기술 저장 불변식은 유지하며 현재 스키마·이전 경로는 위 Phase 3A 계약을 따른다.

### 불변식과 스키마

1. 공고 identity는 `(source, posting_id)`이며 두 값은 비어 있지 않은 문자열이다. storage API는 누락/None/공백/비문자열을 ValueError로 거절한다. 원래 문자열의 대소문자·내용을 임의로 바꾸지 않는다. 정제 경로는 종전대로 앞뒤 공백을 제거한다.
2. job_postings는 기존 14개 필드와 created_at만 갖는다. PK는 `(source, posting_id)`, 두 키는 NOT NULL이며 빈 값·일반 공백만 있는 값은 CHECK로도 막는다. 선택 필드는 nullable TEXT다. created_at은 NOT NULL이다.
3. posting_skills는 source/posting_id/skill 모두 NOT NULL, PK `(source, posting_id, skill)`, FK `(source, posting_id) REFERENCES job_postings(source, posting_id) ON DELETE CASCADE`다.
4. 공고 저장 API가 성공하면 저장된 title/description과 기술 집합은 같은 최신 표현이다. skills 입력 필드는 신뢰하지 않고 실제 저장된 본문에서 현행 extractor로 계산한다. 기술 검출 자체의 알려진 오탐/누락은 별개이며 이번 단계에서 바꾸지 않는다.
5. 경력 결측 canonical 값은 `미상`. 이를 다시 정제해도 `미상`이며, 정제된 공고를 반복 정제하거나 DB 왕복해도 canonical 결측 의미가 유지된다.

### 재저장과 트랜잭션

동일 identity의 모든 선택 필드를 최신 입력으로 교체하고, 기술을 전부 지운 뒤 새 집합을 넣는다. 생략한 선택 필드는 NULL이 된다. 최초 created_at은 바꾸지 않고 갱신 시각 필드는 추가하지 않았다. 반환 int는 신규 공고 identity 수이며 갱신 수가 아니다. 직접 저장 배치의 중복 identity는 마지막 표현이 남고 신규 수는 한 번만 센다. 수집 정제의 중복 제거는 같은 복합 identity의 첫 행 유지 정책을 그대로 사용한다.

save_postings는 모든 identity를 쓰기 전에 검증한다. 준비된 schema에서 SAVEPOINT로 배치 전체를 묶고, 한 공고/기술 저장이라도 실패하면 해당 배치 전부를 rollback한다. 상위 transaction이 없으면 release 시 저장이 완료되고, 상위 transaction이 있으면 caller가 최종 commit/rollback한다. 상위 transaction의 이전 작업을 임의로 commit하지 않는다. schema migration은 저장 배치와 별개로 먼저 완료되므로 이후 잘못된 본문 저장이 실패해도 완료된 schema는 v1일 수 있다.

`connect`와 schema 초기화에서 FK 활성화를 확인한다. SQLite FK는 연결마다 켜야 하며 transaction 도중 설정 변경은 적용되지 않으므로, FK가 꺼진 활성 transaction은 RuntimeError로 거절한다. 이 정책은 [SQLite FK 문서](https://www.sqlite.org/foreignkeys.html)와 [transaction 문서](https://www.sqlite.org/lang_transaction.html)에 따른다.

### user_version 0 → 1 마이그레이션

Phase 1B 기준 실제 schema는 `user_version=0`, job_postings의 posting_id 단일 PK, posting_skills의 `(posting_id, skill)` PK이며 FK가 없었다. 새 DB는 바로 v1로 생성한다. 현재 SQLite를 생성/읽기/쓰기하는 진입점은 storage의 connect, ensure_schema(현재 migrations에서 import), save_postings, load_postings, count_postings 및 두 path wrapper다. pipeline은 path wrapper만 호출한다.

기존 파일 DB는 첫 load/save/count 시 다음 순서로 이전한다.

1. version·테이블·필드·PK를 확인한다. 알려지지 않은 schema/version, 별도 legacy index/trigger/view가 있으면 자동 이전하지 않는다. active transaction에서 migration을 수행하지 않는다.
2. SQLite backup API로 같은 디렉터리에 `<DB 파일명>.pre-v1-<고유값>.bak`을 생성한다. 기존 백업을 덮어쓰지 않는다. 백업 실패는 migration을 중단한다. in-memory DB에는 파일 백업을 만들지 않는다.
3. BEGIN IMMEDIATE 후 새 `_v1` 테이블에 공고를 복사하고 검증한다. source 또는 posting_id가 유효하지 않은 기존 공고는 추측·삭제하지 않고 전체 이전을 중단한다.
4. 남아 있는 공고 본문을 기준으로 기술을 재구성한다. 기존 기술 중 본문에 해당하는 것은 유지, 오래된 누적 기술은 제거, 누락된 추출 기술은 복원한다. 부모 없는 기술은 identity를 복원할 수 없어 새 테이블에 넣지 않는다. 각각의 건수를 한국어 warning log로 남긴다.
5. 공고 필드 보존과 FK 검증을 통과한 뒤에만 구 테이블을 제거하고 새 테이블 이름을 바꾼다. schema 검증 후 user_version=1을 기록하고 commit한다. DDL/copy/rename/version 갱신 중 실패하면 모두 rollback한다.
6. v1 재실행은 schema 확인만 하며 데이터 재생성·기술 재추출·추가 백업은 하지 않는다.

기술을 무조건 복사하면 이전의 본문/기술 불일치를 그대로 남기므로, **유효 기술은 부모뿐 아니라 보존된 본문과도 일치하는 기술**로 정의했다. 원본 전체는 백업으로 보존한다. 본문 밖에서 수동으로 추가한 기술도 현재 파생 집합에는 포함되지 않으므로 백업과 처리 로그를 확인해야 한다.

기존 단일 ID 제약으로 거절되거나 사라진 다른 source의 공고는 복원할 정보가 없다. 남아 있는 source 값을 보존하며 이후부터 동일 external ID의 다른 source를 별개 공고로 저장한다. 정렬은 기존 날짜 DESC/ID DESC에 source ASC를 동점 기준으로 추가했다.

### 운용·복원 주의사항

마이그레이션은 읽기 경로에서도 실행된다. 최초 실행 전에 app·수집 CLI 등 다른 writer를 중지하고 백업 위치의 쓰기 권한과 여유 공간을 확인한다. 자동 backup 시점 이후 동시에 다른 writer가 쓰면 백업과 이전 직전 상태가 달라질 수 있으므로 단독 실행이 원칙이다. BEGIN IMMEDIATE는 실제 이전 중 writer를 배제한다.

복원 시 모든 프로세스를 종료하고 실패/변경 DB 자체도 보관한 뒤, 백업을 별도 경로로 복사해 확인한다. v0 백업을 신 버전 앱으로 열면 migration이 다시 실행된다. 파일 백업·재연결·복사본 복원은 테스트에서 검증했다. 커스텀 schema나 잘못된 기존 identity로 이전이 거절되면 원본을 유지하고 원인을 해결해야 하며 DB를 초기화하면 안 된다. 기본 data 폴더의 백업은 Git에서 제외하며 커스텀 DB 경로의 백업도 공개하지 않는다.

역사 snapshot·updated_at·migration framework·ORM은 추가하지 않았다. 기존 `기타` 값이 원래 결측이었는지는 판단할 수 없어 소급 치환하지 않는다.

## Phase 2A 기술 taxonomy와 추출 계약

2026-09-16 기준. 저장 스키마·identity·migration·transaction 계약은 위 Phase 1C와 같다. 추출 정책만 아래와 같이 확장했다.

### 구조와 범위

`skill_taxonomy.py`의 `SKILL_DEFINITIONS`는 canonical 이름 → (유지보수용 category, 추가 alias) 순서형 dict다. canonical 이름 자체도 alias로 등록한다. 기존 31개 Data/AI 중심 기술과 그 출력 순서를 유지하고 28개를 추가하여 총 59개다. category는 누락·별칭 검토에만 사용하며 UI나 직무 분류에 전달하지 않는다. JSON/YAML/DB나 새 의존성은 추가하지 않았다.

| 분류 | 지원 범위 |
|---|---|
| 언어·쿼리 | Python, SQL, R, Java, Kotlin, JavaScript, TypeScript |
| backend·영속 도구 | Spring, Spring Boot, Spring MVC, Spring Security, JPA, Hibernate, QueryDSL |
| 빌드·테스트 | Gradle, Maven, JUnit, Mockito |
| DB·캐시·검색 | MySQL, PostgreSQL, MongoDB, MariaDB, Oracle, Redis, Elasticsearch |
| 메시징·데이터 엔지니어링 | Kafka, RabbitMQ, Spark, Airflow |
| 클라우드·컨테이너·OS | AWS, GCP, Azure, Docker, Kubernetes, Linux |
| API·보안 | REST API, GraphQL, JWT, OAuth |
| 버전 관리·CI/CD | Git, GitHub Actions, Jenkins, CI/CD |
| 분석·BI·시각화 | Pandas, NumPy, Statistics, A/B Test, Excel, Tableau, Power BI, Looker, Plotly, GA4 |
| AI/ML | Machine Learning, Deep Learning, NLP, PyTorch, TensorFlow, Recommender System |

frontend framework는 이번 범위에 추가하지 않았다. `C`, `Go`, `AI`도 모호한 단독 alias로 새로 등록하지 않았다. 특히 AI는 Machine Learning과 동의어로 취급하지 않는다.

### alias와 canonicalization

- `SpringBoot`/`spring boot`/`스프링부트` → `Spring Boot`, `postgres` → `PostgreSQL`, `k8s` → `Kubernetes`, `깃` → `Git`처럼 한 개념에 canonical 이름 하나를 둔다. Spring 계열은 별개 개념이다.
- 알려진 이름은 casefold와 내부 연속 공백 정리 후 전체 문자열로 비교한다. 추출에서는 다중 단어 alias의 공백·탭·줄바꿈을 허용한다. 띄어쓰기 없는 표기나 하이픈 표기는 명시한 alias만 인정한다.
- canonicalization 결과는 입력에서 처음 등장한 canonical 순서로 중복을 제거한다. 빈 값은 제외한다. 미등록 기술은 앞뒤 공백만 제거하고 원래 대소문자·내부 공백을 보존한다. `C`, `Go`, `AI` 같은 미지원 이름도 사용자 입력에서 삭제하지 않는다.
- 동일 정규화 alias가 다른 canonical에 배정되거나 빈 alias이면 초기화에서 오류를 낸다. 전체 alias의 추출·canonicalization 왕복을 테스트한다.

### 경계와 겹침

- Unicode 단어 문자(한글·영문·숫자·밑줄 등)에 붙은 부분 문자열은 거절한다. `JavaScript`에서 Java, `NoSQL`에서 SQL, `GitHub`에서 Git을 추론하지 않는다. `+`, `#`도 이름에 붙는 문자로 취급하여 다른 언어·식별자의 일부를 잘라내지 않는다.
- 마침표·쉼표·괄호·슬래시·가운뎃점·세미콜론·줄바꿈은 경계다. `Python.`, `Java,`, `(Spring Boot)`, `Kafka/Redis`, `AWS·Docker`, `MySQL; PostgreSQL`을 지원한다. 구두점으로 단어를 합쳐 alias를 만들지는 않는다(`REST/API`는 REST API 아님).
- 한글 접미사는 `은/는/이/가/을/를/과/와/의/도/로/에/만`, `으로/에서/에게/까지/부터/와의/과의/에는/에도`를 허용하되 그 뒤가 다시 단어 경계여야 한다. `파이썬으로`, `SQL과`는 허용하고 `통계청`, `통계로봇`, `SQL과제`, `깃발`, `스프링클러`는 거절한다. `자연어처리`, `통계분석` 같은 붙여 쓴 복합어는 명시적 alias로 지원한다.
- ASCII 알파벳 1–2자 alias(현재 R, ML)는 추가로 공백을 제외한 앞뒤 `&` 및 바로 앞 수치 문맥을 거절한다. `R&D`, `R & D`, `D&R`, `10 ml`, `2.5 ML`은 검출하지 않는다. `R`, `ML engineer`, `R/Python`, `R을 사용`은 유지한다.
- 같은 위치에서 겹치는 alias는 가장 긴 근거를 우선한다. 동률은 위치, alias 선언 순서로 결정한다. `Spring Boot`만 쓰면 Spring Boot만, `GitHub Actions`만 쓰면 GitHub Actions만 반환한다. `Java Persistence API`는 JPA만 반환한다. 별도 위치에 Spring/Java/Git이 명시되면 각각도 반환한다. Deep Learning에서 Machine Learning을 자동 추론하지 않는다.
- 추출은 중복 없이 taxonomy 선언 순서로 반환한다. 내부 set의 순회 순서에 의존하지 않는다. title과 description은 개별 처리하여 한 필드 끝 `Machine`과 다음 필드 시작 `Learning`으로 가짜 복합 기술을 만들지 않는다.

### 한계와 기존 DB 영향

문맥 이해·형태소 분석은 하지 않는다. `통계`/`쿼리`/`Oracle`/`Spring` 등의 일반적·기업명 의미, 독립된 R/ML의 다른 의미, 부정·필수·우대는 구별하지 못한다. 조사와 같은 철자의 단어 끝도 완벽히 분리할 수 없다. 미등록 복합어·조사 결합·`Python3` 같은 붙여 쓴 버전은 보수적으로 누락될 수 있다. `R & Python`처럼 &로 나열한 실제 기술에서도 R은 보수적으로 제외한다. 버전 파서·Unicode 정규화·HTML parser는 도입하지 않았다.

기존 v1 DB를 여는 것만으로 저장 기술을 재작성하지 않는다. 분석은 원래부터 본문을 재추출하므로, 과거 규칙으로 저장한 posting_skills와 새 분석이 다를 수 있다. 정상 save_postings 재저장 시 최신 추출 집합으로 원자적 교체한다. v0 migration도 기존 설계대로 실행 시점의 extractor를 사용하므로 새 규칙의 기술 집합을 생성한다. migration 코드·버전·백업·rollback 방식은 변경하지 않았다. 자동 backfill이나 taxonomy 버전 저장은 이번 범위에 넣지 않았다.

Phase 2A 당시에는 기술 추출 개선 후에도 `Backend Engineer` + `Spring Boot Redis`의 분석가 fallback, Docker 단일 기술의 데이터 엔지니어 판정, mobile→BI/retail→ML 문제가 남았다. 이 분류 결함은 아래 Phase 2B에서 수정했고 추천 점수 공식은 유지했다.

## Phase 2B 역할 taxonomy와 분류 계약

2026-09-16 기준. 역할은 분석 시 계산되는 문자열이며 DB 저장 필드가 아니다. `role_classifier.py`가 다음 canonical label을 정의하고 analyzer를 통해 UI와 기존 호출자에게 전달한다.

| 역할 | canonical label |
|---|---|
| Backend Engineer | 백엔드 엔지니어 |
| Frontend Engineer | 프론트엔드 엔지니어 |
| Full-stack Engineer | 풀스택 엔지니어 |
| Data Analyst | 데이터 분석가 |
| BI Analyst | BI 분석가 |
| Data Engineer | 데이터 엔지니어 |
| ML / AI Engineer | ML 엔지니어 |
| DevOps / Cloud Engineer | DevOps / 클라우드 엔지니어 |
| Unknown / Other | 미분류 / 기타 |

기존 4개 한국어 label은 추천 foundation key와 호환된다. 역할 목록 순서는 UI 표시 순서이며 판정 우선순위가 아니다. ML label은 AI/NLP 관련 엔지니어와 Data Scientist를 포함하는 현재의 넓은 역할 범주다.

### 근거 계층과 경계

1. **명시적 제목**: Backend/back-end/백엔드, Frontend/front-end/프론트엔드, Full-stack/풀스택, Data Analyst, BI Analyst, Data Engineer, ML/AI Engineer, DevOps/SRE/Cloud/Platform Engineer 및 명시한 한국어 표현을 검사한다. server는 단독으로 쓰면 미분류이며 server developer/서버 개발자 같은 개발 직무 표현을 요구한다.
2. **업무·도메인 구문**: 제목에서 역할을 확정할 수 없을 때 제목과 본문 각각의 API 개발·UI 개발·통계 분석·대시보드 운영·ETL·data pipeline·model training·운영 자동화 등을 검사한다. AI API integration이나 일반 플랫폼·파이프라인 단어만으로 역할을 추론하지 않는다. data analysis/analytics, machine learning/deep learning, ETL처럼 업무 분야가 구체적인 구문도 이 단계의 근거다.
3. **기술 조합**: 텍스트 근거가 없을 때만 아래 조합을 사용한다. 단일 기술은 역할을 확정하지 않는다. 중복 기술을 많이 넣어도 근거가 강해지지 않는다.
4. 근거가 없거나 승리 단계에서 충돌하면 **미분류 / 기타**다. 더 약한 단계로 내려가 충돌을 임의로 해소하지 않는다. confidence 숫자는 만들지 않는다.

casefold한 텍스트에서 Unicode 단어 경계를 검사한다. mobile/retail/email/bilingual/html 안의 bi/ai/ml을 찾지 않는다. 영문 구문의 공백·하이픈·탭 변형을 허용하고 한글이 연결된 구문은 띄어쓰기 생략을 허용한다. 한글 조사 은/는/이/가/을/를/의/와/과는 뒤에 단어 경계가 있을 때만 허용한다. `백엔드개발자`는 인식하고 `데이터분석가족`은 인식하지 않는다. 서로 다른 필드 끝과 시작을 붙여 가짜 구문을 만들지 않는다.

### 역할별 근거

| 역할 | 제목·업무 근거 예시 | 제목·업무 근거가 없을 때의 기술 조합 |
|---|---|---|
| Backend | backend, 백엔드, server developer, API developer, API development, 서버 개발 | Spring 계열 + Java/Kotlin/Redis/Kafka/REST API/ORM/DB 중 하나, 또는 Java/Kotlin + ORM + DB/Redis/Kafka |
| Frontend | frontend, 프론트엔드, UI developer, web UI development | 없음. JavaScript/TypeScript만으로 backend와 구분할 수 없음 |
| Full-stack | full-stack, 풀스택, full stack development | 없음. Java+JavaScript만으로 추론하지 않음 |
| Data Analyst | data analyst, 데이터 분석가, data analysis, statistical analysis, 공공데이터 분석 | Statistics/A/B Test + Python/R/Pandas/SQL |
| BI Analyst | BI analyst, business intelligence, KPI analyst/reporting, dashboard development, 대시보드 운영 | Tableau/Power BI/Looker + SQL/Excel |
| Data Engineer | data engineer/platform engineer, 데이터 엔지니어/플랫폼 엔지니어, ETL/ELT, data pipeline/warehouse/lake | Spark/Airflow + SQL/Kafka/AWS/GCP/Azure, 또는 Spark+Airflow |
| ML / AI | ML/AI engineer, 머신러닝 엔지니어, NLP engineer, data scientist, model training, 자연어 처리 | PyTorch/TensorFlow + Python/Machine Learning/Deep Learning/NLP |
| DevOps / Cloud | DevOps, SRE, cloud/platform/infrastructure engineer, 인프라 엔지니어, 배포·운영 자동화 | Docker/Kubernetes + CI/CD/Jenkins/GitHub Actions + AWS/GCP/Azure/Linux |

위 표의 `+`는 서로 다른 그룹을 함께 요구하고 `/`는 그룹 안의 선택지다. ORM은 JPA/Hibernate/QueryDSL, DB는 MySQL/PostgreSQL/MariaDB/Oracle/MongoDB, Spring 계열은 Spring/Spring Boot/Spring MVC/Spring Security다. 기술 조합이 여러 역할을 동시에 만족하면 투표·고정 역할 순서로 고르지 않고 미분류로 남긴다.

### 구체성·모호성 정책

- 같은 위치에서 `data platform engineer`는 내부의 `platform engineer`를 포함하므로 Data Engineer만 근거로 남는다. `ML platform engineer`도 일반 Platform보다 구체적이다. `BI Data Analyst`는 BI로 취급한다.
- 별도 위치의 명시적 직무가 충돌하는 `Backend Engineer / Data Engineer`, `Backend / Frontend`는 미분류다. 단, Full-stack이 명시되고 나머지가 Backend/Frontend뿐이면 Full-stack으로 분류한다. `Full-stack / Data Engineer`까지 합치지는 않는다.
- `Backend Engineer — Docker, AWS`, `ML platform backend`, `Backend engineer working on AI services`는 Backend다. `Data Engineer — Docker, Kubernetes`는 Data Engineer, `ML Engineer — Java, Spring Boot, PyTorch`는 ML, `DevOps Engineer — Python, SQL`은 DevOps다.
- 강한 Data Analyst 제목에 Tableau가 있어도 BI로 바꾸지 않는다. Backend 제목에 Kafka/Airflow가 있어도 Data Engineer로 바꾸지 않는다. 제목 자체가 충돌하면 기술 조합으로 한쪽을 선택하지 않는다.
- career 필드는 분류에 사용하지 않는다. `경력무관`→`경력`은 normalizer의 별도 결함이므로 그대로 남아 있다.

### 호환성과 한계

role_counts/role_skill_counts는 새로운 label을 그대로 집계한다. 공고·기술 순서와 Counter 누적 방식은 변경하지 않았다. 기술 없는 미분류 공고도 role_counts에는 포함되며 기존처럼 role_skill_counts에는 빈 항목을 강제로 만들지 않는다. 빈 입력 계약과 기존 샘플 12건의 기술·직무·추천 결과는 유지된다. DB schema/version/identity/migration 및 기술 추출은 변경하지 않았다.

UI selector는 공유 ROLE_LABELS를 사용하여 확장된다. 새 역할과 미분류에는 추천 foundation을 만들지 않았다. 기존 추천 공식은 해당 역할 빈도가 있으면 사용하고, 없거나 비어 있으면 전체 빈도로 대체한다. 이때 목표 직무 빈도라는 기존 설명이 실제 근거와 다를 수 있고 미분류는 직무 목표가 아니므로, Phase 2C에서 fallback·설명·선택 정책을 검토해야 한다.

규칙은 부정문, 다른 팀 직무 인용, 제목 안의 주업무/부업무 문법, 복잡한 조사·복수형을 완전히 해석하지 않는다. 명시된 혼합 직무는 미분류 비율을 높일 수 있다. 일반 server/플랫폼/AI, JavaScript+TypeScript는 의도적으로 보수적이며 frontend framework 기술 조합은 아직 없다. Data Scientist를 ML에 포함한 넓은 범주와 BI/통계 혼합 공고는 실제 코퍼스로 추가 평가할 여지가 있다. 새로운 기술·역할·추천 모델을 이 단계에서 선제 도입하지 않는다.

## Phase 2C 학습 추천 계약

2026-09-16 기준. 앞의 Phase 2B 추천 설명은 당시 기록이며 이 절이 대체한다.
추천은 **현재 분석한 데이터에서 목표 역할을 준비할 때 미보유 기술 중 무엇을 먼저
학습 후보로 검토할지**를 제안한다. 합격 확률·채용 가능성·공고별 적합도·전체 시장
점유율을 계산하지 않는다. 학습 순서는 교육과정의 선수 관계나 숙련도를 뜻하지 않는다.

### 관측 근거와 기초 지식

- market_count는 role_skill_counts[target_role][skill]이다. 해당 역할로 분류된
  공고의 title/description에서 기술이 추출된 공고 수이며 한 공고 안의 반복 언급은 한 번이다.
  다른 역할·미분류 공고와 global skill_counts는 추천 근거에 합치지 않는다.
- role_posting_count는 role_counts[target_role]이다. 기술이 없는 공고도 포함한다.
  완전한 analyzer 결과에서 없는 역할은 0이다. 기존 부분 dict 입력에서 role_counts 키가
  아예 없으면 None이며, 이를 0이나 전체 공고 수로 추정하지 않는다.
- 숫자 비율 필드는 도입하지 않았다. 설명의 `N건 중 M건`에서 N은 항상 목표 역할 공고 수다.
  전체 기술 수·언급 총합·모든 역할 공고 수를 분모로 쓰지 않는다. 0건은 나누지 않고 기초
  추천이라고 설명하며 None은 분모 미제공이라고 명시한다.
- 기초 목록은 관측 데이터와 별개의 작은 학습 제안이다. 의무 요건도 시장에서 입증한 순위도
  아니다. 가산점은 없고 공고 언급 건수를 바꾸지 않는다. 후보 추가와 동일 건수의 동점 처리에만 쓴다.

| 역할 | 기초 학습 후보 | 선정 범위 |
|---|---|---|
| 백엔드 | Git, REST API, SQL | 버전 관리, API, 관계형 데이터 접근 |
| 프론트엔드 | Git, JavaScript | 버전 관리와 웹 프로그래밍 언어 |
| 풀스택 | Git, JavaScript, REST API, SQL | 웹 UI와 API·데이터 접근의 연결 |
| 데이터 분석가 | Python, SQL, Statistics | 분석 자동화, 질의, 통계 해석 |
| BI 분석가 | Excel, SQL, Statistics | 표 기반 분석, 질의, 지표 해석 |
| 데이터 엔지니어 | Git, Python, SQL | 파이프라인 코드 관리, 스크립팅, 데이터 질의 |
| ML 엔지니어 | Machine Learning, Python, Statistics | 모델 개념, 구현, 통계 평가 |
| DevOps / 클라우드 | CI/CD, Git, Linux | 배포 자동화, 버전 관리, 운영 환경 |

이 목록은 완전한 교육과정이 아니며 Python/Excel/Linux 등도 모든 공고의 필수 조건은 아니다.
기존 Data/AI 목록의 특정 BI 도구·분산 처리 도구·클라우드·ML 프레임워크 고정은 줄였다.
Java/Spring Boot, 특정 DB, 클라우드 사업자, frontend framework는 관측 공고가 언급하면
시장 후보로 추천한다. 현재 taxonomy 밖의 기술을 새로 만들거나 사용자 개인의 Java 선호를
보편적 기초로 넣지 않는다. 목록 선언 순서에는 우선순위가 없다.

### fallback과 미분류 정책

역할 공고가 0건이면 기초 후보만 반환하고 역할 공고가 없다고 설명한다. 공고는 있지만
기술 집계가 비어 있는 경우에는 추출된 언급이 없다고 설명한다. 특정 기초 기술이 관측되지
않은 경우도 동일하게 foundation_only로 표시한다. 기초 기술이 시장에 함께 관측되면
role_market와 is_foundation=True를 동시에 반환하고 설명에도 두 근거를 함께 쓴다.

미분류 / 기타는 일관된 목표 직무가 아니므로 추천하지 않는다. 데이터가 있어도 []이며
가짜 foundation이나 전체 시장 fallback이 없다. 미지원·오타·영문 역할 별칭도 []다.
호출자는 공유 canonical ROLE_LABELS를 사용한다. UI는 미분류 선택 시 구체적인 역할 선택을
안내하며, 기초 후보까지 모두 보유했다면 남는 후보가 없다고 표시한다.

### 반환 계약과 정렬

기존 함수명·인수·목록 반환 형태는 유지하며 각 항목은 models.SkillRecommendation TypedDict다.
score 제거는 의도적인 소비 계약 변경이며 저장 스키마나 AnalysisResult는 바꾸지 않았다.

| 필드 | 타입 | 의미 |
|---|---|---|
| skill | str | canonical 기술명 |
| priority | int | 보유 기술 제외 후 1부터 연속한 표시 순위. 낮을수록 먼저 검토 |
| market_count | int | 목표 역할 공고의 실제 추출 건수, 미관측 기초 후보는 0 |
| role_posting_count | int 또는 None | 역할 공고 수, 부분 입력에서 미제공이면 None |
| is_foundation | bool | 해당 역할 기초 후보 목록의 구성원 여부 |
| evidence_source | role_market 또는 foundation_only | 관측 언급 존재 여부. 둘 다 해당하면 role_market + is_foundation=True |
| reason | str | 관측 건수와 기초 여부, 또는 데이터 부재/추출 부재를 설명하는 한국어 문장 |

정렬 키는 `(-market_count, not is_foundation, skill.casefold(), skill)`이다.
시장 건수가 우선하고, 같은 건수면 기초 기술, 그래도 같으면 canonical 이름 오름차순이다.
Counter 삽입 순서·공고 순서·기초 목록 순서·set 순서와 무관하며 이름 순서는 중요도 주장이 아니다.
시장 언급 1건도 관측 0건인 기초 기술보다 앞선다. 숨은 보너스나 소수 가중치는 없다.

owned_skills는 기존 canonicalize_skills를 사용하고 set으로 중복 제거한다.
springboot/Spring Boot, postgres/PostgreSQL, k8s/Kubernetes는 같은 기술로 제외한다.
보유 기술 제외를 limit 적용보다 먼저 수행한다. limit<=0이면 [], 양수이면 최대 limit개,
후보보다 크면 남은 후보 전부를 반환한다. 입력 분석·보유 목록은 수정하지 않는다.

### 한계와 후속 작업

관측 건수는 수집된 표본의 단순 언급이며 실제 필수·우대·숙련도·부정문을 판별하지 않는다.
데이터 크기·최신성·출처·중복 공급자·분류 오류가 결과에 영향을 준다. 분석 함수에 직접 중복
공고를 넣으면 입력 행대로 세며 추천기가 identity를 재해석하거나 중복 제거하지 않는다.
기존 sample/DB 선택·혼합 정책도 그대로다. 샘플 12건에는 소프트웨어 역할 공고가 없으므로
그 역할은 기초 후보만 보이는 것이 정상이다. 실제 코퍼스 품질·전체 시장 대표성은 검증하지 않았다.

TypedDict는 런타임 검증기가 아니다. 건수는 analyzer의 일관된 비음수 집계를 전제로 하며
외부에서 임의로 만든 모순된 집계를 정정하지 않는다. 부분 dict 호환은 결측 집계 허용을 뜻한다.
경력무관(KD-08)은 추천·분류 입력에 필요하지 않아 그대로 두고 경력 해석 유지보수(기존 Phase 4C)
대상으로 남긴다. 공고별 매칭·프로필·지원 관리·Phase 3는 구현하지 않았다.

## 데이터 소스

1차 데이터 소스는 고용24 채용정보 Open API입니다. API 키가 없거나 네트워크가 제한된 환경에서는 샘플 데이터를 사용합니다.

## 수집 항목

| 필드 | 설명 | 예시 |
| --- | --- | --- |
| source | 데이터 출처 | work24 |
| posting_id | 공고 고유 ID | K123456789 |
| company | 회사명 | 데이터랩 |
| title | 공고 제목 | 데이터 분석가 채용 |
| description | 상세 설명 또는 요약 | SQL/Python 기반 분석 |
| region | 근무지역 | 서울 |
| career | 경력 조건 | 신입 |
| education | 학력 조건 | 대졸 |
| salary_type | 급여 형태 | 연봉 |
| salary | 급여 텍스트 | 3000만원 이상 |
| job_code | 직종 코드 | 134 |
| registered_at | 등록일 | 2026-06-02 |
| closing_at | 마감일 | 2026-06-30 |
| url | 공고 URL | https://... |

## SQLite 테이블

### job_postings

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| posting_id | TEXT PRIMARY KEY | 공고 ID |
| source | TEXT | 출처 |
| company | TEXT | 회사명 |
| title | TEXT | 제목 |
| description | TEXT | 상세/요약 |
| region | TEXT | 지역 |
| career | TEXT | 경력 |
| education | TEXT | 학력 |
| salary_type | TEXT | 급여 형태 |
| salary | TEXT | 급여 |
| job_code | TEXT | 직종 코드 |
| registered_at | TEXT | 등록일 |
| closing_at | TEXT | 마감일 |
| url | TEXT | 공고 URL |
| created_at | TEXT | 저장 시각 |

### posting_skills

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| posting_id | TEXT | 공고 ID |
| skill | TEXT | 추출된 기술 |

## 정제 규칙

- 지역은 첫 번째 시/도 단위 중심으로 표준화한다.
- 경력은 위 Phase 2D 계약의 `미상`, `신입`, `경력`, `무관`, `신입/경력`, `기타`로 표준화한다.
- 기술명은 대소문자와 별칭을 통일한다.
- 동일 `posting_id`는 중복 저장하지 않는다.

## 기술 키워드 예시

- 언어: Python, Java, SQL, R
- 분석: Pandas, NumPy, Statistics, A/B Test
- 시각화: Tableau, Power BI, Looker, Plotly
- 엔지니어링: Spark, Airflow, Kafka, Docker
- 클라우드/DB: AWS, GCP, Azure, MySQL, PostgreSQL, MongoDB
- ML/AI: Machine Learning, Deep Learning, NLP, PyTorch, TensorFlow
