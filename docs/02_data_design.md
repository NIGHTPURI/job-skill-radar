# 데이터 설계

## Phase 1C 현재 영속 계약

2026-09-16 기준. 아래 절이 최신 스키마이며 이후의 기존 MVP 표는 수집 필드 설명을 위한 과거 기록이다.

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

기술 추출 개선만으로 직무 분류가 정확해지지는 않는다. `Backend Engineer` + `Spring Boot Redis`는 여전히 데이터 분석가이고, `Docker.`의 검출 복원은 기존 분류기의 데이터 엔지니어 규칙을 활성화한다. `mobile developer`→BI, `retail assistant`→ML도 남아 있다. 이는 Phase 2B 검토사항이며 분류기와 추천 점수 공식은 수정하지 않았다.

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
- 경력은 `신입`, `경력`, `무관`, `기타`로 표준화한다.
- 기술명은 대소문자와 별칭을 통일한다.
- 동일 `posting_id`는 중복 저장하지 않는다.

## 기술 키워드 예시

- 언어: Python, Java, SQL, R
- 분석: Pandas, NumPy, Statistics, A/B Test
- 시각화: Tableau, Power BI, Looker, Plotly
- 엔지니어링: Spark, Airflow, Kafka, Docker
- 클라우드/DB: AWS, GCP, Azure, MySQL, PostgreSQL, MongoDB
- ML/AI: Machine Learning, Deep Learning, NLP, PyTorch, TensorFlow
