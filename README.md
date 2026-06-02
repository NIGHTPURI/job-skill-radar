# Job Skill Radar

채용공고 데이터를 수집하고 분석해서 데이터 직무별 요구 역량을 보여주는 포트폴리오 프로젝트입니다.

## 목표

- 고용24/워크넷 채용공고 데이터를 수집한다.
- 데이터 직무 공고에서 기술스택을 추출한다.
- 직무, 경력, 지역별 채용 트렌드를 분석한다.
- 사용자의 보유 기술과 목표 직무를 바탕으로 학습 우선순위를 추천한다.
- Streamlit 대시보드로 배포한다.

## MVP 기능

- 샘플 데이터 기반 분석 데모
- 고용24 Open API 수집기
- 기술스택 추출
- 직무별 인기 기술 분석
- 사용자 보유 기술 기반 추천
- SQLite 저장
- Streamlit 대시보드

## 빠른 실행

현재 기본 실행 검증은 외부 패키지 없이 가능합니다.

```powershell
python scripts/run_demo.py
```

샘플 데이터를 DB에 저장하면 대시보드에서 실제 저장소 기반 흐름을 확인할 수 있습니다.

```powershell
python scripts/seed_sample.py
```

대시보드를 실행하려면 패키지를 설치합니다.

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

이 작업 폴더의 가상환경을 사용한다면 다음 명령으로 실행할 수 있습니다.

```powershell
.\scripts\start_dashboard.ps1
```

다른 PC에서 같은 환경을 만들 때는 아래 문서를 따릅니다.

- [다른 PC에서 실행하기](docs/04_other_pc_setup.md)

직무 분류 모델을 scikit-learn으로 고도화하는 단계에서는 ML 확장 패키지를 추가로 설치합니다.

```powershell
python -m pip install -r requirements-ml.txt
```

## 실제 API 수집

고용24 Open API 인증키를 발급받은 뒤 `.env` 또는 환경변수에 넣습니다.

```powershell
$env:WORK24_AUTH_KEY="발급받은_인증키"
python scripts/collect_work24.py --keyword "데이터 분석가" --keyword "데이터 엔지니어" --pages 3
```

## 폴더 구조

```text
.
├── app.py
├── docs/
├── scripts/
├── src/jobskillradar/
├── tests/
├── requirements.txt
└── .env.example
```

## 포트폴리오 설명 포인트

- 요구사항 분석부터 배포까지 전체 개발 생명주기를 경험했다.
- 외부 API 데이터를 수집하고, 정제 규칙을 직접 설계했다.
- 단순 빈도 분석을 넘어 직무별 역량 차이와 학습 추천으로 연결했다.
- API 키가 없는 환경에서도 샘플 데이터로 재현 가능한 데모를 만들었다.
