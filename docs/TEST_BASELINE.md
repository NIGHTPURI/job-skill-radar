# Phase 1A — Regression Test Baseline

## Phase 7A 검증 (2026-09-17)

시작 64d7511, 로컬/원격 동일·clean, 395개 통과. 새 discovery 테스트17개로 총412개다.
역할/복수/중복/비어 있는 계획·보유 기술 독립성·예산·질의 partial/failed/empty·identity 중복·
발견 질의 provenance·상세 재사용/refresh/예산/실패 보존·source 격리·원자성·HTTP 경계의
연결 종료와 다른 writer lock 획득을 검증한다. 실 HTTP는 차단하고 temp DB만 사용한다.
전체 회귀·Work24 집중 테스트·요건 평가·샘플 CLI·diff check를 수행한다.
요건 평가60/60·144/144·13/13, required/preferred FP0 유지(합성 fixture 지표만 의미).
실 API smoke는 아직 수행하지 않았다.


## Phase 6A 검증 (2026-09-17)

Phase 5 367개에서 **395개 모두 통과**. 실패/오류/expected failure/skip 0.
새 테스트는 test_matcher 20, test_pipeline_comparison 6, test_comparison_ui 2다.
기존 requirement extractor/evaluation corpus와 운영 규칙은 수정하지 않았으며
60/60사례·144/144분류·13/13그룹, required/preferred false positive 0을 유지한다.

순수 비교 테스트는 필수/우대/업무 등록·미등록, unspecified/부정의 비승격, AND 전체/일부/미등록,
OR 첫째/둘째/둘 다/미등록, preferred OR, 그룹 구성원 비중복, 독립 근거 공존, 서로 다른 분류와
부정 근거 보존, 네 품질 상태, 미지원 기술/alias/비추론, 지역 충족/불일치/unknown와 선호 구분,
경력/학력/고용 형태 unknown, 목표 직무가 기술 판정을 바꾸지 않음, 결정성·입력 불변·반환 객체
독립성·score/fit/probability/전체 verdict 필드 부재·미검토 추출 버전 거절을 검사한다.

Application은 임시 SQLite로 수동·고용24 흐름, 프로필 revision 변경, 본문 변경, 재시작,
상세 실패 보존, 조회 연결 종료 후 비교, 비교 실패 시 DB 보존, 시장/schema 불변을 검사한다.
UI는 실제 app.py에서 수동 등록→프로필 저장→새 세션→OR 조건/우대/업무/미분류 비교→본문 수정
후 AND 재계산까지 수행한다. 그룹의 개별 구성원은 원문 검토/비교 화면에서 중복 필수로 표시하지
않는다. 프로필 없음·고용24 상세 없음도 성공 판정 없이 안내한다. exact evidence JSON을 제공한다.

전체 unittest·matcher/comparison 집중 suite·평가 CLI·sample CLI·diff --check와 headless smoke를
수행했다. 실 외부 네트워크/API 키는 불필요하다. headless 프로세스는 health 확인 후 종료한다.
schema v3·migration/프로필/수동 워크플로·Work24·skill/role/analyzer/recommender 회귀가 통과한다.

아침 실행:

