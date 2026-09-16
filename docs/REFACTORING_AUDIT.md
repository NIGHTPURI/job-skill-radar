# Phase 0 — Repository Audit

감사일: 2026-09-16. 기준 커밋: `0ee3c40` (`Initial Job Skill Radar MVP`).
대상: 로컬 `NIGHTPURI/job-skill-radar` 체크아웃의 전체 추적 파일 30개. 시작 시 작업 트리는 깨끗했다.
운영 코드·설정·기존 테스트는 변경하지 않았다. 아래 내용은 현재 구현에 대한 감사이며 목표 기능이 이미 있다는 뜻이 아니다.

## 1. 증거와 검증 범위

- **확인된 사실**: 모든 추적 소스, 스크립트, 테스트, 문서, 의존성 및 설정 파일을 읽었다. 로컬에 실제 DB, `.env`, `.venv`, 추가 데이터 파일은 없었다.
- **실행 확인**: Python 3.14.5에서 기존 unittest 4개와 샘플 CLI가 성공했다. 별도 임시 테스트 파일 없이 메모리 SQLite 및 순수 함수 호출로 경계 사례를 확인했다.
- **미검증**: 실제 고용24 응답, 인증키 권한, 상세 API 계약, 실제 공고 품질, 브라우저 화면, 배포 환경. `streamlit`, `pandas`, `plotly`가 현재 Python 환경에 없어 UI를 실행하지 않았다. 패키지를 설치하거나 외부 API를 호출하지 않았다.
- **구분 원칙**: API 관련 필드 설명은 코드가 읽는 필드에 관한 사실이다. 현재 제공자가 실제로 반환하는 모든 필드나 상세 API 제공 여부를 확인한 것으로 해석하지 않는다. 아래 권고는 구현하지 않았다.

## 2. 저장소 구조와 실행 진입점

```text
.
├── app.py                         Streamlit 진입점
├── README.md                      기존 포트폴리오 목적·실행 안내
├── .env.example                   WORK24_AUTH_KEY, JOB_RADAR_DB_PATH
├── .gitignore / .gitattributes     비밀·생성물 제외, 줄바꿈 규칙
├── .streamlit/config.toml          headless, 사용 통계 비활성화
├── requirements.txt               UI 의존성 및 현재 미사용 패키지
├── requirements-ml.txt            선택적 scikit-learn, 현재 모델 없음
├── scripts/
│   ├── run_demo.py                DB·외부 패키지 없는 샘플 분석
│   ├── seed_sample.py             샘플 정제 후 DB 저장
│   ├── collect_work24.py          반복 --keyword, --pages, --display
│   ├── setup_project.ps1          venv·의존성 설치 및 샘플 DB 생성
│   └── start_dashboard.ps1/.cmd   venv의 Streamlit, 포트 8501
├── src/jobskillradar/
│   ├── __init__.py
│   ├── config.py / sample_data.py
│   ├── work24_client.py / normalizer.py / storage.py
│   ├── pipeline.py
│   └── skill_extractor.py / analyzer.py / recommender.py
├── tests/test_core.py / test_storage.py
└── docs/01_requirements.md … 04_other_pc_setup.md
```

`data/job_skill_radar.sqlite`는 실행 시 생성될 기본 경로이며 현재 포함된 데이터 파일이 아니다. 실제 데이터는 Python 상수 `SAMPLE_POSTINGS` 12건뿐이다. `pyproject.toml`, 잠금 파일, CI 설정, DB 마이그레이션, 테스트 전용 설정은 없다. app/CLI/tests가 각각 `src`를 `sys.path`에 넣는다.

`requirements.txt`: `streamlit>=1.58`, `pandas>=2.2`, `plotly>=5.22`, `requests>=2.32`, `python-dotenv>=1.0`. 실제 HTTP는 urllib, 환경파일 처리는 자체 구현이므로 requests와 python-dotenv는 현재 호출되지 않는다. ML 의존성도 코드에서 사용하지 않는다. 하한만 지정하므로 설치 결과를 고정하지 못한다.

## 3. 현재 전체 런타임 흐름

