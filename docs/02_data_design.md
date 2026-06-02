# 데이터 설계

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