```bash
cd ~/Dev/job-skill-radar
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

첫 실행에서 기존 v2 파일은 고유 pre-v3-from-v2 백업 후 자동 이전된다. 다른 writer와 이전
버전 앱을 먼저 종료한다. 사용자 실제 DB는 야간 테스트에 사용하지 않았다. 실공고 정확도,
복잡한 논리/부정·미지원 기술, 동시 편집 충돌 알림, 삭제/프로필 이력은 이번 검증 범위가 아니다.
Phase 6B는 미구현이며 다음 기능 개발 전에 실제 공고의 원문/추출/그룹 표현을 수동 검토한다.

## Phase 5 검증 (2026-09-17)

Phase 4A 345개에서 **367개 전부 통과**. 실패/오류/expected failure/skip 0.
신규 test_profile 11, test_profile_migrations 8, test_profile_ui 3이다.
기존 schema 검사 기대값만 v3/프로필 테이블/pre-v3 백업명으로 갱신했으며 이전 assertions는
삭제하지 않았다. 기존 migration 19개도 통과한다. 요건 평가 60/60·144/144·13/13, 필수/우대 FP 0.

프로필 최초/재조회/수정/revision, 순서·alias·중복의 동일 의미, unknown 기술 보존, 복수 역할,
빈 optional/빈 기술, 선호와 필수 구분, 검증 실패/SQL 실패 rollback, singleton 제약을 확인했다.
수동/고용24 공고와 시장 결과가 프로필 저장으로 바뀌지 않는다. UI는 저장·새 세션·수정·draft
보존·추천 기본값 및 임시 추천 입력이 프로필을 덮어쓰지 않음을 확인했다.

v2 fixture에 manual/work24의 같은 ID·원문·키워드·created_at/fetched_at을 저장하고 공고 세
테이블의 INSERT/UPDATE/DELETE를 막는 trigger를 설치해도 additive migration이 성공했다.
v0/v1/v2에서 마지막 프로필 DDL 후 실패를 주입해 원래 dump/version으로 rollback됨을 검증한다.
v2 백업의 정확한 dump/version/integrity·복사본 복원, 백업 실패 중단, 재시도 비덮어쓰기,
현재 재개방의 백업 부재, fresh v3, source별 FK cascade도 통과했다. 사용자 실제 DB는 건드리지 않았다.

전체 unittest·profile 집중 suite·평가 CLI·sample CLI·diff check와 bounded headless smoke를
실행했다. AppTest에서는 v2 DB를 실제 앱 시작으로 이전한 뒤 재시작해도 백업이 늘지 않음을
확인했다. 로컬 headless 서버는 health 확인 후 종료했다. API 키·실 Work24 네트워크는 불필요하다.

## Phase 4A 검증 (2026-09-17)

212ad8d의 328개에서 **345개 전부 통과**로 확장했다. 실패/오류/expected failure/skip은 0.
신규 manual workflow 14개, Streamlit AppTest 3개다. 기존 Phase 3C 60/60사례·144/144분류·
13/13그룹 및 required/preferred 오탐 0을 유지한다. sample CLI 12건·기존 추천·exit 0도 유지한다.

생성 최소/선택 필드, UUID/충돌/재시작, 원문 공백·CRLF, 입력 검증, 동일 identity/created_at 수정,
본문 수정 후 재추출, Work24 수정 차단, create/edit 실패 rollback, source 격리, source별 시장
범위, 품질 상태와 any_of, DB 연결 종료 후 추출을 검사한다. UI는 실제 app.py를 AppTest로
실행해 생성→목록 이동→새 세션→수정, 입력 실패 시 draft 보존, Work24 수정 UI 부재,
manual만 저장됐을 때 샘플 시장 표시를 확인했다. 테스트는 임시 DB와 차단된 HTTP를 쓴다.

전체 unittest, test_manual*.py, evaluate_requirements.py, run_demo.py, diff --check를 실행했다.
로컬 소켓은 샌드박스에서 차단되어 허용된 headless smoke 실행으로 127.0.0.1의 Streamlit health
응답을 확인하고 프로세스를 종료했다. AppTest가 실제 script/DB 초기화를 검증하며 단순 health
응답만으로 UI 동작을 검증했다고 주장하지 않는다. 실 Work24 네트워크는 사용하지 않았다.

이하 기록은 [Phase 3C 검증](#phase-3c-검증-2026-09-17)까지의 이전 기준선이다. 앞의 단계별 수치와 결함 설명은 당시 기록이다.

기준일: 2026-09-16. 운영 코드 기준: `0ee3c40` (`Initial Job Skill Radar MVP`).
환경: Windows PowerShell, Python 3.14.5, 표준 라이브러리 unittest/SQLite/mock 사용.
Phase 0 문서 3개와 실제 구현을 다시 읽고 작업했다. 운영 코드·스키마·taxonomy·의존성은 수정하지 않았다. Phase 1B/2 작업은 시작하지 않았다.

## 실행 방법과 결과

프로젝트 루트에서 새 Python 프로세스로 실행한다. 설치·API 키·실제 DB는 필요 없다.

```powershell
$env:PYTHONIOENCODING='utf-8'
python -B -m unittest discover -s tests -v
python -B scripts/run_demo.py
```

`PYTHONIOENCODING`은 PowerShell에서 한국어 출력이 깨지는 것을 방지한다. `-B`는 bytecode 생성을 막는다. 기존 저장소 관례에 맞춰 각 테스트가 `src` 경로를 등록한다. `unittest discover`에 `-s tests`를 명시해야 한다.

| 항목 | 변경 전 | 변경 후 |
|---|---:|---:|
| 전체 test method 수 | 4 | 95 |
| 정상 통과 | 4 | 90 |
| 일반 실패 | 0 | 0 |
| 오류 / 예상하지 못한 실패 | 0 | 0 |
| skipped | 0 | 0 |
| expected failures | 0 | 5 |
| unexpected successes | 0 | 0 |

subTest의 입력 조합 수는 전체 테스트 수에 별도로 더하지 않았다. 최종 정방향 전체 실행은 0.233초, 역순 실행은 0.199초였으며 시간은 환경에 따라 달라진다. 역순에서도 같은 90/5 결과로 설정·mock의 순서 의존성을 점검했다. expected failure 5개는 모두 의도한 비교의 AssertionError임을 확인했다(설정·import·fixture 오류가 아님).

데모는 변경 전후 exit 0, 12건이다. 직무 분포는 데이터 분석가 6 / ML 3 / 데이터 엔지니어 2 / BI 1, SQL 보유 데이터 분석가 추천은 Python 9, Statistics 4, Tableau 3, Pandas 3, A/B Test 2로 동일하다. 샘플 전체 기술 Counter와 추천 순서는 pipeline 테스트에 명시했다.

## 테스트 구성과 범위

기존 `test_core.py` 3개와 기존 storage test 1개를 유지했다. 신규 파일 7개, 기존 파일 확장 1개, 합성 XML fixture 1개를 추가했다.

| 파일 | 수 | 범위 |
|---|---:|---|
| `tests/test_core.py` | 3 | 기존 추출·canonicalization·추천 smoke 유지 |
| `tests/test_skill_extractor.py` | 16 | 현재 31개 canonical·대소문자·영문/한글 alias, 중복, 빈/None, 문장부호·부분 단어, 출력 순서, 보유 기술 정규화 |
| `tests/test_analyzer.py` | 15 | 현재 4개 역할, 제목·본문·기술 규칙과 우선순위·fallback·오분류; enrichment와 모든 Counter, 빈/단일/복수 입력, 결측·비변경성 |
| `tests/test_recommender.py` | 10 | 정확한 점수, 모든 역할의 +5…+1 foundation, global fallback, 보유 alias 제외, limit, 동점 순서, 빈 입력 |
| `tests/test_storage.py` | 13 | schema/PK, 전체 필드 round-trip, count, NULL, 기술 추출·반복 저장·정렬, 파일 재연결, 중복 불일치·source 충돌·orphan 기술 |
| `tests/test_work24_client.py` | 16 | XML 전체 필드·결측·학력·본문 구성·오류, URL·인코딩·인증·timeout·페이지·display, HTTP/timeout 전파와 재시도 부재 |
| `tests/test_pipeline.py` | 9 | 샘플 기준선, 빈 DB, 반복 seed, 수집 정제·중복 제거, 기본 키워드, 저장 없는 분석, 부분 실패, 저장 기술 재추출, 연결 종료 |
| `tests/test_normalizer.py` | 8 | 필드·문자열 정리, 빈 ID, 중복·source 충돌, 지역·경력 규칙, 날짜/급여 비정규화 |
| `tests/test_config.py` | 5 | 환경 우선순위, 간단한 env 파싱, 상대/절대/기본 DB 경로, 1회 로딩 |

`tests/fixtures/work24/list.xml`은 합성 공고 2건의 작은 목록 fixture다. 실제 응답·개인 정보·인증키를 복사하지 않았다. 본문 무시 테스트의 추가 `<description>` 태그도 합성 입력이며 실제 Work24 상세 API 필드라는 주장이 아니다.

순수 함수는 unit test, 저장·pipeline은 임시 SQLite integration test, Work24는 parser unit test와 mocked transport test다. 실제 HTTP endpoint·요청 인수는 검사하지만 네트워크는 호출하지 않는다. pipeline은 임시 경로·가짜 collector와 추가 HTTP 차단 mock을 사용한다. 설정 테스트는 환경변수·전역 로딩 상태·프로젝트 루트를 격리하고 복원한다. DB는 메모리 또는 TemporaryDirectory 안에서만 생성하며 기본 `data/job_skill_radar.sqlite`가 생성되지 않았음을 확인했다.

## 테스트 분류 원칙

- 일반 회귀 테스트: 현재 지원하는 계약과 결과를 확인한다.
- `test_current_*`/KD 주석이 붙은 특성 테스트: 현재 잘못되거나 제한적인 동작을 **통과하는 재현 테스트**로 기록한다. 통과가 제품 동작의 올바름을 뜻하지 않는다.
- `@unittest.expectedFailure`: 확인된 결함 중 올바른 기대값이 명확한 5개만 사용한다. 실행을 건너뛰는 skip이 아니다. 수정 후 unexpected success가 나면 decorator를 제거하고 관련 현행 재현 테스트를 새 계약으로 바꿔야 한다.
- 미지원 새 역할·기술·프로필 같은 미래 기능은 expected failure로 만들지 않았다. taxonomy는 확장하지 않았다.

## 결함 목록과 향후 수정

| ID | 재현 결과·영향 | 테스트 분류 | 향후 작업 |
|---|---|---|---|
| KD-01 | `Python.`에서 Python 누락. 문장 끝 요구 기술을 놓침 | expected failure + 현행 경계 테스트 | Phase 3: 마침표/버전 등 경계 정책 수정 |
| KD-02 | `R&D department`에서 R 오탐. 연구 부서를 언어 역량으로 계산 | expected failure | Phase 3: R 단일 문자·문맥 규칙 보완 |
| KD-03 | `통계청`에서 Statistics 오탐 | 통과하는 결함 재현 | Phase 3: 한글 경계·조사 허용을 함께 검토 |
| KD-04 | mobile developer→BI, retail assistant→ML, 백엔드 엔지니어→데이터 엔지니어 | 통과하는 결함 재현 | Phase 3: 제목 경계·우선순위·Unknown 정책. 지금 새 역할 기대값을 강제하지 않음 |
| KD-05 | limit=0 또는 -1이어도 추천 1개 | 0은 expected failure, 두 값의 현재 결과는 재현 테스트 | Phase 3 추천 계약 정리에서 0건 처리·음수 정책 명시. 점수 재설계와 분리 |
| KD-06 | 같은 ID 재저장 시 이전 본문과 신규/이전 기술의 합집합이 공존 | expected failure + 상세 재현 | Phase 2: 공고·기술을 동일한 버전 기준으로 atomic 갱신 |
| KD-07 | 다른 source의 같은 posting_id가 한 공고로 축소 | normalizer/storage 결함 재현 | Phase 2: source를 포함한 identity 및 migration |
| KD-08 | `경력무관`→경력. 제약이 없는 공고를 경력 제한으로 표시 | expected failure + 현재 경력 규칙 테스트 | Phase 4C: 부정/무관·혼합 조건을 보존하는 해석 |
| KD-09 | 합성 오류 XML→빈 목록. 실패와 정상 0건 구분 불가 | 통과하는 결함 재현 | Phase 4B: 실제 오류 계약 확인 후 응답 오류 분류 |
| KD-10 | storage 직접 호출에서 source 누락 시 공고 삽입은 무시되지만 기술 행이 저장됨 | 통과하는 결함 재현; 이번 Phase에 새로 확인 | Phase 2: 입력 검증·공고 저장 성공과 기술 저장의 일관성·FK/transaction 정책 |

KD-10은 일반 pipeline이 clean_posting을 통해 source를 빈 문자열로 채우는 경로와 구분해야 한다. 직접 storage 호출에서 확인한 결함이며 모든 수집에서 orphan이 발생한다는 뜻이 아니다.

expected failure의 정확한 test method:

```text
test_skill_extractor.SkillExtractionTest.test_kd01_sentence_final_period_should_allow_python
test_skill_extractor.SkillExtractionTest.test_kd02_research_abbreviation_should_not_imply_r_language
test_recommender.RecommendationTest.test_kd05_zero_limit_should_return_no_recommendations
test_storage.StorageRegressionTest.test_kd06_persisted_skills_should_agree_with_persisted_content
test_normalizer.NormalizerTest.test_kd08_no_experience_requirement_should_be_unrestricted
```

기타 현행 제한도 테스트에 드러난다: namespace XML 미지원, 전체 페이지 순회, timeout 재시도 없음, 나중 키워드 실패 시 모아 둔 신규 배치 미저장, global 빈도 fallback에도 목표 직무 문구 사용, config 1회 로딩. 이들은 별도 미구현 정책/제약으로 기록하며 모두 expected failure로 부풀리지 않았다.

## SQLite 핵심 재현

1. source=test, posting_id=1, title=`Python developer`, description=`SQL` 저장 → 신규 1.
2. 같은 ID, title=`Java developer`, description=`Kafka` 저장 → 신규 0.
3. 공고 수는 1이고 저장 본문은 여전히 `Python developer` / `SQL`.
4. posting_skills는 Java, Kafka, Python, SQL 4개.
5. 저장 본문에서 재추출하면 Python, SQL 2개뿐이다. 이 불일치를 재현 테스트가 명시하고, 두 집합의 일치를 요구하는 별도 테스트는 예상 실패한다.

갱신 정책을 지금 정하거나 운영 코드를 고치지 않았다. 일관성 invariant는 최초 값 유지/최신 값 갱신 중 어느 정책을 선택하더라도 필요하다.

## Work24 description 검증

완전한 목록 fixture의 description은 `Python 분석 담당 정보서비스업 경력`으로, title + indTpNm + career를 공백으로 합친 값이다. industry/career가 비어 있으면 제목만 남는다. 합성 `<description>Required SQL; preferred Docker</description>`는 무시되고 `Developer Software Experienced`만 생성되는 것을 검증했다. 현재 본문·필수·우대 정보를 얻는다고 해석할 수 없다.

## 검증하지 않은 영역

- 실제 Work24 권한·응답 schema·상세 API·네트워크 통합, 실제 코퍼스 정확도.
- Streamlit UI/캐시/상호작용: Phase 0에서 UI 의존성이 없었으며 이번에도 설치·실행하지 않았다.
- 지원 Python 버전 전체 및 다른 OS: 실행 검증은 Python 3.14.5/Windows만 수행. 새 테스트는 Python 3.11 전용 TestCase.enterContext 대신 기존 Python 3.10에서도 제공되는 ExitStack을 사용한다.
- SQLite 잠금/동시성·디스크 오류·저장 중 강제 실패 rollback·용량 성능·백업/복원. 스키마 migration은 아직 없다.
- 각 public 함수의 모든 잘못된 타입 입력과 보안 fuzzing; 커버리지 백분율은 측정하지 않았다.

UI 검증이 가능한 환경에서는 별도 임시 `JOB_RADAR_DB_PATH`를 지정하고 `streamlit run app.py`로 샘플/빈 DB fallback/샘플 저장을 확인해야 한다. 그 절차를 이번 자동 테스트의 성공으로 주장하지 않는다.

## 변경 범위와 다음 경계

`git diff --check`와 신규 파일 공백 검사를 수행한다. production 추적 파일은 HEAD와 동일함을 확인한다. 기존 Phase 0 문서 3개는 이번 작업 시작 전부터 untracked 상태였고 수정하지 않았다. 이번 문서 변경은 이 파일 하나다.

다음 Phase 1B는 현재 동작을 유지하며 JobPosting/AnalysisResult 계약, application 소스 선택, 명시적 DB/collector 경계와 수집 루프 중복을 정리하는 단계다. 이 문서의 결함 수정은 표의 후속 Phase에서 별도 변경으로 진행한다. 사용자 요청 전에는 Phase 1B를 시작하지 않는다.

## Phase 1B 검증 추가 (2026-09-16)

위 기록은 Phase 1A 당시 기준선이다. Phase 1B 시작 전 동일 명령으로 95개(90 통과·5 예상 실패)와 샘플 CLI 12건을 다시 확인한 뒤 운영 코드를 변경했다.

Phase 1B 결과는 **112개: 107 통과, expected failures 5, 일반 실패 0, errors 0, skipped 0, unexpected successes 0**이다. 기존 95개를 삭제하지 않았다. 연결 소유권이 storage로 옮겨져 `test_pipeline.py`의 연결 종료 테스트에서 patch 대상 두 곳만 storage로 변경했고 assertion은 유지했다.

추가 파일:

- `test_models.py` 4개: 필드 순서, dict 호환, 결측/None, 생성 필드 분리, 기존 추가 필드 처리.
- `test_storage_boundary.py` 3개: 경로 기반 저장/조회, NULL·중복 불일치·orphan 보존, 성공/실패 연결 종료.
- `test_application_boundary.py` 10개: 샘플/DB/빈 DB/오류 정책, config 없는 명시적 경로, 주입 collector, 정제·출처 충돌 보존, 수집 실패 후 무저장, 직접/DB 분석 비교, KD-11 재현.

의미 있는 변경마다 관련 model/normalizer/Work24/analyzer, storage/pipeline, application/recommender 테스트를 순서대로 실행했다. 최종 `python -B -m unittest discover -s tests -v`와 `python -B scripts/run_demo.py`도 성공했다. 샘플 분포와 추천 점수/순서는 Phase 1A와 같다.

기존 expected failure KD-01/02/05/06/08은 모두 그대로다. KD-08은 직무 분류기가 아니라 **경력 정제의 `경력무관`→`경력` 문제**다. 오류 XML과 malformed XML도 기존 특성 테스트로 보호한다(오류 XML은 빈 목록, malformed XML은 ParseError).

### 새로 확인한 기존 결함 KD-11

경력 없는 공고를 수집·정제하면 career=`미상`이지만, DB에서 로드하면서 다시 정제하면 `기타`가 된다. 처음 추가한 “직접 분석과 DB 분석 전체 동등” 테스트가 이 문제로 실패했다. 기준 HEAD의 기존 normalizer에서도 `normalize_career(normalize_career(''))`가 같은 결과임을 별도 실행해 확인했다.

운영 코드는 고치지 않았다. 동등성 테스트는 명시적 경력을 가진 공고로 비교하고, 결측 경력 사례는 `test_current_missing_career_changes_after_storage_round_trip`으로 분리해 차이를 정확히 기록했다. 이는 동등성 assertion을 없애거나 expected failure로 숨긴 것이 아니다. Phase 1C에서 정제의 반복 적용 일관성·기존 데이터 처리 정책을 검토할 후보이다.

### 변경 보존·smoke 검증

- 기준 HEAD와 AST 비교: recommender/skill_extractor 전체, storage.ensure_schema/save_postings 및 analyzer의 분류/enrichment/집계 함수 본문 동일.
- core 모듈 import 성공, app.py와 CLI 3개 문법 검사 성공.
- Streamlit/pandas/plotly가 없어 실제 app import·화면 실행은 미검증. 패키지 설치·실 API 호출은 하지 않았다.
- 새 테스트도 임시 파일 DB 또는 메모리 DB와 mock만 사용한다. 기본 DB에 접근하지 않는다.
- 모델은 TypedDict이며 런타임 검증·결측 보충을 추가하지 않는다. 전면 정적 타입 검사는 수행하지 않았다.

Phase 1B 완료 뒤 Phase 1C 및 Phase 2는 시작하지 않았다.

## Phase 1C 재개 검증 (2026-09-16)

시작 브랜치는 `refactor/v2`, HEAD는 `985d7e0` (`wip: implement phase 1c persistence integrity`)이며 작업 트리는 깨끗했다. Git 이력에는 Phase 1A/1B/1C가 별도 커밋으로 나뉘어 있지 않으므로, 기존 문서와 실제 코드·테스트를 대조했다. 요청된 17개 요구사항은 이미 구현되어 있었고 이번 재개 세션에서는 운영 코드와 테스트를 변경하지 않았다. 로드맵의 미시작 표시와 이 검증 기록만 보완했다.

### 실행 결과

프로젝트 루트에서 다음 명령을 초기 검증과 최종 검증에 각각 실행했다. 두 실행의 결과는 같다. 각 명령의 종료 코드는 0이다.

| 명령 | 결과 |
|---|---|
| `python -B -m unittest discover -s tests -v` | 140개: 136 통과, expected failures 4, failures 0, errors 0, skipped 0, unexpected successes 0 |
| `python -B -m unittest discover -s tests -p test_migrations.py -v` | 13개 모두 통과 |
| `python -B -m unittest discover -s tests -p test_persistence_integrity.py -v` | 15개 모두 통과 |
| `python -X utf8 -B scripts/run_demo.py` | 12건 분석, 정상 종료 |
| `git diff --check` | 출력 없음, 공백 오류 없음 |

초기 실행 시간은 전체 0.410초, migration 0.087초, integrity 0.017초였다. 시간은 환경과 실행마다 달라진다. CLI는 출력 인코딩을 명시했다. 샘플 직무 분포는 데이터 분석가 6 / ML 엔지니어 3 / 데이터 엔지니어 2 / BI 분석가 1, 추천은 Python 9, Statistics 4, Tableau 3, Pandas 3, A/B Test 2로 기존과 같다.

### 요구사항별 확인 근거

| 요구사항 | 구현 및 회귀 검증 |
|---|---|
| 1–2. 복합 DB identity·source 충돌 방지 | 두 테이블의 복합 PK 검사, 서로 다른 source의 동일 external ID 저장·개별 기술 갱신 테스트 |
| 3–4. 오래된 기술 교체·원자적 저장 | 전체 표현 upsert와 기술 집합 교체, 빈 기술 집합, child INSERT 강제 실패 시 신규·기존 공고와 기술 전체 rollback |
| 5. 잘못된 identity의 부분 저장 방지 | 전체 배치 사전 검증, 누락/None/공백/비문자열 거절, DB NOT NULL/CHECK |
| 6–7. FK 활성화·orphan 방지 | application connection 및 schema 진입 시 FK ON 확인, 잘못된 부모/source 거절, source별 CASCADE |
| 8–10. v0→v1 이전·초기화 방지·사전 백업 | legacy fixture의 모든 공고 필드 보존, 알 수 없는 version/layout/custom object 거절, 파일 백업의 원본 dump 및 v0 확인, 백업 실패 시 이전 중단 |
| 11. migration 실패 rollback | copy/rename 후 주입한 실패에서 schema/data/user_version 원복 확인 |
| 12–13. 멱등성·재연결 | 반복 ensure_schema에서 dump 불변, 파일 재연결·갱신, 추가 백업 없음, 백업 복사본 재이전 |
| 14. 기존 orphan 처리 | 부모 없는 기술은 새 테이블에서 제외하고 건수 기록. 본문 불일치 기술 제거·누락 기술 복원, 원본은 파일 백업에 보존 |
| 15. created_at 보존 | 최초 저장 시각의 기존 형식 유지, 갱신과 migration에서 원래 값 보존 |
| 16. 결측 경력 멱등성 | `미상` 반복 정제와 DB 왕복 유지, application 직접/DB 경력 집계 일치 |
| 17. 무관한 동작 보존 | 기존 taxonomy/recommender는 최초 커밋과 동일. analyzer 변경은 모델 import와 타입 표기뿐이며 분류·집계 회귀 테스트 및 샘플 기준선 유지 |

저장 배치는 SAVEPOINT로 묶으며 caller transaction이 있으면 최종 commit/rollback 권한을 유지한다. migration은 저장 배치보다 먼저 별도 transaction으로 완료한다. 세부 정책은 [데이터 설계](02_data_design.md#phase-1c-현재-영속-계약)를 따른다.

### 결함 상태와 검증 한계

KD-06(본문/기술 불일치), KD-07(source 충돌), KD-10(orphan), KD-11(결측 경력 재정제)은 해결되었다. KD-06 테스트는 일반 통과 테스트로 전환되어 예상 실패가 5개에서 4개로 줄었다.

남은 expected failure는 KD-01(`Python.` 누락), KD-02(`R&D`의 R 오탐), KD-05(limit=0 추천 반환), KD-08(`경력무관` 오분류)이다. KD-03(한글 부분 문자열 오탐), KD-04(직무 부분 문자열 오분류), KD-09(오류 XML과 빈 결과 혼동)도 기존 결함 재현 테스트로 남는다. Phase 1C 범위 밖이므로 수정하지 않았다.

이번 검증은 메모리/임시 SQLite와 mock 기반이다. 실제 사용자 DB 이전, Streamlit UI, 실 Work24 API, 동시 writer·디스크 장애·강제 프로세스 종료 복구는 검증하지 않았다. 최초 legacy 이전은 다른 writer를 중지하고 백업 경로 권한·공간을 확인해야 한다. 이미 손실된 다른 source 공고나 `기타`로 바뀐 결측 경력의 원래 값은 추정 복원하지 않는다. Phase 2는 시작하지 않았다.

## Phase 2A 검증 (2026-09-16)

시작 HEAD는 `a8086a6` (`docs: finalize phase 1c validation`), 브랜치는 `refactor/v2`, 작업 트리는 깨끗했다. 문서 5개와 extractor/analyzer/normalizer, storage/migrations/recommender 및 UI/CLI 소비 경로를 확인한 뒤 기준선을 실행했다.

| 검증 | 기준선 | 최종 |
|---|---|---|
| 전체 unittest | 140개, 136 통과, 예상 실패 4, 0.702초 | 171개, 169 통과, 예상 실패 2 |
| skill extractor 파일 | 16개, 14 통과, 예상 실패 2, 0.005초 | 42개 모두 통과 |
| canonicalization 단독 | 위 파일에 포함 | 9개 모두 통과 |
| extraction 소비 경로 통합 | 기존 경계 테스트 | 신규 5개 모두 통과 |
| migration | 기존 전체에 포함 | 13개 모두 통과 |
| persistence integrity | 기존 전체에 포함 | 15개 모두 통과 |
| sample CLI | 12건, exit 0 | 출력 동일, exit 0 |
| git diff --check | 출력 없음, exit 0 | 출력 없음, exit 0 |

전체 실행의 failures/errors/skipped/unexpected successes는 기준선·최종 모두 0이다. subTest 조합은 별도 테스트 수에 더하지 않았다. 검증 명령은 다음과 같다.

```powershell
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_skill_extractor.py -v
python -B -m unittest discover -s tests -p test_skill_extractor.py -k CanonicalizationTest -v
python -B -m unittest discover -s tests -p test_skill_integration.py -v
python -B -m unittest discover -s tests -p test_migrations.py -v
python -B -m unittest discover -s tests -p test_persistence_integrity.py -v
python -X utf8 -B scripts/run_demo.py
git diff --check
```

`test_skill_extractor.py`에 26개 테스트를 추가했다. 독립적인 필수 backend 39개 목록, 기존 Data/AI 31개, 영문·한글 alias, 구두점·줄바꿈, Unicode/식별자 경계, 짧은 약어·수량, 한글 조사·부분 문자열, 가장 긴 근거 우선, 필드 간 가짜 복합어 방지, 순서·중복·미등록 입력 및 taxonomy alias 소유권을 검사한다. KD-01(`Python.`)과 KD-02(`R&D`)는 삭제하지 않고 expectedFailure를 제거했다. KD-03(`통계청`)도 기존 오탐 재현의 기대값을 수정한 일반 회귀 테스트다. JavaScript는 새 지원 기술이므로 기존 Java 부분 문자열 보호 테스트에서 JavaScript만 반환하도록 갱신했다.

`test_skill_integration.py`의 5개 테스트는 새 기술의 source별 저장·정확한 교체·강제 실패 rollback, 기존 v1 읽기의 무변경·재저장 갱신, 기존 v0 이전 경로의 새 추출 결과·created_at/FK/version 보존, 보유 backend alias의 추천 제외를 확인한다. 운영 storage/migrations/analyzer/normalizer/recommender와 기존 persistence 테스트는 수정하지 않았다.

샘플의 전체 기술 Counter와 직무 분포를 고정한 기존 테스트가 수정 없이 통과한다. CLI도 기준선과 동일하다: 12건, 데이터 분석가 6 / ML 엔지니어 3 / 데이터 엔지니어 2 / BI 분석가 1. 추천은 Python 9, Statistics 4, Tableau 3, Pandas 3, A/B Test 2다.

남은 expected failure는 KD-05(비양수 추천 limit), KD-08(`경력무관`) 2개다. KD-04(직무 부분 문자열·기본 분류)와 KD-09(오류 XML)도 범위 밖이다. classifier 테스트 실패나 기대값 변경은 없었다. 별도 probe에서 `Spring Boot Redis` backend 공고의 데이터 분석가 fallback, `Docker.` 추출 복원 시 기존 데이터 엔지니어 규칙 활성화, mobile→BI/retail→ML을 확인했다. Phase 2B에서 검토하며 이번에 고치지 않았다.

실제 공고 코퍼스 정밀도·재현율, UI, 실 API는 검증하지 않았다. 한글 조사·동음이의어·짧은 토큰의 잔여 모호성과 기존 v1 기술 행의 자동 재추출 부재는 [추출 계약](02_data_design.md#phase-2a-기술-taxonomy와-추출-계약)에 명시했다. Phase 2A 범위에서 종료한다.

## Phase 2B 검증 (2026-09-16)

시작 HEAD는 `fd78887` (`feat: expand skill taxonomy and improve extraction`)이며 작업 트리는 깨끗했다. 문서 5개와 현재 분류·추출·정제·모델·샘플 및 역할 label 소비 테스트/UI/추천 경로를 읽고, 수정 전 분류 순서를 [아키텍처 감사](TARGET_ARCHITECTURE.md#phase-2b-실제-구현과-변경-전-분류-감사)로 기록했다.

| 검증 | 기준선 | 최종 |
|---|---|---|
| 전체 unittest | 171개: 169 통과, expected failures 2 (0.914초) | 210개: 208 통과, expected failures 2 |
| analyzer | 15개 모두 통과 (0.003초) | 17개 모두 통과 |
| role classifier | 기존 analyzer에 포함 | 신규 34개 모두 통과 |
| skill extraction/canonicalization | 기존 전체에 포함 | 42개 모두 통과, 그중 canonicalization 9개 |
| migration | 기존 전체에 포함 | 13개 모두 통과 |
| persistence integrity | 기존 전체에 포함 | 15개 모두 통과 |
| sample CLI | 12건, exit 0 | 동일 출력, exit 0 |
| git diff --check | 출력 없음, exit 0 | 공백 오류 없음, exit 0 |

기준선·최종 모두 failures/errors/skipped/unexpected successes는 0이다. 주요 검증 명령:

```powershell
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_role_classifier.py -v
python -B -m unittest discover -s tests -p test_analyzer.py -v
python -B -m unittest discover -s tests -p test_skill_extractor.py -v
python -B -m unittest discover -s tests -p test_skill_extractor.py -k CanonicalizationTest -v
python -B -m unittest discover -s tests -p test_migrations.py -v
python -B -m unittest discover -s tests -p test_persistence_integrity.py -v
python -X utf8 -B scripts/run_demo.py
git diff --check
```

새로 추가한 테스트는 총 39개다: classifier 34, analyzer 집계·결측 2, recommender 새 역할 호환 2, application DB 왕복 1. 각 역할의 여러 영문/한글 공고, 강한 제목 우선, 기술 조합·단일 약한 기술, 경계·부분 문자열, 구체적 복합 제목, 같은 단계 충돌, 명시적 Full-stack, 순서·중복 독립성, career 비참조를 검증한다. sample fixture와 기술 추출 테스트는 변경하지 않았다.

기존 classifier 재현 테스트는 새 계약으로 갱신했다. KD-04의 mobile/retail은 미분류, 백엔드는 Backend로 변경했다. 단일 기술로 역할을 결정하던 검증은 조합 검증으로 바꾸고 별도 단일 기술 부정 테스트를 추가했다. `SQL specialist`는 근거 부족으로 미분류가 된다. 플랫폼 엔지니어는 PyTorch 하나 때문에 ML로 바뀌지 않는다. 기존 테스트를 expectedFailure로 숨기지 않았다.

남은 expectedFailure는 추천 limit KD-05와 경력 정제 KD-08이다. KD-08은 `normalize_career('경력무관')` 직접 호출로 재현되고 classifier가 호출되지 않으므로 이번 범위 밖이다. normalizer와 두 decorator를 유지했다. KD-09 오류 XML 문제도 수정하지 않았다.

샘플 CLI는 데이터 분석가 6 / ML 3 / 데이터 엔지니어 2 / BI 1이며, 전체 기술 Counter와 추천 Python 9, Statistics 4, Tableau 3, Pandas 3, A/B Test 2가 기존과 같다. 새 역할에는 foundation을 추가하지 않았고 역할 빈도·global fallback·빈 데이터 호환 테스트가 통과한다.

app.py는 기존 공유 ROLE_LABELS를 사용한다. 문법 검사와 코드 연결을 확인했지만 Streamlit/Plotly가 없어 실제 UI 실행은 하지 않았다. 실 API·실제 공고 코퍼스 정확도도 미검증이다. 새 규칙의 부정·인용·혼합 제목 한계 및 추천 fallback의 제품상 한계는 데이터 설계에 기록했다. Phase 2C는 시작하지 않았다.

## Phase 2C 검증 (2026-09-16)

시작 HEAD는 `25f2ba3`이며 작업 트리는 깨끗했다. 요청된 문서 5개와 추천·분석·분류·taxonomy·모델·pipeline·UI·샘플 및 추천 소비 테스트를 확인했다. 운영 코드 수정 전 기준선에 일반 실패가 없음을 확인하고, [변경 전 추천 감사](TARGET_ARCHITECTURE.md#phase-2c-변경-전-추천-감사-2026-09-16)를 먼저 기록했다.

| 검증 | 변경 전 정확한 기준선 | 최종 결과 |
|---|---|---|
| 전체 unittest | 210개: 208 통과, 예상 실패 2 (0.565초) | 222개: 221 통과, 예상 실패 1 (0.587초) |
| recommender | 12개: 11 통과, 예상 실패 1 (0.002초) | 24개 모두 통과 (0.029초) |
| analyzer | 17개 모두 통과 (0.011초) | 17개 모두 통과 (0.018초) |
| role classifier | 전체 기준선 포함 | 34개 모두 통과 (0.049초) |
| extraction/canonicalization | 전체 기준선 포함 | 42개 모두 통과 (0.088초) |
| migration | 전체 기준선 포함 | 13개 모두 통과 (0.084초) |
| persistence integrity | 전체 기준선 포함 | 15개 모두 통과 (0.036초) |
| skill integration | 전체 기준선 포함 | 5개 모두 통과 (0.012초) |
| sample CLI | 12건, exit 0 | 12건, 추천 출력만 의도적 변경, exit 0 |
| git diff --check | 출력 없음, exit 0 | 출력 없음, exit 0 |

기준선·최종의 failures/errors/skipped/unexpected successes는 모두 0이다.
subTest 조합은 테스트 수에 별도로 더하지 않았다. 시간은 실행 환경에 따라 달라진다.
실행 명령(각각 종료 코드 0):

```powershell
python -B -m unittest discover -s tests
python -B -m unittest discover -s tests -p test_recommender.py
python -B -m unittest discover -s tests -p test_analyzer.py
python -B -m unittest discover -s tests -p test_role_classifier.py
python -B -m unittest discover -s tests -p test_skill_extractor.py
python -B -m unittest discover -s tests -p test_migrations.py
python -B -m unittest discover -s tests -p test_persistence_integrity.py
python -B -m unittest discover -s tests -p test_skill_integration.py
python -X utf8 -B scripts/run_demo.py
git diff --check
```

### 추천 회귀와 의도적인 계약 변경

recommender 테스트는 12개에서 24개로 확대했다. 기존 가산점·global fallback·입력 순서
의존 기대값은 새 계약으로 갱신했으며, KD-05의 기존 zero limit 테스트는 삭제하지 않고
expectedFailure만 제거했다. 음수/0/1/일반 양수/후보 수 초과, 8개 구체적 역할 각각의
시장 근거 분리, 미분류·미지원 역할, 작은 기초 목록, 데이터 없는 역할, 기술 없는 역할 공고,
보유 alias·중복·전부 보유, 빈도 우선·기초 동점·이름 동점·역순 공고·반복 호출,
설명 근거, 역할 분모·0·분모 미제공, 명시적 반환 키, 입력 불변성과 career 비의존을 검증한다.

pipeline 샘플 테스트는 집계 기대값을 유지하고 추천 순위·실제 건수·분모만 새 계약으로
검증한다. sample 직접 분석과 DB 왕복 분석의 추천도 같음을 확인했다. skill integration의
기존 alias 테스트는 analyzer가 생산한 backend 집계에서 한국어 별칭을 제외하도록 바꿨다.
analyzer·role classifier·extractor·migration·persistence 테스트 파일 자체는 수정하지 않았다.

### 샘플 CLI 전후

샘플은 그대로 12건이다. 데이터 분석가 6 / ML 3 / 데이터 엔지니어 2 / BI 1과 전체 기술
Counter가 유지된다. SQL 보유 데이터 분석가의 이전 출력은 Python 9, Statistics 4,
Tableau 3, Pandas 3, A/B Test 2(가산점 포함)였다. 이제 다음 순서로 출력한다.

| 순위 | 기술 | 데이터 분석가 공고에서 언급 | 기초 후보 |
|---|---|---|---|
| 1 | Python | 6건 중 5건 | 예 |
| 2 | A/B Test | 6건 중 2건 | 아니오 |
| 3 | Tableau | 6건 중 2건 | 아니오 |
| 4 | Statistics | 6건 중 1건 | 예 |
| 5 | GA4 | 6건 중 1건 | 아니오 |

Tableau/Pandas 고정 기초 가산을 제거했으므로 결과가 달라지는 것이 의도한 동작이다.
같은 관측 빈도의 A/B Test와 Tableau, GA4와 나머지 비기초 후보는 이름으로 순서를 정한다.
점수·백분율을 출력하지 않으며 현재 분석한 역할 공고의 언급 건수라고 설명한다.

### 남은 결함과 검증 한계

예상 실패는 2→1이다. KD-05 비양수 limit은 해결됐고, KD-08 경력무관은 추천이 career를
사용하지 않으므로 수정하지 않았다. KD-09 오류 XML도 기존 수집 영역의 문제로 남는다.
새 일반 실패나 저장·추출·분류 결함은 발견하지 않았다. 데이터가 부족한 역할을 global 빈도로
대체하던 오해와 미분류를 목표 직무처럼 추천하던 동작은 이번에 명시적으로 제거했다.

app/recommender/models/demo는 AST 문법 검사를 통과했다. Streamlit과 Plotly가 설치되어
있지 않아 실제 UI·브라우저 상호작용은 미검증이다(pandas는 설치됨). UI의 기존 배치는 유지하고
순위·추천 의미·미분류·데이터 부재·모두 보유 안내만 추가했다. 실 API·실제 공고 코퍼스 정확도는
검증하지 않았다. 의존성 설치·외부 호출·실제 사용자 DB 수정은 하지 않았다.
추천 결과는 analyzer의 일관된 집계를 전제로 하며 외부 임의 집계의 런타임 유효성 검증은 없다.
Phase 2C에서 종료하며 Phase 3와 공고별 매칭은 시작하지 않았다.

## Phase 2D 검증 (2026-09-16)

시작 작업 트리는 깨끗했다. 지정 문서 3개와 normalizer/models, 경력 관련 테스트,
application 경계, Work24 XML·inline fixture를 확인한 뒤 기준선을 실행했다.
expectedFailure는 KD-08 테스트 하나뿐이었다.

| 검증 | 기준선 | 최종 |
|---|---|---|
| 전체 unittest | 222개: 221 통과·예상 실패 1 (0.573초) | 226개 모두 통과 (0.610초) |
| normalizer | 8개: 7 통과·예상 실패 1 (0.001초) | 11개 모두 통과 |
| application boundary | 전체 기준선 포함 | 12개 모두 통과 |
| analyzer / classifier / recommender | 전체 기준선 포함 | 각각 17 / 34 / 24개 모두 통과 |
| skill extraction | 전체 기준선 포함 | 42개 모두 통과 |
| migration / persistence integrity | 전체 기준선 포함 | 각각 13 / 15개 모두 통과 |
| sample CLI | 12건, exit 0 | 동일 출력, exit 0 |
| git diff --check | exit 0 | exit 0 |

일반 실패·오류는 기준선과 최종 모두 0이며 최종 예상 실패·skip·unexpected success도 0이다.
검증 명령은 `python -B -m unittest discover -s tests`와 같은 명령의
`-p test_normalizer.py`, `-p test_application_boundary.py`, `-p test_analyzer.py`,
`-p test_role_classifier.py`, `-p test_recommender.py`, `-p test_skill_extractor.py`,
`-p test_migrations.py`, `-p test_persistence_integrity.py`이다.
CLI는 `python -X utf8 -B scripts/run_demo.py`, 공백 검사는 `git diff --check`로 실행했다.

기존 순서는 결측 → 신입 → 경력 → 무관/관계없음 → 기타였다. 따라서 None/빈 문자열/공백/미상은
미상, 신입은 신입, 경력·경력 1년·경력 3년 이상은 경력, 경력무관도 경력, 관계없음은 무관,
신입/경력은 신입이었다. 저장소 XML fixture의 경력·공백과 inline Experienced는 각각
경력·미상·기타였다. 무관 판정을 먼저 수행하고 혼합 범주를 보존하도록 수정했다.

KD-08 기존 테스트를 그대로 유지하고 expectedFailure를 제거했다. normalizer에 혼합 표현,
canonical/원문 멱등성, 기존 XML fixture 정제 테스트 3개와 application 경력별 DB 왕복 테스트
1개를 추가했다. 기존 persistence 멱등성 테스트의 입력을 확대하고 경력무관 기대값을 무관으로
고쳤다. 무관한 기대값은 변경하지 않았다. 운영 코드 변경은 normalize_career 함수뿐이다.

샘플 직무·기술 집계와 추천 Python → A/B Test → Tableau → Statistics → GA4 및 설명은
Phase 2C와 동일하다. 실 API·실사용 DB·UI 실행은 이번 검증에 포함하지 않았고 관련 코드를
변경하지 않았다. 이미 잘못 축약해 저장한 경력 값은 추정 복원하지 않는다.
canonical 정책은 [데이터 설계](02_data_design.md#phase-2d-경력-정규화-계약)를 따른다.
Phase 2D에서 종료하며 Work24 상세 수집과 Phase 3는 시작하지 않았다.

## Phase 3A 검증 (2026-09-16)

브랜치 `refactor/v2`, 시작 HEAD `e6a53c4` (`fix: correct career normalization semantics`).
시작 작업 트리에는 tracked 11개 수정(394 insertions/44 deletions)과 untracked 4개가 있었다.
상세 계약·요청·파서·v2 DDL/이전·저장·pipeline·CLI와 상세 fixture/test가 이미 구현되어 있었다.
reset/checkout/reclone 없이 이를 이어서 검토·보완했다. `git diff --check`는 시작부터 통과했다.

마지막 커밋 기준선은 226개 모두 통과였고, 재개 시 실제 미커밋 상태는 **248개 모두 통과**였다.
최종은 **275개 모두 통과**, expected failures/failures/errors/skips/unexpected successes 모두 0이다.
환경은 Linux, Python 3.12.3, unittest/SQLite/mock이다. 전체 최종 실행 시간은 2.548초이며
환경에 따라 달라진다. subTest 입력 조합은 개수에 별도로 더하지 않았다.

| 최종 검증 | 결과 |
|---|---|
| 전체 unittest | 275/275 통과 |
| Work24 목록/client | 18/18 통과 |
| Work24 상세 parser | 14/14 통과 |
| Work24 상세 client | 9/9 통과 |
| migration | 19/19 통과 |
| storage + storage boundary | 16/16 통과 |
| 상세 persistence/path boundary | 7/7 통과 |
| 기존 persistence integrity | 15/15 통과 |
| pipeline + detail pipeline | 16/16 통과 |
| normalizer | 11/11 통과 |
| skill extractor | 42/42 통과 |
| role classifier | 34/34 통과 |
| recommender | 24/24 통과 |
| collection CLI | 4/4 통과 |
| sample CLI | 12건, 기존 집계·추천 순서, exit 0 |
| git diff --check | 공백 오류 없음, exit 0 |

실행 명령:

```bash
python -B -m unittest discover -s tests
python -B -m unittest discover -s tests -p 'test_work24*.py'
python -B -m unittest discover -s tests -p test_migrations.py
python -B -m unittest discover -s tests -p 'test_storage*.py'
python -B -m unittest discover -s tests -p test_posting_details.py
python -B -m unittest discover -s tests -p test_persistence_integrity.py
python -B -m unittest discover -s tests -p 'test_pipeline*.py'
python -B -m unittest discover -s tests -p test_normalizer.py
python -B -m unittest discover -s tests -p test_skill_extractor.py
python -B -m unittest discover -s tests -p test_role_classifier.py
python -B -m unittest discover -s tests -p test_recommender.py
python -B -m unittest discover -s tests -p test_collect_work24_cli.py
python -B scripts/run_demo.py
git diff --check
git status
```

상세 parser는 공식 문서의 계층을 따르는 합성 fixture로 선택 20개 원문 필드·nullable 값,
줄바꿈·CDATA·namespace·keyword 순서/중복·잘못된 계층·오류 응답을 검증한다.
request 테스트는 endpoint·authKey/wantedAuthNo/callTp/returnType/infoSvc·timeout·UTF-8·identity·UTC
시각을 확인한다. HTTP/timeout/불완전 read/encoding/API 오류는 safe category로 분류하고
키·응답 본문이 exception/traceback/CLI/failure reason에 실리지 않도록 검증했다.
새 목록 보안 테스트에서 호출 소스 줄에 쓴 가짜 키 리터럴이 traceback에 나타나는 테스트 오류가
한 번 있었으며, 실제 호출처럼 변수로 전달하도록 고쳤다. 운영 예외의 민감한 context 노출은 없다.

KD-09 기존 오류 XML 테스트는 정상 빈 목록과 오류를 구분하는 회귀 테스트로 전환했다.
예상 밖 목록 envelope와 malformed XML은 안전한 오류를 반환하고 namespace 목록을 지원한다.
error/errorCode/errorCd 인식은 방어적인 합성 사례이며 미확인 공식 오류 코드 표를 만들지 않았다.
목록 함수의 성공 반환 계약·페이지 요청 수는 유지하되 실패 예외 타입은 Work24Error로 통일했다.

신규 `test_posting_details.py`는 첫 저장/조회, 동일·변경 refresh, 새 fetched_at, NULL·JSON keywords,
유효성 검증, orphan과 잘못된 source, 복합 identity/CASCADE, 배치 rollback, caller transaction,
path 재개방과 성공/실패 연결 종료를 검사한다. 기존 job_postings/skills/created_at도 유지된다.

`test_migrations.py`에 추가한 v1 fixture는 Phase 2D schema를 고정했다. 기존 두 테이블의
모든 INSERT/UPDATE/DELETE를 거절하는 trigger로 v1→v2의 추가 이전을 확인한다.
과거 추출값/수동 기술도 그대로 남는다. v0→v2 공고·created_at 보존 및 기존 기술 재구성,
v0의 최종 v2 DDL 실패와 v1 DDL 실패 rollback, fresh→v2, v2 재개방을 검증했다.
파일 백업의 원본 dump/user_version/integrity, 복사본 복원, 실패 시 migration 중단,
불완전 백업 제거, 재시도 시 새 백업과 기존 파일 불변, 현재 DB 추가 백업 부재도 확인했다.

`test_pipeline_details.py`는 20개 목록/19개 상세 성공/1개 실패와 이후 failed refresh의 이전 상세·
fetched_at 보존을 별도로 검증한다. 다른 identity의 성공은 계속 저장한다. 키워드 간 중복은
정제 후 한 번만 요청한다. HTTP boundary에서 이전 storage 연결이 모두 닫혔음을 확인하고
별도 SQLite writer가 즉시 BEGIN IMMEDIATE를 획득하며 전체 목록을 볼 수 있음을 검사한다.
상세만의 기술·직무·경력 문자열을 넣어도 저장 기술·분석·추천·정규화 career가 바뀌지 않는다.

CLI 테스트는 실제 CLI→pipeline→임시 DB와 mocked HTTP를 연결한다. 기본 목록 전용 exit 0,
상세 전체 성공 exit 0, 상세 부분 실패 exit 2 및 성공 데이터 보존, 목록 실패 exit 1과 안전한
출력을 확인한다. 자동 테스트는 실 네트워크·API 키·사용자 DB를 사용하지 않는다.

샘플 CLI는 12건, 데이터 분석가 6/ML 3/데이터 엔지니어 2/BI 1이며 SQL 보유 분석가의 추천은
Python(5/6) → A/B Test(2/6) → Tableau(2/6) → Statistics(1/6) → GA4(1/6)다.
추출기·분류기·추천기·정규화기 운영 코드는 수정하지 않았다.

실 API smoke·사용자 실제 DB migration·UI·동시 migration writer·프로세스 강제 종료·디스크
고갈은 실행하지 않았다. 문서로 endpoint/계층을 확인했지만 실제 키 권한·응답 변종·요청 한도는
실환경 검증이 남는다. 자유 텍스트의 개인정보 자동 정제, TTL/재시도/이력 snapshot/실패 이력
영속화는 없다. 백업은 최초 migration을 다른 writer 중지 상태로 실행하는 운영 정책을 따른다.
상세 필드는 raw evidence로만 보존한다. 요건 추출·job matching은 없으며 **Phase 3B는 미시작**이다.

## Phase 3B 검증 (2026-09-17)

시작 HEAD는 `78276e0` (`feat: add Work24 job detail ingestion`), 브랜치는 `refactor/v2`,
작업 트리는 깨끗했다. 구현 전 git status/log, 전체 unittest **275/275**, sample CLI 12건·exit 0,
git diff --check를 확인했다. 지정 아키텍처 문서와 원문/시장 추출/수집/저장/UI 경계를 검토하고
순수 추출 + 조회 시 재계산, 파생 persistence 없음, schema v2 유지 결정을 먼저 보고했다.

최종 **306개 모두 통과**다. expected failures/failures/errors/skips/unexpected successes 모두 0.
Linux/Python 3.12.3에서 전체 최종 실행은 2.982초이며 시간은 환경에 따라 달라진다.
기존 테스트를 수정하거나 예상 실패로 바꾸지 않았다. 신규 테스트 method는 31개이며
18개 수동 기대값 평가 사례와 subTest 조합은 테스트 수에 중복 합산하지 않았다.

| 최종 검증 | 결과 |
|---|---|
| 전체 unittest | 306/306 통과 |
| requirement extractor | 23/23 통과, 그 안에 평가 fixture 18사례 포함 |
| requirement application/CLI | 8/8 통과 |
| Work24 목록/detail parser/client | 41/41 통과 |
| migration | 기존 19/19 통과; 새 migration 없음 |
| pipeline 전체 | 24/24 통과; 위 application 8개 포함 |
| storage + storage boundary | 16/16 통과 |
| raw posting detail persistence | 7/7 통과 |
| persistence integrity | 15/15 통과 |
| normalizer | 11/11 통과 |
| skill extractor | 42/42 통과 |
| role classifier | 34/34 통과 |
| analyzer | 17/17 통과 |
| recommender | 24/24 통과 |
| sample CLI | 12건, 기존 출력 유지, exit 0 |
| git diff --check | 공백 오류 없음, exit 0 |

실행 명령:

```bash
python -B -m unittest discover -s tests
python -B -m unittest discover -s tests -p test_requirement_extractor.py
python -B -m unittest discover -s tests -p test_pipeline_requirements.py
python -B -m unittest discover -s tests -p test_migrations.py
python -B -m unittest discover -s tests -p 'test_work24*.py'
python -B -m unittest discover -s tests -p 'test_pipeline*.py'
python -B -m unittest discover -s tests -p 'test_storage*.py'
python -B -m unittest discover -s tests -p test_posting_details.py
python -B -m unittest discover -s tests -p test_persistence_integrity.py
python -B -m unittest discover -s tests -p test_normalizer.py
python -B -m unittest discover -s tests -p test_skill_extractor.py
python -B -m unittest discover -s tests -p test_role_classifier.py
python -B -m unittest discover -s tests -p test_analyzer.py
python -B -m unittest discover -s tests -p test_recommender.py
python -B scripts/run_demo.py
git diff --check
git status
```

### 평가 근거와 수정한 경계

`tests/fixtures/requirements/evaluation.json`은 직접 만든 짧은 합성 문장 18사례다.
각 사례에 검토 이유·입력·기술별 예상 분류·품질 상태를 고정했다. 실제 공고를 복사하지 않았다.
한국어 필수/우대/업무 섹션, 영어 섹션, 제목 없는 단서, mixed posting, 기술스택,
부정문, 여러 섹션의 같은 기술, Spring/Boot 겹침, alias, 기술 없는 문장, 비기술 자격,
모호성, 알 수 없는 제목/서식, 중립 섹션 전환, certificate/computer_skill과 inline 조각을 포함한다.

추가 테스트는 단서가 해당 조각에만 적용됨, 부정이 섹션/우대 필드보다 우선함,
필수/우대 충돌·질문·인용·대안·복합 conjunction의 미분류, unknown HTML/표 제목의 상태 종료,
CRLF/Unicode 원문 slice와 섹션 위치, 필드 간 상태 격리, keyword 중복 index, 모든 근거 보존,
canonical alias/부모 기술 비추론, 결정성·버전·입력 불변·결과 객체 독립성,
네 품질 상태·미지원 기술·비기술 조건·잘못된 입력 실패를 검증한다.
Phase 3A XML fixture를 실제 parser로 읽고 파생 추출해도 원문이 동일함을 확인했다.

초기 테스트에서 `필수가 아닙니다`의 활용형을 놓쳐 required 섹션이 잘못 유지되는 실패를
확인했다. 부정 패턴을 보완하고 해당 회귀 사례를 그대로 통과시켰다. 운영 검토에서
일반적인 `필요합니다`/`반드시`/`plus`만으로 보유 조건을 추정하지 않도록 범위를 제한했다.
회의 참석/지원서 의무와 기술 보유 조건이 혼동되는 명백한 사례도 미분류로 남긴다.
테스트 기대값을 오분류에 맞춰 낮추지 않았다.

### application·원문·기존 동작 보존

새 pipeline 조회 테스트는 실제 임시 SQLite로 수행한다. 상세 연결이 닫힌 뒤 추출이 시작되고
별도 writer가 즉시 잠금을 얻을 수 있음을 확인했다. 추출 전후 DB dump는 동일하다.
성공 raw refresh 뒤 최신 원문·fetched_at을 읽어 stale 요건 없이 재계산하며, 실패 refresh 뒤에는
이전 raw와 같은 파생 결과가 남는다. 추출 오류를 주입해도 최신 raw·전체 DB·이전 반환 객체가
보존되고 오류가 호출자에게 전달된다. source별 같은 ID와 부모 삭제도 독립적이다.

`inspect_requirements.py`는 실제 main/인수 파서와 pipeline을 연결해 JSON provenance 및
detail_not_fetched 상태를 검증했다. Streamlit은 수정·실행하지 않았다. 새 추출 테스트는
HTTP와 SQLite 접근을 차단하고, application 테스트는 HTTP를 차단한다. 실 네트워크·Work24 키·
사용자 DB는 필요 없다. Work24 client/storage/migrations/시장 extractor/taxonomy/normalizer/
classifier/analyzer/recommender의 운영 코드는 변경하지 않았다.

샘플은 12건, 데이터 분석가 6/ML 3/데이터 엔지니어 2/BI 1이다. 기술 집계와 추천
Python(5/6) → A/B Test(2/6) → Tableau(2/6) → Statistics(1/6) → GA4(1/6)는 기존과 같다.
상세 required-only로 시장 집계를 바꾸지 않았다.

### 남은 한계

합성 fixture와 지정 경계의 통과를 실제 공고 전체의 정확도로 주장하지 않는다. 복잡한 부정,
문장 간 참조, 임의 제목/서식, HTML/표, 동의어·미지원 기술, 여러 대상의 단서 범위는 제한적이다.
보수적인 규칙은 실제 요건도 unspecified로 남길 수 있다. 별도 정밀도/재현율 평가는 하지 않았다.
raw free text와 추출 근거에 대한 자동 개인정보 정제도 없다.

파생 데이터는 저장하지 않아 이전 버전 결과의 역사 조회나 SQL 근거 검색은 제공하지 않는다.
같은 원문·현재 taxonomy·추출기 버전 1에서 결정적으로 재계산한다. schema v2와 기존 migration/
백업 정책을 유지한다. raw 원문을 파괴하지 않으므로 후속 규칙 개선 후 재처리할 수 있다.
프로필·매칭·점수·LLM·지원 추적은 없으며 **Phase 4 이상은 시작하지 않았다**.

## Phase 3C 검증 (2026-09-17)

시작 commit은 `f4997c3` (`feat: add structured job requirement extraction`), branch는
`refactor/v2`이며 작업 트리는 깨끗했다. 수정 전 지정 명령으로 전체 **306/306**, 샘플 CLI 12건·
exit 0, diff 공백 오류 없음을 확인했다. Linux/Python 3.12.3, 표준 unittest/mock/임시 SQLite를 쓴다.

### corpus와 보정 전후 지표

기존 18개를 삭제하지 않고 **60개 수동 기대값 합성 사례**로 확장했다. 입력, review_note,
canonical 기술별 분류, 품질, 선택적 expected_groups가 label이다. 한 사례에 여러 문장/기술이
있을 수 있으며 총 **144개 기술 분류, 13개 그룹**이다. 기대값은 의도한 의미로 정했고 추출
결과에 맞춰 낮추지 않았다. 실제 공고 전문·연락처·키는 포함하지 않는다.

범위: 한국어/영어 필수·우대·업무, 섹션 없음, stack, 양 언어 제목, 공동 접속, 대안, 부정,
혼합 문맥, 반복/충돌, Spring/Boot와 부모 비추론, alias, 미지원 Elixir, 모호/이상 서식,
필드별 문맥과 keyword 메타데이터. 전용 테스트에는 결측·품질·offset·실패·그룹 반복도 있다.

**운영 규칙 수정 전에** 확장 corpus를 v1으로 실행해 아래 baseline을 기록했다.
보정 중 부정 나열의 활용형에도 같은 오탐이 있음을 추가 발견해 `negated_comma_list`의 입력만
확장했다. 원래 문장·기대값을 모두 유지했다. 수정 전 추출기를 최종 corpus에 다시 실행한 결과도
아래와 같았다. 최종 corpus SHA-256:
`3ffe3bf8ddeb50fcc8dba57b5bfa40c7b630754fc301ed33967f1f1af6e14fd9`.

| 개별 기술 분류 | v1 TP/FP/FN | v1 fixture precision / recall / F1 | v2 TP/FP/FN | v2 fixture precision / recall / F1 |
|---|---|---|---|---|
| required | 31 / 3 / 11 | 91.1765% / 73.8095% / 81.5789% | 42 / 0 / 0 | 100% / 100% / 100% |
| preferred | 24 / 0 / 1 | 100% / 96% / 97.9592% | 25 / 0 / 0 | 100% / 100% / 100% |
| responsibility | 12 / 0 / 1 | 100% / 92.3077% / 96% | 13 / 0 / 0 | 100% / 100% / 100% |
| unspecified | 61 / 13 / 3 | 82.4324% / 95.3125% / 88.4058% | 64 / 0 / 0 | 100% / 100% / 100% |

- 사례 완전 일치: **40/60 → 60/60**. 개별 분류 일치: **128/144 → 144/144**.
- 클래스 불일치: **16 → 0**. 분류 FP/FN 합계: 각각 **16 → 0**.
- 그룹 일치: **0/13 → 13/13**, 그룹 FP **0 → 0**, FN **13 → 0**.
  v1 그룹 precision은 예측이 없어 N/A, recall/F1은 0. v2 그룹 precision/recall/F1은 각각 100%.
  그룹 기대 분포는 required 9, preferred 3, unspecified 1이다. responsibility 그룹 표본은 없다.
- 개별 분류와 그룹의 오탐을 합산한 안전 지표: **required FP 3 → 0, preferred FP 0 → 0**.

v1 required 오탐 사례는 `comma_any_of_under_heading`(Java), `negative_heading_boundary`(Docker),
`negated_comma_list`(Java)다. required 누락은 ability_required(SQL), qualifications_heading(Python),
english_all_of(Java/SQL), comma_all_of(Spring Boot/JPA), explicit_spring_pair(Spring/Spring Boot),
alias_all_of(Spring Boot/PostgreSQL), crlf_spacing(Python)다. preferred 누락은
bold_colon_heading(Docker), responsibility 누락은 mixed_work_and_required(SQL)다.
unspecified FP 13개는 이 양성 분류 누락에 대응하고, FN 3개는 필수 오탐에 대응한다.
그룹 없는 v1은 모든 expected_groups 사례를 누락하며, 개별 분류가 맞아도 사례 전체는 실패한다.

이 값은 **같은 수동 합성 fixture로 규칙을 보정하고 평가한 결과**다. 독립 holdout·실공고·시장·
운영 정확도가 아니며 100%를 실서비스 정확도로 주장하지 않는다. 실제 대표 코퍼스는 미평가다.

### 평가 계산·gate·재현

평가 단위는 (case, canonical skill, effective class)다. 잘못된 분류는 예측 클래스의 FP이자
기대 클래스의 FN이다. 누락/추가 기술과 중복 결과도 센다. 그룹은 relation/class/구성원 집합을
비교하되 반복 그룹 개수는 보존한다. 개별 기술 지표와 그룹 지표는 별도로 보고하며 안전 FP
합계만 함께 표시한다. 분모가 없는 precision/recall/F1은 100%로 꾸미지 않고 N/A(null)다.
provenance 정확성은 별도 원문 slice·section·규칙 테스트가 검사한다.

```bash
python -B scripts/evaluate_requirements.py
python -B scripts/evaluate_requirements.py --json
```

`--fixtures PATH`로 다른 수동 label 파일을 검사할 수 있다. 기본 CLI는 각 클래스 fixture
precision/recall/F1·FP/FN, 필수/우대 오탐, 그룹 지표, 불일치 사례를 출력한다. JSON에는 모든
세부 지표와 corpus hash가 있다. 모든 사례의 기술 분류·그룹·품질이 정확히 맞아야 **exit 0**이다.
불일치가 있으면 **exit 1**, 파일/입력/추출 오류도 성공으로 숨기지 않는다. 필수/우대 오탐 0이
필수 조건이며, 전부 미분류/빈 결과로 만들어 누락을 늘려도 통과하지 못하는 엄격한 회귀 gate다.
실공고 정밀도 목표 수치를 임의로 설정한 것이 아니다.

기존 버전 기준선 재현(현재 corpus/평가기로 기존 commit의 순수 추출 함수만 실행):

```bash
PYTHONPATH=src python -B - <<'PY'
import json
import subprocess
from pathlib import Path
from jobskillradar.requirement_evaluation import evaluate_requirements
namespace = {'__name__': 'jobskillradar._baseline', '__package__': 'jobskillradar'}
source = subprocess.check_output([
    'git', 'show', 'f4997c3:src/jobskillradar/requirement_extractor.py'
], text=True)
exec(compile(source, 'phase3b_baseline', 'exec'), namespace)
cases = json.loads(Path('tests/fixtures/requirements/evaluation.json').read_text())
print(json.dumps(evaluate_requirements(cases, extractor=namespace['extract_requirements']), indent=2))
PY
```

### 최종 회귀 검증

전체 **328/328 통과**, failures/errors/expected failures/skips/unexpected successes 모두 0.
기존 306개를 유지하고 22개 method를 추가했다. 기존 버전 assertion만 의미 변경에 맞춰 1→2로
갱신했다. 60개 fixture와 subTest는 method 수에 중복 합산하지 않았다.

| 집중 검증 | 결과 |
|---|---|
| requirement extractor | 33/33 |
| requirement evaluation | 12/12 |
| pipeline requirements | 8/8, 위 둘과 합계 53개 |
| Work24 list/detail parser/client | 41/41 |
| migration | 19/19, schema 변경 없음 |
| storage + boundary / detail persistence / persistence integrity | 16/16, 7/7, 15/15 |
| pipeline 전체 | 24/24 |
| normalizer / skill extractor / role classifier | 11/11, 42/42, 34/34 |
| analyzer / recommender | 17/17, 24/24 |
| evaluation CLI | 60/60사례·144/144분류·13/13그룹, exit 0 |
| sample CLI / diff check | 기존 출력 유지·exit 0 / 공백 오류 없음 |

전체 unittest, 평가 CLI, 위 각 suite의 `python -B -m unittest discover -s tests -p FILE_PATTERN`,
`python -B scripts/run_demo.py`, `git diff --check`, `git status`로 검증했다.
샘플은 12건, 데이터 분석가 6/ML 3/데이터 엔지니어 2/BI 1이며 추천 순서와 분모는
Python(5/6) → A/B Test(2/6) → Tableau(2/6) → Statistics(1/6) → GA4(1/6)로 유지한다.

추출/평가 테스트는 HTTP/DB 접근을 차단하고 application은 임시 DB와 가짜 transport를 쓴다.
키·실제 네트워크·사용자 DB가 필요 없다. 실 Work24 smoke는 수행하지 않았고 Streamlit은
변경/실행하지 않았다. 새 persistence나 migration은 없으며 schema v2, 원문 저장·실패 갱신
보존·연결 종료 경계·시장 분석·직무 분류·추천·경력 정규화를 유지한다.

중첩 AND/OR, 복잡한 부정/예외, 문장 간 참조, 임의 제목/HTML/표, 미지원 기술·동의어는
여전히 제한적이다. alias/parent-child 추론 규칙은 바꾸지 않았다. 빈 required를 요건 없음으로
읽거나 any_of를 여러 독립 필수로 읽어서는 안 된다. 미래 소비자는 개별 요약과 그룹·원문·품질을
함께 처리해야 한다. 사용자 프로필·매칭·점수·Phase 4 이상은 시작하지 않았다.