1. `streamlit run app.py` 또는 시작 스크립트가 app의 최상위 코드를 실행한다. `src` 경로 등록 후 UI와 파이프라인 함수를 import한다.
2. `config.load_env_file()`은 최초 한 번 `.env`를 파싱한다. 기존 환경변수를 덮어쓰지 않는다. 파일이 없어도 `_ENV_LOADED=True`가 되므로 같은 프로세스에서 나중에 파일을 만들거나 수정해도 다시 읽지 않는다. 상대 DB 경로는 프로젝트 루트를 기준으로 한다.
3. 기본 모드는 `DB 우선`. `load_analysis(mode)`가 `load_db_analysis()`를 호출한다. 이 함수는 DB 디렉터리·파일과 스키마를 만들 수 있으므로 이름과 달리 순수 읽기가 아니다.
4. DB에 행이 있으면 전부 읽고 다시 정제·추출·분류·집계한다. 행이 없으면 `analyze_sample()`로 전환한다. `샘플` 모드는 바로 샘플을 분석한다. **DB/API 예외 발생 시 자동 샘플 대체는 구현되어 있지 않다.**
5. 샘플 저장 버튼은 정제된 12건을 저장한다. 수집 버튼은 쉼표로 나눈 키워드와 페이지 수를 `collect_work24_to_db()`에 전달한다. 빈 키워드 목록은 pipeline의 기본 5개 키워드로 대체된다.
6. 수집은 키워드별·페이지별 동기 순차 요청 → XML 목록 파싱 → 모든 결과를 메모리에 모음 → 정제 및 ID 중복 제거 → SQLite 저장 순서다. `collect_and_analyze()`는 별도 경로로 DB 저장 없이 수집·정제·분석하며 현재 app/CLI의 호출자는 없다.
7. 정제는 알려진 14개 필드만 문자열로 남기고 지역·경력을 축약한다. 빈 ID를 버리고 같은 ID는 최초 공고를 유지한다. 날짜·급여·직무명은 실제로 표준화하지 않는다.
8. 저장 시 제목·description에서 기술을 추출하여 `posting_skills`에 넣는다. 로드 후 분석에서는 이 테이블을 읽지 않고 다시 추출한다.
9. 분석은 각 공고에 `skills`, `role`을 붙인다. 전체 기술·직무·경력·지역 Counter와 직무별 기술 Counter를 만든다. 한 공고 안의 같은 기술은 한 번만 센다.
10. UI는 Counter를 DataFrame으로 바꿔 차트를 그린다. 목표 직무·보유 기술을 추천 함수에 전달하고 점수·고정 이유 문구를 표시한다. 공고 표는 회사, 제목, 직무, 지역, 경력, 기술, 마감일만 표시한다. URL은 저장하지만 UI 표에 없다.

샘플 결과: 12건, 데이터 분석가 6 / 데이터 엔지니어 2 / ML 엔지니어 3 / BI 분석가 1. SQL 보유 데이터 분석가 추천은 Python 9, Statistics 4, Tableau 3, Pandas 3, A/B Test 2다.

## 4. 모듈 책임·의존성·응집도

| 모듈 | 책임 / 성격 | 의존성과 호출자 | 평가 |
|---|---|---|---|
| `app.py` | 화면, 입력 파싱, 소스 선택, 실행 연결, 캐시 / UI+application | pandas/plotly/Streamlit, config/pipeline/recommender/analyzer → Streamlit이 실행 | 점수 계산 자체는 없음. 소스 정책·입력 계약이 UI에 남음 |
| `config.py` | 환경 로딩·DB 경로 / infrastructure | os/pathlib → app/pipeline/수집·seed CLI | 작고 응집적이나 전역 1회 로딩이 암묵적 상태 |
| `sample_data.py` | 고정 예제 12개 / fixture | 외부 의존 없음 → pipeline, storage test | 재현성 좋음. 모두 데이터 직군, 현재 기준 마감된 날짜 |
| `normalizer.py` | 필드 정리, 지역·경력, 중복 제거 / domain+ingestion policy | 순수 Python → pipeline/tests | 작지만 정보 손실 및 출처 없는 ID 정책 포함 |
| `skill_extractor.py` | 별칭 사전, regex 추출, 보유 기술 정규화 / domain | re → analyzer/storage/recommender/tests | UI와 분리됨. 데이터 정의와 알고리즘 혼재 |
| `analyzer.py` | 직무 규칙, 공고 enrichment, 빈도 집계 / domain+analysis | extractor, Counter → pipeline/app/CLI | 현재 규모에서는 합리적. 직무 확대 시 classifier 분리 가치 있음 |
| `recommender.py` | 빈도+직무 기초 가산 / domain | canonicalize_skills → app/CLI/tests | 순수 함수 유지 가치. 가산점·설명 계약 부족 |
| `work24_client.py` | URL·요청·XML·필드 매핑 / collection infrastructure | urllib/ElementTree → pipeline | 소스 격리는 이미 있음. 오류와 데이터 품질 표현 없음 |
| `storage.py` | DDL·연결·저장·조회+기술 추출 / persistence+domain | sqlite3/pathlib/datetime/extractor → pipeline/tests | 추출 책임과 저장 책임 결합, 중복 갱신 불일치 |
| `pipeline.py` | sample/DB/API 흐름 연결 / application | config, collector, normalizer, analyzer, storage, fixtures → app/CLI/tests | 서비스 계층의 시작점으로 보존. 전역 경로·함수 직접 결합, 수집 루프 중복 |
| `__init__.py` | 패키지 설명·exports | 런타임 로직 없음 | `__all__`에 pipeline은 없으나 직접 import 가능 |
| CLI 3개 | 인수·출력·종료 코드 / adapter | pipeline/config, demo는 analyzer/recommender | 유용한 얇은 진입점 |
| PowerShell/CMD 3개 | 로컬 설치·실행 / 운영 | venv/pip/Streamlit | 유지할 가치. setup은 샘플을 실제 기본 DB에 넣음 |

