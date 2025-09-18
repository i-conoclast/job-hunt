# 🎯 Job Hunt - Recruitment Operations System

**"많이·빠르게·정확하게" 지원하는 채용 운영 시스템**

체계적인 채용 자동화 파이프라인으로 지원 효율성과 성공률을 극대화합니다.

## 🏗️ 시스템 아키텍처

```
[소스 수집] → [표준화] → [점수화] → [문서생성] → [추적관리]
     ↓           ↓         ↓         ↓         ↓
  자동수집    정규화DB   우선순위   원클릭생성  단계별관리
```

### 핵심 흐름 (5단계)

1. **Intake (자동 수집)**: Wanted/사람인/LinkedIn/회사채용 자동 수집
2. **Normalize (표준화)**: 비교·점수화가 쉬운 데이터 형태로 변환
3. **Rank (점수화)**: 역량 매칭 기반 우선순위 자동 결정
4. **Generate (문서 생성)**: 이력서/자기소개서/이메일 원클릭 생성
5. **Track (추적 관리)**: 지원 단계별 상태 관리 및 팔로업

## 📊 프로젝트 구조

```
job-hunt/
├── src/
│   ├── core/                    # 핵심 로직
│   │   ├── job_normalizer.py    # 채용공고 표준화
│   │   ├── job_scorer.py        # 점수화/우선순위
│   │   └── application_generator.py  # 지원서류 생성
│   ├── scrapers/                # 데이터 수집
│   ├── services/                # 외부 서비스 연동
│   └── utils/                   # 유틸리티
├── data/
│   ├── raw_jd/                  # 원본 채용공고
│   └── normalized/              # 표준화된 데이터
├── templates/                   # 문서 템플릿
│   ├── resume/                  # 이력서 템플릿
│   ├── cover_letter/            # 자기소개서 템플릿
│   └── emails/                  # 이메일 템플릿
├── snippets/                    # 경험 스니펫 라이브러리
├── config/                      # 설정 파일
├── scripts/                     # CLI 도구
└── out/jobkits/                 # 생성된 지원서류
```

## ⚡ 빠른 시작

### 1. 환경 설정
```bash
# 의존성 설치
poetry install

# 설정 파일 확인
ls config/
```

### 2. 채용공고 수집
```bash
# 여러 소스에서 AI/ML 관련 채용공고 수집
poetry run python scripts/jobctl.py collect -s wanted -s saramin -k "AI,ML,RAG,LLM" -l 50

# 결과: data/raw_jd/jobs_20250918_1234.json
```

### 3. 데이터 표준화
```bash
# 수집된 데이터를 표준 형태로 변환
poetry run python scripts/jobctl.py normalize data/raw_jd/jobs_20250918_1234.json

# 결과: data/normalized/jobs_normalized_20250918_1234.json
```

### 4. 점수화 및 우선순위 지정
```bash
# 사용자 프로필 기반 점수 계산
poetry run python scripts/jobctl.py score data/normalized/jobs_normalized_20250918_1234.json

# 결과: data/normalized/jobs_scored_20250918_1234.json
```

### 5. 일일 트리아지 (우선순위 검토)
```bash
# 오늘 검토할 상위 10개 채용공고
poetry run python scripts/jobctl.py triage data/normalized/jobs_scored_20250918_1234.json --top 10
```

### 6. 지원서류 생성
```bash
# 특정 채용공고에 대한 맞춤 지원서류 생성
poetry run python scripts/jobctl.py generate --job-id WANTED_EXAMPLE_AI_123456 --resume ko_rag --cover short

# 결과: out/jobkits/WANTED_EXAMPLE_AI_123456/
```

## 🎯 주요 기능

### 자동 수집 (Intake)
- **다중 소스**: Wanted, 사람인, 링크드인 동시 수집
- **키워드 필터**: "LLM", "RAG", "AI 엔지니어" 등 저장 검색
- **중복 제거**: URL 기반 자동 중복 제거

### 지능형 표준화 (Normalize)
- **통합 스키마**: 회사/역할/기술스택/요구사항 표준화
- **기술 태그 매핑**: 동의어 처리 (머신러닝 ↔ ML ↔ 기계학습)
- **레드플래그 탐지**: 야근/강제회식 등 자동 탐지

