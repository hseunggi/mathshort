## 📐 MathShort


Mathshort는 문제를 올리면 단계별 해설, 검산 포인트, 수식 렌더, 영상 생성까지 한 번에 처리합니다.

## ✨ 프로젝트 소개

MathShort는 수학 문제 풀이를 보고도 이해가 잘 되지 않는 Z세대 학생들을 위해 만들어진
AI 기반 자동 해설·영상 생성 서비스입니다.

수학 문제 이미지를 업로드하면,
최신 GPT-5.2 기반 추론 모델이 문제를 분석해 단계별 풀이와 검산 포인트를 생성하고,
이를 바탕으로 숏츠 스타일의 60초 세로 영상을 제작해 핵심만 빠르게 전달합니다.

## 🚀 MathShort 핵심 기능
🔹 AI 기반 문제 풀이 생성 (GPT-5.2)
- 수학 문제 이미지를 업로드하면 최신 GPT-5.2 기반 모델이 문제를 분석
- 단계별 풀이, 핵심 개념 요약, 검산 포인트를 구조화된 JSON 형태로 생성
- 단순 정답 제공이 아닌 이해 중심 설명 제공

🔹 Z세대 맞춤 숏츠 영상 자동 제작
- 생성된 풀이를 바탕으로 60초 세로형 숏폼 영상 자동 생성
- 인트로 → 단계별 설명 → 정답 정리 구조
- 음성 내레이션(TTS)과 수식 시각화를 결합한 학습 콘텐츠

🔹 인증 시스템
- 이메일 기반 회원가입 및 인증 코드 검증
- Google OAuth2 로그인 지원
- Spring Security 기반 세션 인증 구조
## 🛠 기술 스택

#### 📱 Client
| Part   | Tech                                                 |
| ------ | ---------------------------------------------------- |
| Web UI | HTML, CSS, JavaScript (Spring Boot Static Resources) |

#### 🖥 Backend & Infrastructure
| Part              | Tech                           |
| ----------------- | ------------------------------ |
| Main Server       | Spring Boot (Java 21)          |
| AI / Video Worker | Python                         |
| Queue / Messaging | Redis                          |
| Database          | MySQL                          |
| Authentication    | Spring Security, Google OAuth2 |
| Mail              | Spring Mail                    |
| API Docs          | Swagger (springdoc-openapi)    |
| Infra             | Docker Compose                 |

#### 🧠 AI & Video Pipeline
| Part                | Tech                       |
| ------------------- | -------------------------- |
| LLM / Vision        | OpenAI GPT-5.2             |
| Image Understanding | OpenAI Vision API          |
| TTS                 | OpenAI Text-to-Speech      |
| Formula Rendering   | matplotlib (LaTeX), Pillow |
| Video Processing    | ffmpeg                     |
| DB Sync             | SQLAlchemy + PyMySQL       |

#### 📦 Data & Storage
| Part               | Tech                                             |
| ------------------ | ------------------------------------------------ |
| File Storage       | Docker Volume (`/data/uploads`, `/data/outputs`) |
| Metadata Storage   | MySQL                                            |
| Job State Tracking | Redis Queue                                      |

## 🎬 AI 숏츠 생성 파이프라인 (AI Pipeline)
1. Input: 사용자가 수학 문제 이미지(PNG) 업로드
2. Job Create: Spring Boot가 Job 생성 후 MySQL에 메타데이터 저장, Redis Queue에 작업 등록
3. Problem Understanding (Vision): Python Worker가 이미지를 읽고 문제를 텍스트로 추출/해석 (OpenAI Vision)
4. Solution Planning (LLM): GPT-5.2 기반으로 다음을 JSON구조로 생성
    - 문제 유형(concept)
    - 단계별 풀이(steps)
    - 검산 포인트(check)
    - 최종 답(finalAnswer)

5. Formula Rendering: 단계별 LaTeX 수식을 이미지로 렌더링 (matplotlib / Pillow, 환경에 따라 폴백 지원)
6. Narration (TTS): 단계별 설명 문장을 기반으로 음성 생성 (OpenAI TTS)
7. Scene Composition: 인트로 → 단계별 풀이 → 정답 요약 순서로 프레임/씬 구성 (세로 9:16)
8. Rendering: ffmpeg로 이미지(프레임) + 음성(TTS) + 자막/수식 합성하여 최종 60초 MP4 생성
9. Result Save: 생성된 영상 경로 및 상태를 MySQL에 업데이트하고, 사용자는 웹에서 결과를 다시보기

## 시스템구조
<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/001a9520-0894-4d51-84e7-f17887771cdc" />


## 결과화면
<img width="800" height="450" alt="스크린샷 2026-02-09 190751" src="https://github.com/user-attachments/assets/9d064056-b3d6-455d-a734-64762bac2c9c" />
<img width="800" height="450" alt="스크린샷 2026-02-09 190834" src="https://github.com/user-attachments/assets/aa9046d3-a7a8-4dcc-baba-86cf0dcbbe4c" />
<img width="800" height="450" alt="스크린샷 2026-02-09 190808" src="https://github.com/user-attachments/assets/5d60308d-bcc4-4d15-ad34-8985944d88f5" />
<img width="400" height="800" alt="solve" src="https://github.com/user-attachments/assets/0900f9ec-9b58-42dd-a9b8-4f9ddc6e4e86" />
<img width="353" height="600" alt="스크린샷 2026-02-09 195612" src="https://github.com/user-attachments/assets/64571c13-0919-4823-9c3d-0a3bc8a33884" />

## 웹 배포
http://mathshort.duckdns.org/
 