## 5. app.py 책임 분석

| 현재 책임 | 향후 위치 | 이유 |
|---|---|---|
| page config, sidebar, charts, metrics, table, spinner, success | app 유지 | UI 고유 책임 |
| `counter_frame`, 기술 리스트의 표시 문자열 변환 | app 또는 화면이 커질 때 UI helper | 도메인 연산이 아닌 표시 변환 |
| `load_analysis`의 DB 우선/샘플 fallback 결정 | pipeline의 application 함수 | CLI/테스트에서도 소스 정책 검증 가능 |
| 쉼표 입력 분리, widget 범위 | 기본 분리는 UI, 유효성 검증은 application | CLI 등에서 동일한 입력 규칙 보장 |
| 목표 직무 선택·보유 기술 입력 및 추천 호출 | UI에 입력·호출 유지 | 분류·계산은 이미 외부에 있음 |
| 저장·수집 호출과 캐시 무효화 | 서비스 호출은 UI adapter, 결과 정책은 pipeline | UI가 SQL/HTTP를 직접 호출하는 것은 아님 |
| `@st.cache_data(ttl=60)` | Streamlit adapter 유지 | domain에 Streamlit 의존성 도입 불필요 |

캐시 키의 명시적 입력은 `mode`뿐이다. DB 경로, DB 변경 revision, 추출 규칙 버전은 없다. 외부 CLI 저장은 최대 TTL 동안 반영이 늦을 수 있고 설정 변경도 키에 포함되지 않는다. 저장/수집 성공 뒤 `st.cache_data.clear()`는 전체 data cache를 지운다. 보유 기술 변경은 추천을 다시 계산하지만 분석은 캐시를 재사용한다. API 오류를 잡는 UI 코드가 없어 정상 차트 렌더링 이전에 실행이 끊길 수 있다.

따라서 app을 대규모로 재작성할 근거는 없다. 가장 큰 문제는 파일 크기보다 딕셔너리 결과 계약, 소스 정책, 캐시의 숨은 입력이다.

## 6. Work24 통합

코드의 목록 endpoint: `https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do`.
요청은 `authKey`, `callTp=L`, `returnType=XML`, `startPage`, `display`, `sortOrderBy=DESC`를 보내고 keyword/region/occupation은 값이 있을 때 추가한다. UI/CLI는 region/occupation을 노출하지 않는다.

| XML에서 읽는 필드 | 내부 결과 |
|---|---|
| wantedAuthNo, company, title | posting_id, company, title |
| title + indTpNm + career | 공백으로 합친 description; 상세 본문 아님 |
| region, career | region, career |
| minEdubg, maxEdubg | 비어 있지 않은 값을 ` ~ `로 연결한 education |
| salTpNm, sal, jobsCd | salary_type, salary, job_code |
| regDt, closeDt, wantedInfoUrl | registered_at, closing_at, url |

누락 태그는 빈 문자열. `root.findall('.//wanted')`를 사용하여 namespace가 있는 XML이나 다른 스키마는 대응하지 않는다. 원본 XML과 업종 필드는 별도 보관하지 않는다.

