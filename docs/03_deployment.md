# 배포 계획

## 1단계: 로컬 실행

```powershell
python scripts/run_demo.py
```

## 2단계: 대시보드 실행

```powershell
python -m pip install -r requirements.txt
python scripts/seed_sample.py
streamlit run app.py
```

로컬 가상환경을 이미 만들었다면 `.\scripts\start_dashboard.ps1`로 실행할 수 있습니다.

## 3단계: GitHub 업로드

```powershell
git init
git add .
git commit -m "Initial job skill radar MVP"
```

## 4단계: Streamlit Community Cloud 배포

1. GitHub에 저장소를 올린다.
2. Streamlit Community Cloud에서 새 앱을 만든다.
3. `app.py`를 엔트리 파일로 지정한다.
4. Secrets에 `WORK24_AUTH_KEY`를 등록한다.
5. API 키가 없어도 샘플 데이터 화면이 먼저 표시되는지 확인한다.

## 5단계: 배포 후 점검

- 샘플 데이터 대시보드가 표시되는지 확인한다.
- API 키 등록 후 실제 데이터 수집이 되는지 확인한다.
- README의 실행 방법이 그대로 동작하는지 확인한다.

## 이후 확장

- PostgreSQL 저장소로 전환
- FastAPI 백엔드 분리
- React 프론트엔드 확장
- 주기적 수집 스케줄러 추가
- 직무 분류 모델 고도화
