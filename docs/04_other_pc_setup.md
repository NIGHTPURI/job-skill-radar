# 다른 PC에서 실행하기

## 가장 추천하는 방식

GitHub 저장소에 올린 뒤 다른 PC에서 내려받아 실행합니다. 압축 파일로 옮겨도 되지만, GitHub를 쓰면 포트폴리오 제출과 배포까지 이어가기 쉽습니다.

## 준비물

- Python 3.10 이상
- Git
- 인터넷 연결
- 선택 사항: 고용24 Open API 인증키

## 1. 프로젝트 받기

GitHub를 사용할 경우:

```powershell
git clone 저장소_URL
cd 저장소_폴더
```

압축 파일로 옮길 경우:

1. 현재 프로젝트 폴더를 압축한다.
2. 다른 PC에서 압축을 푼다.
3. 압축을 푼 폴더에서 PowerShell을 연다.

다른 PC로 옮길 때 `.venv`, `work`, `__pycache__` 폴더는 옮길 필요가 없습니다.

## 2. 실행환경 만들기

```powershell
.\scripts\setup_project.ps1
```

PowerShell 실행 정책 때문에 막히면 다음 명령을 사용합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_project.ps1
```

## 3. 대시보드 실행

```powershell
.\scripts\start_dashboard.ps1
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:8501
```

## 4. 실제 고용24 데이터 수집

프로젝트 루트에 `.env` 파일을 만들고 인증키를 넣습니다.

```env
WORK24_AUTH_KEY=발급받은_인증키
JOB_RADAR_DB_PATH=data/job_skill_radar.sqlite
```

대시보드를 새로고침하면 왼쪽 사이드바의 API 키 상태가 `설정됨`으로 바뀝니다.

## 자주 생기는 문제

### python 명령을 찾을 수 없음

Python을 설치하고, 설치 과정에서 `Add Python to PATH`를 선택합니다.

### 스크립트 실행이 막힘

다음 명령을 사용합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_project.ps1
```

### 화면은 뜨는데 실제 수집 버튼이 비활성화됨

`.env` 파일에 `WORK24_AUTH_KEY`가 없거나 값이 비어 있는 상태입니다.