- 상세 URL 방문·상세 API 호출 없음. 필수·우대·업무 텍스트를 분리할 근거 없음.
- 요청당 `urlopen(..., timeout=30)`만 있음. 총 실행 시간 제한·백오프·재시도·부분 성공 결과 없음.
- HTTP/네트워크/UTF-8 decode/XML 파싱 예외는 전파. 파싱 가능한 오류 XML에 wanted가 없으면 정상 0건과 구별하지 못함(합성 오류 XML로 확인).
- display는 1–100, pages는 최소 1로 보정. UI pages는 최대 5지만 CLI·함수의 상한은 없음.
- 지정 페이지를 전부 요청. 총 건수 확인, 빈 페이지 조기 종료, 체크포인트 없음.
- API client 자체 중복 제거 없음. pipeline의 정제에서 posting_id 첫 행만 유지하고 DB에서 INSERT OR IGNORE.
- 마지막 키워드에서 실패해도 이전에 모은 결과가 아직 DB에 저장되지 않았으므로 해당 실행의 결과 전체를 저장하지 못함. 기존 DB는 남음.
- 인증키가 query string에 있으므로 향후 로그/오류 보고에 URL 전체를 남기지 않도록 해야 함. 현재 별도 로그 체계는 없음.

**권고**: 상세 수집은 필요하지만 먼저 공식 상세 API 명세·권한·본문 필드·제한을 확인해야 한다. 이 감사는 상세 endpoint나 필드명을 추측하지 않는다. 본문 수동 등록도 함께 제공하면 외부 API 제약과 무관하게 개인 사용을 시작할 수 있다.

## 7. 기술 추출

현재 taxonomy는 Python 소스의 `SKILL_ALIASES` 31개다. 아래는 전체 canonical 및 alias 목록이다(좌측 이름도 보유 기술 정규화에 사용).

| Canonical | 검색 alias |
|---|---|
| Python | python, 파이썬 |
| SQL | sql, 쿼리 |
| R / Java | r / java |
| Pandas / NumPy | pandas / numpy |
| Statistics | statistics, 통계 |
| A/B Test | a/b test, ab test, a-b test, ab테스트, a/b테스트 |
| Excel / Tableau | excel, 엑셀 / tableau, 태블로 |
| Power BI | power bi, powerbi |
| Looker / Plotly | looker / plotly |
| Spark / Airflow / Kafka | spark, 스파크 / airflow / kafka |
| Docker / Kubernetes | docker / kubernetes, k8s |
| AWS / GCP / Azure | aws, amazon web services / gcp, google cloud / azure |
| MySQL / PostgreSQL / MongoDB | mysql / postgresql, postgres / mongodb, mongo db |
| Machine Learning | machine learning, 머신러닝, ml |
| Deep Learning | deep learning, 딥러닝 |
| NLP | nlp, 자연어 |
| PyTorch / TensorFlow | pytorch, 파이토치 / tensorflow, 텐서플로 |
| Recommender System | recommender system, 추천시스템, 추천 시스템 |
| GA4 | ga4, google analytics 4 |

본문 추출은 입력을 공백으로 연결하고 소문자로 바꾼 뒤, import 때 컴파일한 `(?<![a-z0-9+#.])ALIAS(?![a-z0-9+#.])`로 검색한다. alias는 re.escape되며 기술별 한 번만 반환한다. 결과 순서는 taxonomy 삽입 순서다. 공백 수·하이픈·버전·Unicode 정규화는 하지 않는다.

보유 기술 `canonicalize_skills()`는 strip/lower 후 **전체 문자열 일치**다. 모르는 입력은 원래 표기를 유지한다. 같은 canonical만 중복 제거하므로 미등록 기술의 대소문자 차이는 남는다. 이 경로와 본문 검색 경로는 동작이 다르다.

확인한 경계 사례:

- `Python.` → 기술 없음: 마침표를 경계에서 막아 문장 끝 기술을 놓침.
- `JavaScript` → Java로 잡히지 않음: 유효한 보호 규칙.
- `R&D` → R: 언어가 아닌 문맥도 잡을 수 있음.
- `통계청` → Statistics: 한글은 경계 차단 문자에 포함되지 않음.
- `SQL과 파이썬`은 인식: 한글 조사와 붙은 기술명을 허용하는 장점도 있음.
- 부정 표현, 단순 언급, 필수/우대, 연차·숙련도 구분 없음. 이런 문맥 오인 규모는 실제 코퍼스에서 미측정.

요청된 backend 기술 22개 중 **7개 지원**: Java, MySQL, PostgreSQL, Kafka, Docker, Kubernetes, AWS.
미지원 **15개**: Spring, Spring Boot, Spring MVC, Spring Security, JPA, Hibernate, QueryDSL, Gradle, Maven, Redis, Linux, REST API, JWT, Git, CI/CD.

데이터/AI는 통계·분석·시각화·파이프라인·전통 ML 도구가 중심이다. scikit-learn, dbt, Snowflake, LLM 도구 등은 없다. 이들이 반드시 필요한지는 사용자 공고 코퍼스로 검증해야 한다.

