# Korean STT

동영상/오디오 파일에서 한국어 자막(SRT)을 자동 생성하는 데스크톱 앱.

![Dashboard](https://img.shields.io/badge/UI-Dashboard-blue) ![Python](https://img.shields.io/badge/Python-3.11+-yellow) ![License](https://img.shields.io/badge/License-MIT-green)

## 주요 기능

- 동영상/오디오 → 한국어 자막(SRT) 자동 생성
- 2가지 AI 모델 지원
  - **Moonshine** — CPU/GPU, 빠른 속도, 한국어 특화 (~105MB)
  - **Qwen3-ASR** — GPU 전용, 고품질, 다국어 지원 (~4.5GB)
- 앱 내에서 모델 원클릭 다운로드 (HuggingFace)
- 다크/라이트 테마 전환
- SRT 미리보기, 복사, 저장

## 스크린샷

> Figma 디자인: [Korean STT Desktop UI](https://www.figma.com/design/PRjwb3zDBRfruBL7dxHkdY)

## 요구사항

- Python 3.11+
- ffmpeg (PATH에 설치 또는 프로젝트 폴더에 배치)
- NVIDIA GPU + CUDA (Qwen3 모델 사용 시)

## 설치 및 실행

```bash
# 1. 클론
git clone https://github.com/<your-repo>/korean-stt.git
cd korean-stt

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 실행
python main.py
```

첫 실행 시 모델이 없으면 사이드바에 **다운로드** 버튼이 표시됩니다.
클릭하면 HuggingFace에서 자동으로 다운로드됩니다.

## 프로젝트 구조

```
├── ui/                     프론트엔드 (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── main.py                 엔트리포인트 (pywebview)
├── api.py                  JS ↔ Python API 브릿지
├── transcriber.py          모델 로딩 및 추론
├── audio_utils.py          ffmpeg 오디오 추출
├── subtitle_utils.py       SRT 생성
├── settings.py             경로 및 설정
├── model_downloader.py     HuggingFace 모델 다운로드
├── requirements.txt        Python 의존성
└── tests/                  테스트
```

## 모델 수동 다운로드

앱 내 다운로드 대신 PowerShell 스크립트를 사용할 수도 있습니다:

```powershell
.\download_models.ps1
```

## 빌드 (Windows 인스톨러)

```powershell
.\build_windows.ps1
```

PyInstaller로 exe를 생성하고 Inno Setup으로 인스톨러를 만듭니다.
빌드 결과: `dist\installer\KoreanSTT_Setup_1.0.0.exe`

## 사용된 모델

| 모델 | HuggingFace | 크기 | 하드웨어 |
|------|------------|------|---------|
| Moonshine | [UsefulSensors/moonshine-tiny-ko](https://huggingface.co/UsefulSensors/moonshine-tiny-ko) | ~105 MB | CPU / GPU |
| Qwen3-ASR | [Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) | ~4.5 GB | GPU (CUDA) |

## License

MIT
