# Phase 1A — Regression Test Baseline

최신 결과는 문서 끝의 [Phase 1C 재개 검증](#phase-1c-재개-검증-2026-09-16)을 따른다. 앞의 Phase 1A/1B 수치와 결함 설명은 당시 기록이다.

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