**권고**: 범위를 넓히는 단계에서 JSON 같은 표준 라이브러리로 읽는 taxonomy 파일로 옮기고 stable skill ID, alias 중복·정합성 검사, 버전을 추가한다. 현재 regex의 동작을 먼저 회귀 테스트로 보존하고 경계 수정은 별도 변경으로 공개한다. Spring Boot를 Spring과 항상 이중 집계할지 같은 관계 정책도 명시해야 한다.

## 8. 직무 분류

출력은 데이터 분석가, 데이터 엔지니어, ML 엔지니어, BI 분석가 4종뿐이다. 우선순위는 다음과 같다.

1. 제목에 `bi` 또는 `kpi` 부분 문자열 → BI.
2. 제목에 `데이터 분석`, `분석가`, `분석 담당` → 데이터 분석가.
3. 제목+description에 `엔지니어`, `파이프라인`, `etl`, `플랫폼` 또는 Spark/Airflow/Kafka/Docker/Kubernetes 기술 → ML 관련 기술이 있으면 ML, 없으면 데이터 엔지니어.
4. 전체 텍스트에 `머신러닝`, `ml`, `ai`, `딥러닝`, `nlp` 또는 ML 기술 집합 → ML.
5. 전체 텍스트에 `bi`, `대시보드`, `dashboard`, `kpi` 또는 Tableau/Power BI/Looker → BI.
6. 나머지 모두 데이터 분석가. Unknown 없음.

ML 기술 집합은 Machine Learning, Deep Learning, NLP, PyTorch, TensorFlow다. 직종 코드(job_code)는 사용하지 않는다. 경계 없는 부분 문자열 규칙 때문에 `mobile developer`가 BI, `retail assistant`가 ML로 분류됨을 확인했다. `Backend Engineer`, `Frontend Developer`, `DevOps Engineer`는 기본 데이터 분석가, `백엔드 엔지니어`는 데이터 엔지니어다. 앞선 제목 분석가 규칙은 ML 본문보다 우선하므로 복합 공고도 하나로 강제된다.

**권고**: stable role ID와 표시명을 분리하고 Backend, Frontend, Full-stack, Data Analyst, Data Engineer, ML/AI, DevOps/Cloud 및 Unknown을 지원한다. BI는 기존 값과 호환되는 하위 분류 또는 독립 값으로 유지·매핑한다. 명시적 제목 → 본문 근거 → 보수적 기술 보조 → Unknown 순서 및 모호성 근거를 테스트로 고정한다. Docker 하나로 직무를 결정하지 않는다. ML 모델은 지금 필요하지 않다.

## 9. 현재 추천 계산의 정확한 의미

입력: target_role, owned_skills, analysis의 role_skill_counts/skill_counts, limit(기본 8, UI 6, CLI 5).

```text
counts = 해당 직무 Counter가 존재하고 비어 있지 않으면 그 Counter,
         아니면 전체 skill_counts
score(skill) = counts[skill] + foundation_bonus(skill)
foundation_bonus = 직무 foundation 목록 앞에서부터 5, 4, 3, 2, 1
```

| 직무 | 앞에서부터 +5, +4, +3, +2, +1 |
|---|---|
| 데이터 분석가 | SQL, Python, Statistics, Pandas, Tableau |
| BI 분석가 | SQL, Power BI, Tableau, Excel, Looker |
| 데이터 엔지니어 | SQL, Python, Spark, Airflow, AWS |
| ML 엔지니어 | Python, Machine Learning, PyTorch, Deep Learning, SQL |

foundation을 역순으로 순회하며 enumerate(1)의 값을 더한다. 공고에 전혀 없는 foundation도 후보로 추가된다. canonicalized 보유 기술을 제외하고 Counter.most_common 순으로 limit개를 반환한다. 동점은 Counter 삽입 순서 영향이며 의미 있는 우선순위 규칙이 아니다. 유효 직무에서 `limit=0`도 한 개가 반환되는 것을 확인했다(추가 후 종료 검사).

예: 샘플 데이터 분석가 Python 등장 5건 + 가산 4 = 9. 이 수치는 백분율·합격 확률·공고별 적합도가 아니다. 데이터가 많아질수록 빈도의 상대적 영향이 커진다. 기반 기술은 고정된 기초역량 문구, 나머지는 목표 직무 빈도 문구만 보여준다. 전체 빈도로 fallback해도 목표 직무 문구이므로 근거가 부정확할 수 있다. 분모, 실제 빈도, 가산점, fallback 여부는 UI에서 구분되지 않는다. 빈 데이터에도 기초 기술을 추천할 수 있다.

