
# news_crawler_demo

간단한 뉴스 크롤러 데모 프로젝트입니다.  
각각의 코드는 뉴스 페이지에서 최근 5개의 기사를 찾습니다.  
뉴스에서의 본문 텍스트, 이미지, 첨부파일, 제목, 날짜 데이터를 추출하여 json 형식으로 저장합니다.

> ✅ Python: 3.13+  
> ✅ Package Manager: Poetry

---

## 1. pyenv 설치 (Python 버전 관리)

프로젝트는 Python 3.13 이상을 요구합니다. pyenv로 버전을 관리할 수 있습니다.

### macOS

```bash
# Homebrew로 설치 (Xcode Command Line Tools 필요)
brew install pyenv

# 셸 설정 (~/.zshrc 또는 ~/.bash_profile)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Python 3.13 설치
pyenv install 3.13
pyenv local 3.13   # 이 프로젝트에서 사용할 버전
```

### Linux (Ubuntu/Debian)

```bash
# 의존성 설치
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev \
  libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# pyenv 설치
curl https://pyenv.run | bash

# 셸 설정 (~/.bashrc 또는 ~/.zshrc)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Python 3.13 설치
pyenv install 3.13
pyenv local 3.13
```

### Windows

Windows는 **pyenv-win**을 사용합니다.

```powershell
# PowerShell (관리자 권한 권장)
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
& "./install-pyenv-win.ps1"
```

설치 후 PowerShell을 다시 열고:

```powershell
pyenv install 3.13.0
pyenv local 3.13.0
```

---

## 2. Poetry 설치 (패키지 관리)

### macOS / Linux

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Poetry 실행 파일 경로를 PATH에 추가 (필요 시):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Windows (PowerShell)

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

설치 후 `%APPDATA%\Python\Scripts` 가 PATH에 있는지 확인하고, 새 터미널에서 `poetry --version`으로 확인합니다.

### 설치 확인

```bash
poetry --version
```

---

## 3. 코드 실행 방법

### 3.1 프로젝트 디렉터리로 이동

```bash
cd news_crawler
```

### 3.2 가상환경 생성 및 의존성 설치

```bash
poetry install
```

### 3.3 Playwright 브라우저 설치 (최초 1회)

이 프로젝트는 Playwright로 브라우저를 사용합니다. Chromium 등 브라우저 바이너리를 한 번 설치해야 합니다.

```bash
poetry run playwright install chromium
```

전체 브라우저(Chromium, Firefox, WebKit)를 설치하려면:

```bash
poetry run playwright install
```

### 3.4 크롤러 스크립트 실행

Poetry 가상환경 안에서 Python 스크립트를 실행합니다.

```bash
# 예: 부산항만공사 뉴스 크롤러
poetry run python crawler_demo_busanpa.py
```

다른 크롤러 예시:

```bash
poetry run python crawler_demo_ulogistics.py
poetry run python crawler_demo_surff.py
poetry run python crawler_demo_shippingnews.py
poetry run python crawler_demo_sea.py
poetry run python crawler_demo_oceanpress.py
poetry run python crawler_demo_ksg.py
poetry run python crawler_demo_kotra.py
poetry run python crawler_demo_kita.py
poetry run python crawler_demo_iata.py
poetry run python crawler_demo_flexport.py
poetry run python crawler_demo_cello.py
poetry run python crawler_demo_cargonews.py
```

### 3.5 (선택) Poetry 셸에서 실행

가상환경을 활성화한 뒤 `python`만으로 실행할 수도 있습니다.

```bash
poetry shell
python crawler_demo_busanpa.py
exit
```

---

## 4. 실행 결과

각 스크립트는 해당 뉴스 사이트에서 최근 기사 5건을 수집해 **JSON 파일**로 저장합니다.  
파일명 및 저장 위치는 각 스크립트 내부에 정의되어 있습니다.

