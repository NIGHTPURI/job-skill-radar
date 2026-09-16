# 데이터 설계

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