### 스마트 점수화 (Rank)
```yaml
# 점수 구성 (총 100점)
핵심역량매칭: 60점    # 필수기술 매칭율
시니어리티적합: 10점   # 경력수준 적합도
도메인적합: 10점      # 업계 경험 매칭
근무형태: 8점        # 리모트/하이브리드 선호
신규성: 5점          # 포스팅 최신성
언어요건: 7점        # 한/영 소통 역량
```

### 원클릭 문서 생성 (Generate)
- **경험 스니펫 라이브러리**: 재사용 가능한 프로젝트 경험
- **동적 템플릿**: Jinja2 기반 회사/역할 맞춤 생성
- **다양한 포맷**: 국문/영문 이력서, 짧은/긴 자기소개서

## 📈 운영 리듬

### 일일 루틴 (30-45분)
- **오전 10:00**: Today's Triage (신규 공고 검토 → Shortlist 선정)
- **오후 2:00-4:00**: 지원 작업 (서류 생성/품질 점검/제출)

### 주간 회고 (30분)
- **금요일 4:00**: 지표 리뷰 & 가중치 조정
- **화/목 15분**: 팔로업 메일 발송

## 🔧 설정 파일

### config/scoring.yml
```yaml
# 사용자 프로필 기반 점수 가중치
weights:
  must_match: 60      # 핵심 기술 매칭
  seniority: 10       # 경력 레벨 적합
  domain: 10          # 도메인 경험
  work_type: 8        # 근무 형태
  recency: 5          # 최신성
  language: 7         # 언어 요건

user_profile:
  required_skills: ["python", "llm", "rag", "machine learning"]
  seniority_level: "mid"
  work_type_preference: "hybrid"
```

### snippets/experience_snippets.yml
```yaml
- id: taxlaw_rag
  title: "NTS Tax-Law RAG Callbot"
  one_liner_ko: "법령 RAG로 근거제공률 40% 향상"
  impact_metrics: ["근거 제공률 +40%", "검증 통과율 95%"]
  tags: ["LLM", "RAG", "GraphDB", "LangChain"]
  bullets_ko:
    - "AGE(GraphDB)로 법령 관계 그래프 구축"
    - "LangChain 최적화로 응답 시간 개선"
```

## 📊 성과 지표

### 타겟 KPI
- **지원 수**: 주 10-15건
- **응답률**: 25% (업계 평균 5% 대비)
- **시간 절약**: 주 10시간 (수동 대비)

### 추적 지표
- 소스별 전환율 (Wanted vs 사람인 vs 직접지원)
- 템플릿별 성과 (이력서 v1 vs v2)
- 스테이지별 체류 시간

## 🎯 MVP 체크리스트 (7단계)

- [x] **Notion/Airtable 스키마** 설계
- [x] **경험 스니펫 라이브러리** 구축
- [x] **이력서/자기소개서 템플릿** 준비
- [x] **점수화 규칙** 구현
- [x] **CLI 도구** (jobctl.py) 개발
- [ ] **자동 수집** 파이프라인 연동
- [ ] **팔로업 SLA** 설정

## 🚀 다음 단계

### Phase 1: MVP 완성
- [ ] Notion API 연동으로 실제 DB 구축
- [ ] Zapier/Make 자동화 설정
- [ ] 일일 트리아지 대시보드

### Phase 2: 고도화
- [ ] LLM 기반 자동 JD 파싱
- [ ] 이메일 자동 발송 (팔로업)
- [ ] A/B 테스트 프레임워크

### Phase 3: 확장
- [ ] 네트워킹 자동화 (LinkedIn)
- [ ] 면접 준비 자료 생성
- [ ] 레퍼런스 관리 시스템

---

**목표**: "사람이 매일 뒤지는 행위 제거"로 볼륨 확장의 핵심 달성
**Tech Stack**: Python 3.11+ • Poetry • Jinja2 • PyYAML • Click
**Status**: MVP Core 완성 ✅ | 자동화 연동 진행중 🚧