현재 개인화는 목표 직무와 보유 기술 제외뿐이다. 숙련도, 필수·우대, 지역·연차·급여 제약, 시계열 변화, 학습 비용은 사용하지 않는다. 점수 재설계 전 현재 계산을 정확히 고정하는 테스트가 필요하다.

## 10. SQLite와 데이터 정합성

| 테이블 | 컬럼·제약 | 읽기/쓰기 |
|---|---|---|
| job_postings | posting_id TEXT PK; source/created_at NOT NULL; company, title, description, region, career, education, salary_type, salary, job_code, registered_at, closing_at, url은 TEXT | INSERT OR IGNORE; 전체 SELECT, registered_at DESC 및 posting_id DESC; COUNT |
| posting_skills | posting_id, skill 모두 TEXT NOT NULL; 복합 PK(posting_id, skill) | INSERT OR IGNORE만; 분석에서 조회하지 않음 |

FK는 선언되지 않았다. 추가 인덱스·스키마 버전·마이그레이션·업데이트·삭제·검색·페이지 조회는 없다. source를 포함하지 않은 ID는 다른 공급자와 충돌한다. 원시 SQLite TEXT PK의 비-null 보장을 명시하지 않았고 저장 함수는 ID를 검증하지 않는다(일반 pipeline은 빈 ID를 사전에 제거).

`created_at`은 저장 호출당 한 번 만든 로컬 naive datetime, 초 정밀도다. 등록일/마감일은 원본 문자열이고 정렬도 문자열 순서다. 관측일, 최종 확인일, 원문 버전, 마감 상태, 추출 버전이 없다. schema 보장 함수는 read/count에도 DDL과 commit을 실행한다. `connect()`가 폴더를 만들고 연결한다. 성공 시 최종 commit, pipeline의 finally에서 연결을 닫지만 저장 함수 자체의 명시적 rollback 경계는 없다.

**재현된 불일치**: 같은 ID의 제목 Python 저장 후 제목 Java 저장 → 반환 신규 수 1, 0; 공고 제목은 Python 유지, posting_skills에는 Python과 Java 둘 다 존재. UI는 저장된 제목을 재추출하므로 저장된 기술 테이블과 다른 분석을 한다. 재수집이 최신화가 되지 않으며 기술은 누적된다.

향후 필요한 저장 정보(이번 Phase에서는 생성하지 않음):

| 기능 | 필요한 식별·관계·데이터 |
|---|---|
| 프로필 | 단일 로컬 profile ID, 수정 시각·revision, 경험·선호·제약 |
| 보유 기술·목표 직무 | profile→skill, profile→role, stable taxonomy ID, 숙련도는 정의 후 도입 |
| 공고 식별 | 내부 ID와 UNIQUE(source, external_id); 기존 ID 참조 이관 |
| 북마크 | profile→posting UNIQUE, 저장일 |
| 지원 현황·노트 | application→posting/profile, 단계·수정일; 노트·단계 이력 |
| 매칭 | posting snapshot/profile revision/rule version, 근거·일치·누락·unknown·계산 상세 |
| 공고 스냅샷 | posting→snapshot, 원본/정규화 텍스트·content hash·관측 시각·수집 실행 |
| 수요 이력 | 수집 범위·기간·출처·role별 유효 공고 분모 및 skill별 분자, taxonomy version |

시계열 집계 테이블은 우선 snapshot에서 계산하고 필요가 생길 때 materialize한다. 등록일별 현재 공고 집계를 시장 성장으로 부르면 안 된다. 비교 가능한 수집 범위와 반복 관측이 먼저 필요하다.

## 11. 데이터 품질과 실제 사용 가능성

| 항목 | 현재 보유 정보 | 적합도 판단에 충분한가 |
|---|---|---|
| 필수/우대 | 별도 필드·섹션 없음, 일부 샘플에 우대라는 말만 있음 | 아니오 |
| 업무 | 실제 수집은 제목+업종+경력 | 아니오 |
| 경력 | 원본 career 문자열을 신입/경력/무관/기타/미상으로 축약 | 연차·혼합 조건 소실. 신입/경력→신입, 경력무관→경력 확인 |
| 학력 | min/max 텍스트 연결, 정규화 없음 | 표시용 일부 정보만 가능 |
| 지역 | 목록 region을 넓은 지역으로 축약 | 상세 위치·재택·통근 조건 판단 불가 |
| 고용형태 | 필드 없음 | 아니오 |
| 급여 | 유형과 원문 문자열 | 범위·단위·협의 여부를 수치 비교할 수 없음 |
| 기술 | 빈약한 description에서 31개 규칙 검색 | 요구 수준·필수 여부·미검출과 미요구 구분 불가 |

