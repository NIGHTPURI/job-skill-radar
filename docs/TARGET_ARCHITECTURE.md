# Target Architecture — 개인용 Job Intelligence

## Phase 7B 현재 경계 (2026-09-17)

schema v4: 자동 발견 실행/소속을 discovery_storage에 추가했다. 7A 코어의 마지막 저장에만
실행 기록을 묶고 네트워크 경계는 유지한다. 완성된 실행만 원자적으로 보이므로 프로세스 종료
중 실행에는 이력이 없을 수 있다. 예상 API 실패는 partial/failed로 저장한다. DB/프로그래밍
오류는 성공으로 숨기지 않고 전파한다. 파생 비교/shortlist/시장 snapshot은 저장하지 않는다.
검증된 고정 계획과 안전 category만 저장하며 extra field와 모순된 count/status를 거절한다.
run의 profile_revision은 계획의 출처이며 현재 프로필과 달라도 과거 값을 바꾸지 않는다.


## Phase 7A 현재 경계 (2026-09-17)

최신 단계는 사용자 정의 자동 발견 Phase 7A다. 지원 추적/점수는 범위 밖이다.
discovery.build_discovery_plan은 시간·DB·HTTP·UI 없는 순수 역할 계획이다.
discovery_pipeline.discover_work24_jobs는 저장 프로필→계획→순차 목록→중복 제거→제한 상세→
discovery_storage의 짧은 atomic 저장 순이다. HTTP 동안 열린 DB 연결이 없다.
Work24 외 source는 받아들이지 않는다. query별 발견 provenance와 안전한 실패 category를
반환한다. 기존 pipeline 목록/상세 함수, raw, 추출기, matcher, 시장 집계는 변경하지 않는다.
모든 결과를 받아 마지막 저장하므로 프로세스 강제 종료/예상 밖 오류 시 미저장 실행은 사라질 수
있다. 재시도/실행 중 상태/데몬은 없다. 예산과 의미는 데이터 설계 Phase 7A 절을 따른다.


## Phase 6A 현재 구현 경계 (2026-09-17)

최신 완료 상태는 Phase 4A·5·6A, schema v3, extractor v2다. 아래 단계별 기록은 완료 당시 상태다.
UI → pipeline.load_posting_comparison → profile/detail readers 종료 → pure matcher 순이다.
비교 결과는 현재 profile revision과 원문/fetched_at/extractor version에서 다시 계산한다.
캐시·matcher 테이블·schema v4·점수 subsystem은 없다. comparison 모델에는 상태와 provenance만 있다.

독립 근거와 all_of/any_of를 별도 단위로 처리해 그룹 구성원을 독립 mandatory gap으로 중복
표시하지 않는다. OR 하나 충족, AND 전체/일부/미등록, 우대/업무/미분류의 서로 다른 의미를
유지한다. 충돌·긍정/부정 근거는 review에 남긴다. 전역 적합도 verdict를 반환하지 않는다.
지역은 정확한 단일 시·도 원문과 선언된 선호/필수 목록만 비교하며 나머지는 unknown이다.
목표 직무 포함 여부는 안내용이고 기술 조건을 덮어쓰지 않는다. 전체 시장 빈도·역할 분류·
학습 추천 로직은 계속 별도다. 기존 상세 추출/평가 corpus도 변경하지 않았다.

아침 흐름은 공고 직접 등록 → 저장한 공고/원문·요건 → 내 프로필 저장 → 재시작 → 공고에서
‘내 프로필과 비교’다. AppTest로 이 전체 흐름과 이후 본문 수정 재계산을 검증했다.
Phase 6B 숫자 점수·후보 순위·합격 확률은 의도적으로 미구현이다.

## Phase 5 현재 구현 경계 (2026-09-17)

현재 schema v3와 단일 로컬 프로필을 사용한다. profile.py는 기존 taxonomy/역할 기반 순수
검증·정규화, profile_storage.py는 singleton 저장·revision, profile_ui.py는 편집 화면이다.
app → pipeline load/save_profile → profile_storage 순이며 UI SQL·로그인·멀티유저는 없다.
선호/필수 지역은 다른 필드이고 연차·고용 형태는 아직 해석하지 않는다. 파생 요건은 저장하지 않는다.
v2→v3는 additive이고 기존 공고/raw 데이터와 FK를 그대로 유지한다. v0/v1 경로·사전 고유 백업·
rollback·재개방도 검증했다. 상세 계약은 데이터 설계의 Phase 5 절을 따른다.
이하 이전 단계의 schema v2/미시작 설명은 완료 당시 기록이다.

## Phase 4A 실제 구현 경계 (2026-09-17)

현재 수동 공고 흐름은 app → review_ui → pipeline create/update/list/review → storage다.
manual_postings는 입력 검증과 원문/list 표현 생성만 담당한다. Streamlit에는 SQL이 없다.
수동 공고의 두 테이블 쓰기는 원자적이며 조회 연결 종료 후 기존 requirement extractor를 쓴다.
schema v2·추출기 v2·그룹 의미·원문 보존·고용24 수집 경계는 유지한다.
시장 화면만 명시적으로 Work24 범위를 선택한다. 수동 공고는 개별 검토 자료이고 표본 시장
빈도로 자동 편입하지 않는다. 회사/제목/본문 등록→영속 목록→원문/구조화 요건→동일 ID 수정이
가능하다. 실 UI 테스트와 bounded headless 서버 smoke를 수행했다. 삭제는 이번 범위에 없다.