지역은 alias 포함 검사 순서에 의존한다. 예컨대 `광주`라는 단독 입력은 광주광역시로 취급되어 상세 지역 없이는 동명이인 지역을 구별하지 못한다. clean_posting은 추가 필드와 원본 상세 지역·경력을 버린다. 결측을 빈 문자열로 바꾸므로 미수집/원문 결측/파싱 실패 원인도 구분하지 못한다.

샘플과 실데이터는 같은 DB에 저장할 수 있고 source 필터가 없다. DB에 샘플만 있어도 UI 데이터 라벨은 DB다. 샘플은 모든 마감일이 2026년 6–7월이며 만료 필터 없이 계속 분석된다. 검색 키워드 자체도 데이터 직군 중심이라 관측 모집단을 전체 개발자 시장으로 일반화할 수 없다.

**제품상의 가장 큰 공백**: 공고별 비교, 본문 수동 등록, 지속 프로필, 북마크, 지원 상태, 상세 링크 접근, 기간 분석 모두 없다. 지금은 유용한 로컬 빈도 데모지만 일상적인 지원 의사결정 도구는 아니다.

## 12. 테스트와 회귀 위험

현재 테스트 4개:

- `test_extract_skills`: 긍정 사례 4개 포함 여부만 확인하는 unit test.
- `test_canonicalize_skills`: alias와 중복 제거 1개 사례의 unit test.
- `test_recommend_skills`: 샘플 전체 흐름을 사용하는 작은 in-process integration test; SQL 제외/Python 포함만 검증.
- `test_save_and_load_postings`: tempfile SQLite integration test; 저장 수·조회 수·COUNT만 검증. 값·순서·기술 행은 검증하지 않음.

외부 네트워크·API 키·UI 의존성 없이 실행 가능하다. 커버리지 도구를 실행하지 않았으므로 수치 커버리지는 주장하지 않는다.

구조 변경 전 우선 보호할 계약:

1. 샘플 12건 전체 분석·직무/기술 Counter, 추천 점수·동점 순서·fallback·빈 입력·limit.
2. 추출 경계(문장부호, 한글 조사, Java/JavaScript, R&D), canonicalization 미등록값.
3. 직무 규칙 우선순위·unknown 현행 fallback 및 오분류 재현 사례. 현행 특성 테스트와 의도적 수정의 새 기대값을 분리.
4. 정제의 빈 필드/ID, source 충돌, 첫 행 유지, 경력·지역 축약.
5. SQLite 모든 필드 round-trip, 재저장, 기술 불일치, 정렬, 실패 transaction, schema 호환.
6. 합성 XML 성공/결측/오류/잘못된 XML; mocked urlopen으로 timeout·파라미터·pagination·실패 전파.
7. pipeline 임시 DB·수집 mock으로 sample/empty DB/API 흐름·부분 실패·연결 종료.
8. config 환경 우선순위·경로·1회 로딩(상태 격리); 설치 후 Streamlit sample/DB 모드·수집 실패 표시 smoke test.

## 13. 결합도, 중복 지식, 암묵적 모델

- 필드 목록이 normalizer, Work24 mapper, sample, storage INSERT/SELECT/keys, UI에 반복된다. 타입은 dict이므로 누락 필드가 런타임까지 드러나지 않는다.
- 분석 dict은 postings 및 5개 Counter 집합의 암묵적 계약이다. UI는 직접 key 접근; recommendation은 누락 key를 조용히 fallback한다.
- role label이 analyzer와 recommender의 foundation key에 중복된다. UI는 analyzer의 목록에 의존한다.
- storage가 domain extractor를 호출하고 analyzer도 다시 호출한다. persisted skill의 의미·버전이 없다.
- pipeline의 두 수집 함수에 루프 중복. 전역 config 사용으로 임시 경로·가짜 collector 주입이 불편하지만 현재 규모에서 대형 DI framework는 불필요하다.
- domain 자체는 Streamlit을 import하지 않는다. 문제는 UI/domain 완전 혼재가 아니라 결과 계약·오케스트레이션 일부의 경계다.