이하 Phase 3C 완료 당시 기록(2026-09-17). 최신 기능은 위 Phase 4A 경계를 따른다.
Phase 3A 원문 수집·schema v2와 기존 시장 추출·분류·추천·경력 정규화는 유지한다.
Phase 3C 계약은 [데이터 설계](02_data_design.md#phase-3c-요건-의미-보강평가-계약),
검증은 [테스트 기준선](TEST_BASELINE.md#phase-3c-검증-2026-09-17)을 따른다. Phase 4 이상은 미시작이다.
아래 이전 단계 기록과 장기 구조는 당시 현황·설계 제안이다.

Phase 0 당시 사실은 [감사 문서](REFACTORING_AUDIT.md), 적용 순서는 [로드맵](ROADMAP_V2.md)을 따른다. Phase 1C 저장 무결성·마이그레이션 계약은 계속 유지한다.

## Phase 3C 실제 구현 경계

순수 추출기는 버전 2다. taxonomy 기반의 제한된 나열 문법으로 all_of/any_of를 구별한다.
any_of의 필수/우대 의미는 그룹에만 있고 개별 구성원은 unspecified 근거를 받는다.
독립 근거는 기존 우선순위로 모으되 그룹·약한 근거·반복 위치를 보존한다. 알려지지 않은 대안
구성원을 삭제한 불완전 그룹이나 중첩 boolean tree를 만들지 않는다. 부정된 나열/제목의 범위,
Qualifications·wrapper 콜론, 명시적 사용 능력/업무 표현을 보강했다. offsets는 계속 원문 slice다.

```text
evaluate_requirements.py → committed synthetic/manual corpus
  → requirement_evaluation.evaluate_requirements
    → pure extract_requirements → skills + groups + exact provenance + quality
    → fixture-only class/group TP/FP/FN + precision/recall/F1 + mismatched cases
    → strict reviewed-label gate (including zero required/preferred false positives)
```

평가 모듈은 I/O 없는 비교 함수이고 CLI만 fixture 파일을 읽는다. HTTP/SQLite/키가 필요 없다.
기존 조회 pipeline과 inspect CLI는 버전 2 결과를 그대로 전달한다. 수집 경로에는 추출을
삽입하지 않았으며 파생 DB/cache도 없다. schema v2·migration·백업·실패 refresh 보존은 그대로다.
네 품질 상태는 유지하며 분류된 그룹도 requirements_extracted의 근거다.

합성 수동 corpus 60개에서 v1 40/60사례·128/144분류·필수 오탐 3건 → v2 60/60·144/144·
13/13그룹·필수/우대 오탐 0건이다. 클래스별 수치는 테스트 기준선에 기록했다.
이는 규칙을 보정한 **fixture 지표이며 실공고 정확도가 아니다**. 실 API smoke는 미실행이다.
중첩 대안·복잡한 부정/예외·임의 제목·미지원 기술은 여전히 검토가 필요하다.
시장 분석·직무 분류·학습 추천·경력 정규화·Streamlit은 변경하지 않았다. 프로필/매칭/Phase 4는 없다.

## Phase 3B 실제 구현 경계

아래는 완료 당시 버전 1 기록이다. 새 그룹과 보강된 의미는 위 Phase 3C 계약을 따른다.

`requirement_extractor.py`가 기존 `extract_skills`/taxonomy를 사용하는 순수 추출 함수다.
제한된 행·섹션 문맥을 required/preferred/responsibility/unspecified로 분류한다. 원문·위치·섹션·
규칙 코드를 유지하고 canonical 기술별로 대표 분류와 전체 근거를 모은다. model 계약은 기존
TypedDict 형식이다. 추출기 버전 1과 네 품질 상태, 네 비기술 원문 조건도 별도로 반환한다.

```text
inspect_requirements.py / application caller
  → pipeline.load_posting_requirements(source, posting_id, db_path)
    → storage.load_posting_detail_from_db → close connection
    → extract_requirements(detail or None)
      → source sections/clauses + existing canonical skill detection
      → local classification + all evidence + deterministic aggregation
      → quality status + minimally interpreted source conditions
```

단일 공고의 근거 검토는 저장된 raw detail에서 재계산하므로 파생 테이블/cache는 도입하지 않았다.
schema v2·v0/v1 이전·백업·FK는 그대로다. 규칙 변경 뒤 재호출하면 새 버전 결과를 얻는다.
성공 refresh 뒤에는 새 원문, 실패 refresh 뒤에는 기존 원문을 사용한다. 추출 오류는 전파하고
raw DB나 이전 반환값을 수정하지 않는다. 추출 중 DB 연결·HTTP 요청을 유지하지 않는다.

기존 수집 함수와 시장 analyzer/recommender는 새 파생값을 사용하지 않는다.
필수 기술 수가 비었다는 사실을 고용주 요건 부재로 해석하지 않는다. 미지원 기술·부정·대안·
복잡한 문맥은 원문 검토가 필요하다. Streamlit은 변경하지 않고 작은 JSON 검사 CLI만 추가했다.
job matching·점수·프로필·LLM·Phase 4 이상은 없다.

## Phase 3A 실제 구현 경계

새 서비스 계층 없이 기존 모듈을 확장했다. models는 `DetailEvidence`, `PostingDetail`,
`DetailFailure`, `CollectionResult` dict 계약을 제공한다. Work24 client가 공식 상세 요청,
XML 구조·응답 identity 확인, 안전한 오류 범주와 성공 UTC 관측 시각을 소유한다.
원문 20개 필드와 순서·중복을 보존하는 keywords만 선택하며 연락처·전체 응답 XML은 저장하지 않는다.

```text
CLI --with-details
  → collect_work24_with_details_to_db
    → collect_postings: list HTTP → normalize/deduplicate (source, posting_id)
    → save_postings_to_db: atomic list batch → close connection
    → each identity: detail HTTP (no DB connection)
      → success: save_posting_details_to_db → close connection
      → Work24Error: append safe DetailFailure; preserve previous detail; continue
  → counts and failures; exit 0 / partial detail failure 2
```

목록 실패는 기존처럼 목록 저장 전에 중단되며 CLI는 안전한 범주와 exit 1을 반환한다.
기존 `collect_work24_to_db`는 int 반환과 목록 전용 트래픽을 유지한다. 상세 수집은 opt-in이며
실행마다 수집된 identity를 한 번만 갱신한다. DB/프로그래밍 오류는 그대로 전파한다.

storage는 상세 conn/path API와 SAVEPOINT 배치를 제공한다. 성공 응답만 upsert하고,
실패한 refresh는 이전 상세·fetched_at을 보존한다. migrations는 fresh→v2, v0→v1→v2,
추가 방식 v1→v2를 단일 transaction으로 처리한다. 복합 FK/CASCADE와 caller transaction을 유지한다.
파일 백업은 이전 전에 `.pre-v2-from-vN-<고유값>.bak`으로 만들고 실패하면 이전을 중단한다.
v2 재개방은 멱등적이며 추가 백업을 만들지 않는다. v0의 기존 기술 재구성 정책과 v1의 정확한
행 보존은 구별한다. 복원·동시 writer 제한은 데이터 설계에 명시했다.

상세 evidence는 기존 analyzer/extractor/classifier/recommender 경로에 연결하지 않는다.
목록 description과 정규화 career는 그대로이며 raw_career_condition은 별도 원문이다.
요건 해석·LLM·매칭·사용자 기능·Phase 3B는 구현하지 않았다.
아래 장기 설계의 snapshot·수집 이력·TTL·백오프·새 UI는 현재 기능이 아니다.

## Phase 2C 변경 전 추천 감사 (2026-09-16)

운영 코드 수정 전에 확인한 입력은 target_role 문자열, owned_skills 목록, analysis dict,
limit(기본 8, UI 6, CLI 5)이다. 보유 기술은 기존 canonicalize_skills로 별칭을 통합하고
set으로 중복을 제거한다. 역할명 자체의 별칭 정규화는 없다.

role_skill_counts[target_role]가 존재하고 비어 있지 않으면 이를 복사하며, 없거나 비면
skill_counts 전체 빈도로 조용히 대체한다. 기존 foundation은 데이터 분석가
SQL/Python/Statistics/Pandas/Tableau, BI SQL/Power BI/Tableau/Excel/Looker,
데이터 엔지니어 SQL/Python/Spark/Airflow/AWS, ML Python/Machine Learning/PyTorch/Deep Learning/SQL이다.
각 목록 앞에서부터 5/4/3/2/1을 더하며 관측되지 않은 기술도 후보에 넣는다.
새 소프트웨어 역할과 미분류에는 foundation이 없다.

따라서 score는 선택한 Counter의 공고 언급 건수 + 임의의 기초 가산점이다.
샘플 Python 9는 분석가 공고 5건 + 기초 가산 4이며 확률·적합도·시장 비율이 아니다.
Counter.most_common 내림차순에서 보유 기술을 건너뛰며 동점은 Counter 삽입 순서에 따른다.
기초 기술 설명은 시장 근거를 가리고, 나머지는 global fallback도 목표 직무 빈도라고 설명한다.
추가 후 limit을 검사하므로 후보가 있으면 0과 음수에도 1개를 반환한다.

수정 전 검증: 전체 210개 중 208 통과·예상 실패 2(0.565초), 추천 12개 중
11 통과·예상 실패 1(0.002초), analyzer 17개 통과(0.011초). CLI는 12건과
Python 9/Statistics 4/Tableau 3/Pandas 3/A/B Test 2를 출력했고 git diff --check도 exit 0이다.
일반 실패·오류는 없다. 경력무관 결함은 career 정제만의 문제이며 추천 입력에 필요하지 않다.

### Phase 2C 실제 구현 경계

recommender는 analyzer가 만든 집계만 소비하는 순수 함수다. SQLite·네트워크·Streamlit을
참조하지 않으며 analyzer나 classifier를 다시 실행하지 않는다. models의 SkillRecommendation
TypedDict는 런타임 dict를 유지한다. 기존 score 키는 제거하고 priority, market_count,
role_posting_count, is_foundation, evidence_source와 reason을 반환한다.

역할별 언급 건수 내림차순 → 기초 여부 → canonical 이름 순으로 정렬한다.
8개 구체적 역할에는 작은 기초 후보를 제공하고 미분류·미지원 역할에는 빈 목록을 반환한다.
역할 데이터가 없으면 기초 후보만 남기며 전체 빈도로 대체하지 않는다. UI는 입력 역할과
기존 role_counts/role_skill_counts로 빈 결과와 데이터 부족을 안내하고 각 항목의 설명을 표시한다.
새 응답 wrapper나 별도 서비스는 필요하지 않다. CLI/UI는 score 대신 순위를 소비한다.

## Phase 2B 실제 구현과 변경 전 분류 감사

변경 전 `analyzer.classify_role`의 판정 순서는 다음과 같았다. 모두 단순 부분 문자열 또는 기술 집합 교집합 검사였으며 처음 일치한 분기가 반환되었다.

| 순서 | 근거 위치·조건 | 결과 |
|---|---|---|
| 1 | 제목: bi 또는 kpi | BI 분석가 |
| 2 | 제목: 데이터 분석, 분석가, 분석 담당 | 데이터 분석가 |
| 3 | 제목+본문: 엔지니어, 파이프라인, etl, 플랫폼 또는 기술: Spark/Airflow/Kafka/Docker/Kubernetes 중 하나 | ML 기술이 있으면 ML, 없으면 데이터 엔지니어 |
| 4 | 제목+본문: 머신러닝, ml, ai, 딥러닝, nlp 또는 기술: Machine Learning/Deep Learning/NLP/PyTorch/TensorFlow 중 하나 | ML 엔지니어 |
| 5 | 제목+본문: bi, 대시보드, dashboard, kpi 또는 기술: Tableau/Power BI/Looker 중 하나 | BI 분석가 |
| 6 | 위 조건 미일치 | 데이터 분석가 |

3번의 ML 기술은 4번과 같은 집합이다. 이 순서 때문에 Docker 하나가 Backend 제목을 무시하고 데이터 엔지니어를 선택했다. mobile의 bi, retail/email의 ai도 잘못된 근거가 됐다. 영어 Backend/Frontend/DevOps 직무는 표현할 수 없었고 무근거 fallback은 분석가 빈도를 부풀렸다. 주어진 입력에서 결과 자체는 결정적이었지만 업무상 우선순위가 잘못되어 있었다.

`경력무관` 예상 실패는 별개다. `normalize_career`가 무관보다 경력 포함 여부를 먼저 검사해 발생하며, classifier는 career를 읽지 않는다. 해당 정상화 규칙과 expectedFailure는 변경하지 않았다.

현재 구조는 작은 `role_classifier.py` 하나에 9개 canonical label, 제목/업무 구문 표, 경계 helper, 기술 조합 predicate, 충돌 해결 규칙을 둔다. `analyzer`는 기존 import 경로 호환을 위해 ROLE_LABELS/classify_role을 재노출하고 enrichment·Counter 집계만 유지한다. 숫자 가중치·가짜 confidence·새 result model은 없다.

명시적 제목 → 업무/도메인 → 기술 조합 순서이며 같은 단계의 충돌은 미분류다. 더 긴 복합 구문이 포함된 일반 구문보다 우선하고, 명시적 Full-stack은 Backend/Frontend 조합을 포괄한다. 상세 규칙과 예외는 데이터 설계를 따른다.

Streamlit은 기존에 analyzer.ROLE_LABELS를 import하므로 추가 역할이 자동으로 selector에 나타난다. 기존 4개 label·순서를 유지하고 5개를 뒤에 추가했다. UI·모델·DB·추천 코드는 수정하지 않았다. 새 역할에 foundation이 없어도 기존 추천기가 역할 빈도 또는 전체 빈도를 사용한다. 이 fallback의 제품상 적절성과 설명 문구는 Phase 2C 검토 대상이다.

## Phase 1C 실제 구현 현황

- 현재 identity는 **(source, posting_id)** 복합 PK다. 불필요한 surrogate ID는 도입하지 않았다. 정제 중 중복 제거도 같은 복합 키를 사용하며 동일 키는 수집 배치의 첫 행을 유지한다.
- `migrations.py`가 FK 활성화, user_version=0→1 검사·이전, 신규 schema 생성과 legacy 파일 백업을 담당한다. SQL 리소스 폴더/프레임워크 없이 Python 모듈 하나에 명시적 DDL을 둔다. `storage.ensure_schema` import 경로는 호환 유지한다.
- `storage.save_postings`는 identity를 검증한 후 전체 입력 배치를 savepoint로 저장한다. 공고 upsert와 해당 identity의 기술 삭제·재추출·삽입은 원자적이다. 직접 저장한 batch 안에서 같은 identity가 반복되면 마지막 값이 남는다.
- 저장 반환값은 기존 UI/CLI의 의미대로 **신규 identity 수**다. 갱신은 0을 더한다. 선택 필드 누락은 이전 값 유지가 아닌 NULL 교체다. created_at은 최초 값 유지, updated_at은 추가하지 않았다.
- FK는 `(source, posting_id)`를 참조하고 ON DELETE CASCADE다. 모든 app connection에서 활성화하고 raw sqlite3 connection도 schema 진입 시 확인한다. FK OFF인 활성 transaction은 조용히 commit하지 않고 거절한다.
- legacy 공고의 14개 필드와 created_at을 그대로 복사한다. 기술은 보존한 title/description에서 현행 extractor로 재구성하여 이전 누적 결함을 제거한다. 본문과 일치하는 기존 기술은 유지되며, orphan/불일치/복원 기술 수를 로그로 보고한다. 파일 백업에는 원래의 모든 행이 남는다.
- normalize_career의 `미상`만 canonical 값으로 인식하도록 수정했다. `경력무관`의 기존 오분류와 taxonomy/추천/분석 규칙은 변경하지 않았다.

자세한 스키마·백업·실패 정책은 [데이터 설계](02_data_design.md#phase-1c-현재-영속-계약)를 따른다. storage 내부의 기술 추출은 같은 저장 표현에서 파생값을 만드는 실제 무결성 경계로 유지했다. 외부 raw SQL로 본문만 수정하는 작업까지 기술 일치를 보장하는 DB trigger는 없으므로 정상 공고 쓰기는 save_postings를 사용해야 한다. 외부 도구가 FK를 끄면 DB 제약도 우회할 수 있다.

## Phase 1B 구현 기록 (당시 기준)

새 디렉터리·서비스 클래스 없이 `models.py`만 추가했다. `JobPosting`과 `AnalysisResult`는 표준 라이브러리 TypedDict다. 현재 API가 부분 dict, None, 추가 필드를 허용하므로 dataclass로 일괄 변환하기보다 런타임 dict를 유지하는 최소 계약을 택했다. 타입 선언은 입력 검증이나 강제 변환이 아니다. 전체 프로젝트의 정적 타입 검사를 완료했다는 의미도 아니다.

### 확인한 공고 계약

| 구분 | 현재 필드·의미 |
|---|---|
| 기본 14개 | source, posting_id, company, title, description, region, career, education, salary_type, salary, job_code, registered_at, closing_at, url |
| 필수 입력 | 모든 함수에 공통인 필수 키는 없음. clean_posting은 {}도 받지만 clean_postings는 빈 ID를 제외. Work24 parser는 14개 키를 모두 생성하며 값은 빈 문자열일 수 있음 |
| persistence 제약 | posting_id는 기존 PK, source/created_at은 NOT NULL. source나 ID에 새 검증을 추가하지 않음. 직접 storage 호출의 NULL·오류·orphan 동작 보존 |
| 선택·결측 | storage의 누락 기본 필드는 None으로 조회될 수 있음. 정제는 문자열로 바꾸지만 analyzer 직접 호출은 키 부재와 None을 구별함 |
| 생성 필드 | analyzer가 skills:list[str], role:str을 추가/덮어씀. 추가 사용자 필드는 analyzer가 유지하지만 normalizer는 제거 |
| storage 전용 | created_at은 저장 시 생성하고 기존 조회 결과에는 포함하지 않음. 모델에 추가하지 않음 |
| UI 전용 | source_label, mode, Counter의 차트 열 이름, 쉼표로 연결한 skills 표시값. 영속 공고 계약에 포함하지 않음 |

`POSTING_FIELDS`는 모델의 기본 필드 선언 순서에서 유도한다. normalizer의 기존 REQUIRED_FIELDS와 storage 조회 매핑이 이를 공유한다. SQL SELECT/INSERT는 읽기 쉬운 명시적 SQL로 유지하고 DDL·save 본문은 변경하지 않았다. 모델의 기본 필드 순서를 변경한다면 SQL 열 순서와 계약 테스트를 함께 검토해야 한다.

`AnalysisResult`는 기존 postings와 skill_counts/role_counts/career_counts/region_counts/role_skill_counts를 이름과 타입으로 명시한다. 분모·프로필·매칭·새로운 분석 정보는 넣지 않았다. recommendation은 기존 partial dict 입력 및 점수 계산을 그대로 사용한다.

### 구현된 경계

```text
app.load_analysis (Streamlit cache, 기존 ttl=60)
  → pipeline.load_analysis (DB 우선 / 빈 DB 샘플 / 샘플 전용 정책)
    → pipeline.load_db_analysis → storage.load_postings_from_db
    → pipeline.analyze_sample

pipeline.collect_work24_to_db / collect_and_analyze
  → pipeline.collect_postings (키워드 루프 → 기존 정제·중복 제거)
    → collector callable (기본 Work24 HTTP/XML client)
  → storage.save_postings_to_db 또는 순수 analyzer
```

- storage의 두 path 함수가 연결 생성·종료를 소유한다. 기존 conn 기반 함수도 유지한다. contextlib.closing은 연결을 닫으며 새로운 transaction 정책을 도입하지 않는다. 읽기 시 schema 생성, save commit, 기술 재추출과 중복 불일치도 기존대로다.
- pipeline의 DB 함수는 keyword-only `db_path`를 선택적으로 받는다. 생략 시 기존 config를 호출하고, 제공하면 사용자 환경을 읽지 않는다.
- 수집 함수는 keyword-only `collector` callable을 선택적으로 받는다. 서비스 클래스·provider 계층 없이 실제 HTTP를 대체할 수 있다. 각 callable은 auth_key/keyword/pages/display 키워드를 받는다. 분석 전용 경로의 display=100도 이제 명시적으로 전달하며 기본 HTTP 요청값은 동일하다.
- 모든 키워드 수집이 성공한 뒤 정제·저장한다. 중간 실패 시 저장하지 않는 기존 정책과 첫 ID 우선 중복 처리도 그대로다.
- app에는 cached wrapper만 남겼다. 차트·입력·메시지·캐시 TTL/clear 방식은 바꾸지 않았다. 오류가 나면 샘플로 자동 전환하는 새 동작도 넣지 않았다.
- analyzer는 I/O 없이 기존 계산을 유지하고 Work24 client는 HTTP/XML과 필드 매핑만 소유한다. recommender와 taxonomy는 수정하지 않았다.

검증: 112개(107 통과, 기존 예상 실패 5), 샘플 12건·추천 순서 유지. 자세한 결과는 [테스트 기준선의 Phase 1B 기록](TEST_BASELINE.md#phase-1b-검증-추가-2026-09-16)을 참고한다. 아래 장기 모델·디렉터리 중 migrations, role_classifier, matcher, taxonomy 파일 등은 아직 구현하지 않았다.

## 1. 설계 목표와 유지할 기반

한 사람이 로컬에서 공고를 모으고, 자신의 조건과 비교하며, 지원 과정을 기록하는 도구가 목표다. SQLite와 Streamlit을 유지한다. 현재 `pipeline.py`를 application 경계로 발전시키고 필요한 순수 함수·모델만 추가한다. 웹 서버, 인증 시스템, 범용 repository 계층, DI container는 현재 요구가 아니다.

UI는 입력·표시·화면 캐시를 맡고 application은 작업 순서·트랜잭션·오류 결과를 맡는다. domain은 기술·직무·요건·비교 계산을 담당한다. 외부 응답 구조는 collector 안에서 변환하며 SQLite의 행 구조는 storage 밖으로 퍼뜨리지 않는다. 분석과 개인 매칭은 서로 다른 결과와 용어를 쓴다.

## 2. 점진적 목표 디렉터리

다음은 최종적으로 필요한 파일의 후보이며 한 번에 scaffold하지 않는다. `domain/`, `services/`, `repositories/`라는 빈 디렉터리를 추가하지 않고 기존 평면 패키지를 유지한다.

```text
app.py                              Streamlit 구성·입력·표시·캐시
src/jobskillradar/
  config.py                         환경과 로컬 경로
  models.py                         실제 사용하는 dataclass/result 계약
  pipeline.py                       기존 application 진입점 및 작업 조합
  normalizer.py                     손실 없는 원본+정규화 정책
  skill_extractor.py                alias 매칭 및 evidence
  role_classifier.py                역할 규칙·근거·Unknown
  requirement_extractor.py           본문 섹션·필수/우대/미구분 추출
  analyzer.py                       공고 집계·분모·출처·기간
  recommender.py                    학습 우선순위와 계산 근거
  matcher.py                        프로필 대 공고 비교 순수 함수
  storage.py                        SQLite CRUD·트랜잭션 helper
  migrations.py                     스키마 버전·순차 migration 실행
  work24_client.py                  목록·검증된 상세 API adapter
  sample_data.py                    명시적 demo fixture
  taxonomy/
    skills.json                    canonical ID·alias·버전
    roles.json                     role ID·표시명·제목 alias
  migrations/
    001_*.sql                      첫 영속 스키마 변경 때 도입
scripts/                            기존 실행·수집·샘플 스크립트 유지
tests/
  test_*.py                        기존 unittest 구조 유지
  fixtures/work24/                 합성 또는 비식별 XML fixture
docs/                              계약·실행·계산 기준
data/                              로컬 DB 및 필요한 원문, Git 제외
```

새 디렉터리의 이유:

- `taxonomy/`: 엔지니어링 직군 확장 시 검색 지식과 Python 알고리즘을 분리하고 검증·버전 관리를 쉽게 한다. JSON을 사용해 YAML 의존성을 추가하지 않는다.
- `migrations/`: 최초 스키마 변경부터 기존 사용자 데이터를 지키는 순차 SQL이 필요하다. runner와 같은 stem을 사용하더라도 이 폴더는 import 패키지가 아닌 SQL 리소스 폴더로 취급한다.
- `tests/fixtures/work24/`: 네트워크 없이 실제 parser의 성공·오류·결측 계약을 테스트하기 위한 데이터다. 비밀과 개인 정보는 넣지 않는다.
- `data/`: 이미 config에 존재하는 로컬 실행 경로다. 서비스 계층이나 별도 데이터 플랫폼이 아니다.

새 파일의 이유:

- `models.py`: 지금 여러 dict에 복제된 필드·결측 의미를 통일한다. 모든 미래 모델을 선제 구현하지 않는다.
- `role_classifier.py`: taxonomy 확장 때 analyzer의 집계와 분류 규칙을 독립 검증할 수 있도록 한다.
- `requirement_extractor.py`: 기술 언급과 실제 필수·우대 요건은 다른 개념이므로 섹션 근거를 별도로 다룬다.
- `matcher.py`: 기존 시장 빈도 추천과 공고별 비교를 혼동하지 않게 한다.
- `migrations.py`: 현재 CREATE IF NOT EXISTS만으로는 기존 DB 구조를 안전하게 변경할 수 없다.

UI가 커져야 `ui/` 또는 Streamlit pages를 추가한다. 다른 실제 공급자가 생기기 전에는 collector interface hierarchy를 만들지 않는다. storage가 기능별로 커지는 시점에만 파일을 분리한다.

## 3. 의존성과 실행 흐름

```text
Streamlit / CLI
       ↓
pipeline (application)
   ├─ Work24 client → raw/list/detail 결과
   ├─ normalizer + extractor + classifier → domain 모델
   ├─ SQLite storage → 영속 공고·프로필·관측 기록
   └─ analyzer / matcher / recommender → 설명 가능한 결과
       ↓
UI 표시 모델·CLI 출력
```

domain 함수는 Streamlit·네트워크·SQLite를 import하지 않는다. 모델도 UI와 DB를 모른다. storage는 이미 계산된 기술·요건을 저장하며 extractor를 직접 실행하지 않는다. application은 명시적 DB 경로와 collector callable을 받을 수 있게 하는 정도로 테스트 경계를 만든다. 기존 CLI가 호출하는 함수는 호환 wrapper로 유지할 수 있다.

공고 입력은 두 경로다.

1. 수동 등록: 제목·회사·URL·본문·선택 메타데이터 입력 → application validation → 정규화·추출 → 공고 및 snapshot 저장.
2. Work24: 목록 수집 → 식별·변경 판단 → 검증된 detail 요청 → source DTO 변환 → 동일한 application 경로.

상세 실패 시 목록 공고를 버리는 대신 `list_only`/`detail_failed` 상태와 이유를 남기는 것이 목표다. 전체 성공을 가장하지 않고 수집/저장/갱신/중복/실패 수를 구분한다. 정책 확정 전 현재 반환 int를 조용히 다른 의미로 바꾸지 않는다.

## 4. 필요한 모델과 계약

| 모델 | 핵심 필드·규칙 | 도입 시점 |
|---|---|---|
| JobPosting | source/posting_id 복합 identity, title/company/url, 향후 원문·정규화 metadata·detail status | 현재 계약 유지, 추가 정보는 해당 기능 단계 |
| AnalysisResult | postings, counts, denominator, source scope, 기간·품질 요약 | 초기에는 기존 결과와 동등한 필드부터 |
| Skill / Role | stable ID, display name, aliases, version | taxonomy 확장 |
| SkillEvidence | skill ID, 원문 구간, 추출 rule/version | 본문 추출 |
| JobRequirement | kind(required/preferred/unspecified), skill/비기술 요건, 원문·섹션·추출 상태 | 본문 추출 |
| UserProfile / UserSkill | local profile ID, skills, target role IDs, 선호·제약, revision | 개인화 |
| JobMatchResult | matched/missing/unknown, 제약 평가, 계산 항목·분모·버전·근거 | 매칭 |
| SavedJob / Application | profile/posting, saved time, stage, notes, stage history | 추적 |
| SkillDemandSnapshot | period/scope/role/skill, 공고 분자·분모, observation/taxonomy version | 반복 관측 분석 |

단순 dataclass와 Enum/Literal로 시작한다. API 원본 dict는 collector 내부에 한정할 수 있다. 결측, 확인된 없음, 미수집, 추출 실패를 같은 빈 문자열로 표현하지 않는다. 원문과 정규화 값을 함께 남겨 잘못된 규칙을 나중에 재처리할 수 있게 한다.

## 5. 영속 설계와 이관

첫 변경 전에 기존 DB 백업·버전 식별·복원 테스트를 마련한다. migration은 transaction 단위로 실행하고 실패 시 기존 DB를 사용할 수 있어야 한다. 초기 sample/실데이터 혼재는 source로 분리하고 삭제하지 않는다.

- 공고: 현재 복합 PK(source, posting_id)를 유지한다. 향후 수동 공고는 `manual` source와 충돌 없는 ID를 사용한다. URL만으로 다른 공고를 무조건 합치지 않는다.
- 관측: collection_runs는 시작/종료/키워드/페이지/성공·실패 범위를 보존한다. posting snapshot은 내용 hash·관측 시각·출처·원문·정규화 결과를 연결한다. 같은 내용 재수집과 내용 변경을 구별한다.
- 최신 공고와 추출 결과: 한 transaction에서 같은 snapshot/version을 기준으로 갱신한다. 이전 기술을 무조건 누적하지 않는다. 기존 posting_skills를 유지할지 snapshot FK로 옮길지는 migration 설계에서 정한다.
- timestamps: published_at과 observed_at을 구분하고 관측 시각은 timezone이 명확한 UTC로 보존한다. 원본 날짜가 해석 불가하면 원문과 parse 상태를 남긴다.
- profile, user_skills, target_roles는 단일 사용자부터 시작한다. 계정·로그인 구조는 만들지 않는다.
- saved_jobs, applications 및 notes/stage history는 posting을 참조한다. UI 단계 전환은 이력과 함께 atomic하게 저장한다.
- 매칭은 처음에는 필요할 때 계산해도 된다. 저장할 때는 profile revision + posting snapshot + rule/taxonomy version을 함께 저장하여 오래된 결과를 식별한다.
- skill demand는 snapshot/run 자료로 SQL 집계부터 시작한다. 전용 요약 테이블은 실제 비용 문제가 생겼을 때만 도입한다.

FK와 필요한 UNIQUE를 명시하고 각 연결에서 FK enforcement를 설정한다. 조회에 필요한 인덱스는 실제 필터·정렬 패턴에 맞춰 추가한다. 범용 ORM 도입은 필수 조건이 아니다.

## 6. 규칙과 설명 가능성

직무는 최소 Backend, Frontend, Full-stack, Data Analyst, Data Engineer, ML/AI, DevOps/Cloud, Unknown을 지원한다. 기존 BI 값은 명시적 호환 정책을 둔다. 제목·본문 근거와 모호성을 반환한다. 단일 인프라 기술로 데이터 엔지니어를 확정하지 않는다.

backend taxonomy는 Java, Spring, Spring Boot, Spring MVC, Spring Security, JPA, Hibernate, QueryDSL, Gradle, Maven, MySQL, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS, Linux, REST API, JWT, Git, CI/CD를 포함한다. 기존 데이터·AI 기술은 유지한다. alias와 관계는 테스트로 검증하며 하위 기술 보유가 상위 기술 충족을 뜻하는지는 별도 공개 규칙이다.

매칭은 합격 확률이 아니다. 먼저 필수/우대별 일치·미보유·판단불가 목록과 career/location 등 제약을 보여준다. 숫자는 요건 근거가 충분할 때만 제공한다. 확인되지 않은 요건을 미충족으로 처리하지 않는다. 점수가 도입되면 공식·분모·각 항목 기여·제외 항목·정책 버전을 모두 결과에 포함한다. 정확한 weight는 Phase 0에서 임의로 정하지 않고 수동 검토 공고 fixture와 사용 목적을 바탕으로 해당 Phase에서 승인 가능한 형태로 확정한다.

학습 추천은 기존 빈도+기초 가산 결과를 legacy 동작으로 구별한다. 이후 사용자의 실제 목표 공고 gap과 비교 가능한 시장 수요를 함께 사용하되, 원래 빈도·공고 분모·관측 기간·기초 가산 같은 근거를 각각 노출한다. 성장 데이터가 없으면 현재 빈도만 있다고 표시한다.

## 7. UI와 운영 원칙

샘플/실제/혼합 출처와 목록만/상세 확보 상태를 명확히 표시한다. API 실패가 기존 로컬 공고 열람까지 막지 않게 한다. 수집 실패, 빈 결과, 상세 누락을 서로 다른 상태로 표시한다. API 키가 없는 경우에도 수동 등록과 프로필·지원 추적을 사용할 수 있어야 한다.

캐시는 UI에서 관리하되 DB identity/revision, 필터, rule version을 반영한다. 저장 성공 후 관련 결과만 무효화하는 방향으로 개선한다. 키·개인 프로필·본문을 로그에 무조건 남기지 않는다. local backup/export를 우선하고 클라우드 배포는 실제 필요가 있을 때 별도 검증한다.

## 8. 검증 기준과 미해결 사항

각 경계는 순수 unit test, 임시 SQLite integration, 합성 XML/HTTP mock, 소수 UI smoke test로 검증한다. 실제 API test는 명시적 opt-in으로 분리해 기본 테스트가 키·네트워크 없이 돌아가야 한다.

남은 결정: Work24 상세 계약·접근 권한, 본문 섹션 언어·형식, 실제 사용할 지원 단계, 프로필 숙련도 정의, 역할 중복 처리, 공고 갱신과 source ID 이관 정책, 점수 가중치, 관측 비교 기간. 이는 검증할 설계 질문이며 현재 동작에 대한 사실이 아니다. 규모가 커졌다는 증거 없이 프레임워크나 DB를 교체하지 않는다.