| 현재/미래 entity | 현재 표현 | explicit model의 가치 |
|---|---|---|
| JobPosting | raw/clean/enriched dict가 동일 이름으로 이동 | source ID·원문·정규화·결측 계약 명확화 |
| Skill | canonical 문자열과 alias dict | stable ID, version, 계층·alias 충돌 검증 |
| AnalysisResult | Counter를 담은 dict | 소스·분모·기간·데이터 품질을 함께 반환 |
| SkillRecommendation | skill/score/reason dict | 빈도·가산점·fallback 분리 |
| UserProfile/UserSkill | UI 문자열만, entity 없음 | 저장·변경 revision·정규화 재사용 |
| JobRequirement | 없음 | required/preferred/unspecified, 원문 근거·unknown |
| JobMatchResult | 없음 | 일치·누락·판단불가·제약·계산 설명 |
| SavedJob/Application | 없음 | 사용자-공고 관계, 상태·노트·이력 |
| SkillDemandSnapshot | 없음 | 기간/모집단/분모/분자·수집 정책 구분 |

권고는 작은 dataclass부터 시작하는 것이다. 존재하지 않는 모든 entity를 Phase 1에 만들 필요는 없다.

## 14. 유지할 강점과 실제 우선순위

**유지**: local-first, SQLite, Streamlit, src 패키지 구조, 표준 라이브러리 기반 핵심 실행, 순수 추출/분석/추천 함수, 별도 Work24 모듈, 재현 가능한 샘플, CLI, 환경변수 기반 키 구성, tempfile 테스트, 연결 finally 종료, parameterized SQL.

**지금 필요**: 회귀 기준 보강, 현재 점수 의미 문서화, source ID·업데이트·추출 결과 일관성 정책 결정, 환경/UI 검증 기반 확보. 코드 수정은 다음 Phase 승인 후.

**곧 유용**: backend 포함 taxonomy/직무 및 Unknown, 수동 본문 등록·상세 수집, 원문·관측 보존, 프로필·설명 가능한 공고 비교, URL·북마크·지원 관리.

**나중 선택**: 충분한 반복 수집 이후 수요 변화/학습 우선순위 결합, 스케줄러, 다른 공급자, 더 복잡한 통계 또는 ML(라벨·평가 근거가 있을 때).

**현재 불필요**: FastAPI+React 전환, PostgreSQL 교체, microservices, 범용 repository/DI framework, 모델 기반 불투명 점수, 근거 없는 합격확률, 추천을 위한 vector DB.

기존 문서와 차이: 요구사항의 날짜·급여 표준화, API 오류 fallback은 구현되지 않았다. 분석 결과 전체가 저장되는 것도 아니다(공고와 추출 기술만 저장). 배포 문서의 DB/웹스택 전환은 필요 근거 없는 기존 구상이며 V2의 전제가 아니다. Streamlit Secrets 직접 읽기는 코드에 없고 배포 환경에서 환경변수로 전달되는지는 이번 감사에서 검증하지 않았다. `.env` 수정 후 브라우저 새로고침만으로 갱신된다는 안내는 1회 로딩 구현과 맞지 않을 수 있다.

## 15. 검증 기록

| 명령/검증 | 결과 |
|---|---|
| `git ls-files`, 전체 파일 읽기, `git log -1 --format='%h %s'` | 전체 30개 확인, 기준 커밋 기록 |
| `git status --short` (시작) | 변경 없음 |
| `python --version` | Python 3.14.5 |
| `python -B -m unittest discover -s tests -v` | 4 tests, OK |
| `python -B scripts/run_demo.py` | exit 0, 12건·직무 분포·추천 확인 |
| `python -B -` 읽기 전용 probe | 메모리 DB 불일치·분류·추출·합성 XML·limit 경계 재현 |
| `importlib.util.find_spec` | streamlit/pandas/plotly 없음 |
| `git diff --check` | 기존 추적 파일 기준 오류 없음; 신규 문서는 별도 검사 |
| 문서 검증용 `python -B -` | 신규 3개 UTF-8·공백·코드 fence·상대 링크 정상, 변경 경로가 요청 문서 3개뿐임을 확인 |

PowerShell의 초기 출력에서 한국어 인코딩이 깨졌고, stdin probe의 한글 리터럴도 손상되었다. 해당 한글 결과는 증거로 사용하지 않고 Unicode escape 입력과 ASCII JSON 출력으로 재검증했다. `rg`가 설치되어 있지 않아 `git ls-files`와 PowerShell 파일 조회로 대체했다. CLI 자체 성공과 출력 인코딩 문제를 구분한다.

테스트의 DB는 임시 디렉터리에, 추가 probe의 DB는 메모리에만 생성했다. 기본 DB 생성, 수집·seed/setup 스크립트 실행, 의존성 설치, 네트워크 호출은 하지 않았다. UI와 실 API의 성공을 주장하지 않는다.
