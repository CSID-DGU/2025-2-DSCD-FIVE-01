# LLM 기반 HS 코드 추천 시스템

> **목표**: 상품명/설명 같은 **텍스트 입력**만으로 HS 코드 **Top-N 후보**와 **설명 가능한 근거**를 구조화 JSON으로 제공합니다.  
> **핵심**: RAG 기반 검색 근거 + LLM 생성 + 사후 검증(코드 유효성·근거 일치·스키마 룰)로 **환각(할루시네이션) 최소화**.  
> **배제**: 세율/FTA, 이미지 입력·캡션 등 **이미지 관련 기능 일체 제외**.

---

## 1) 개요

- **프로젝트명**: LLM 기반 HS Code Recommendation (Text-only)  
- **과목**: 데이터사이언스 캡스톤디자인  
- **목표**: 자연어로 입력된 상품 정보(상품명·설명)를 바탕으로 **HS 코드 Top-N**과 **근거 텍스트**를 반환

### 주요 제공 기능
- 🔎 **Top-N HS 코드 추천** (LLM + RAG)
- 📚 **근거 텍스트 제공**: 검색된 규정/해설/사례의 관련 문단을 함께 제시
- 🧪 **사후 검증**: 코드 유효성(존재/자릿수/계층) + 근거-응답 일치도 + JSON 스키마 검사
- 🔁 **재생성 루프**: 검증 실패 사유를 피드백해 자동 재생성(최대 n회)

---

## 2) 시스템 아키텍처

```text
[입력(상품명·설명)]
         │
         ▼
  [전처리·정규화] ──▶ [임베딩] ──▶ [VectorDB 검색]
         │
         ▼
      [LLM 생성(JSON 스키마 강제)]
         │
         ├─ 검증① 코드 유효성(존재/형식/계층 규칙)
         ├─ 검증② 근거-응답 일치도(semantic entailment)
         └─ 검증③ 스키마/룰(JSON 키/타입/금지표현)
         ▼
      [재랭킹·재생성 루프]
         │
         ▼
      [최종 JSON 응답]
```

- **데이터 소스(예시)**: HS 코드 목록(국제 4·6자리/국내 10자리), 품목분류 해설, 공공 사례 등  
- **VectorDB**: Chroma 또는 FAISS (코사인 유사도 Top-K 검색)  
- **LLM**: JSON 스키마 고정 프롬프트, 근거 중심 생성

---

## 3) VectorDB 구축: 데이터 수집 → 정제 → 인덱싱 → 검색 

본 시스템은 **텍스트 전용** HS 코드 추천을 위해 규정/해설/사례/코드목록을 임베딩하여 **VectorDB**(Chroma 또는 FAISS)에 구축합니다.  
핵심은 **정제 일관성**, **계층형 메타데이터(류–호–소호–국내세분)**, **근거 텍스트 품질 관리**입니다.

### 3.1 사용 데이터


1) **HS 코드 목록** (`data/processed/hs_list.csv`)  
- 목적: **코드 유효성 대조**(존재/자릿수/계층 규칙)  
- 컬럼:
  - `hs_code_full` (str)  예: `"7323.93.0000"`
  - `chapter` (str)       예: `"73"`
  - `heading` (str)       예: `"7323"`
  - `subheading` (str)    예: `"7323.93"`
  - `national` (str)      예: `"7323.93.0000"`
  - `title_ko` (str)      국문 품목명
  - `title_en` (str)      영문 품목명
  - `notes` (str)         요약 설명(선택)

2) **품목분류 해설·규정·지침** (`data/processed/explanatory.parquet`)  
- 목적: **근거 텍스트** 제공  
- 컬럼:
  - `doc_id` (str)        문서 ID(출처 식별)
  - `section` (str)       장/절/항 등 구획 정보
  - `language` (str)      `"ko"` / `"en"`
  - `text` (str)          본문(정제된 문단)
  - `related_codes` (list[str])  연관 HS 코드(있으면 기록)
  - `source_name` (str)   출처명
  - `source_loc` (str)    페이지/조문 등 위치 정보

3) **사례/판례/질의응답 등** (`data/processed/cases.parquet`)  
- 목적: **현장 적용 근거 텍스트** 제공  
- 컬럼:
  - `case_id` (str)       사례 ID
  - `title` (str)         사례 제목
  - `facts` (str)         제품 특징/사실관계(정제)
  - `decision` (str)      분류 판단 요지(텍스트)
  - `language` (str)      `"ko"` / `"en"`
  - `related_codes` (list[str])
  - `source_name`, `source_loc`

### 3.2 전처리(정제) 규칙
- **문자 정규화**: 공백/개행 정리, 특수문자 통일, 한·영 괄호/따옴표 표준화  
- **중복 제거**: 동일 문단/동일 문서 구획의 중복 제거(hash 기반)  
- **언어 태깅**: `language` 필수(한국어/영어 혼재 시 검색 가중치 조절)  
- **불필요 구역 제거**: 저작권 고지, 머리말/목차/표지 등 검색에 불필요한 영역 제외  
- **용어 사전**: 동의어·약어 표준화(예: SUS304 ↔ 스테인리스강 304)  
- **코드 표기 통일**: `NNNN.NN.NNNN` 형태(마침표/자릿수 엄격)  
- **문단 분할**: 문장 경계 기반 분할 후 길이 기준으로 합치기(너무 짧은 문장 단독 금지)

### 3.3 임베딩 & 인덱싱
- **임베딩 모델**: `text-embedding-3-large`(권장) 또는 Sentence-Transformers 계열  
- **메타데이터 저장**(검색·재랭킹·설명 출력에 활용):
  - `doc_id | case_id`, `source_name`, `source_loc`
  - `language`
  - `related_codes`
  - `chapter/heading/subheading/national` (가능 시)  
- **저장소**:
  - **Chroma**: 간편, 메타데이터 쿼리 유용
  - **FAISS**: 속도/메모리 최적화(대규모에 적합)  
- **거리함수**: 코사인 유사도(권장)

```bash
# 인덱스 구축
python scripts/build_index.py \
  --input ./data/processed \
  --out ./data/index \
  --db chroma \
  --embedding_model text-embedding-3-large \
  --batch_size 128
```

### 3.4 검색 전략(텍스트 전용)
1. **하이브리드 질의 구성**  
   - 사용자 입력 정규화(불용어 제거, 단위/수치 표준화)  
   - **메타 필터**(예: `chapter:73`, `heading:7323`) + **의미 기반 질의**(임베딩) 결합
2. **계층 인지 검색**  
   - 상위 계층(류/호) 단서가 강하면 **후속 재검색**에서 해당 계층 가중
3. **Top-K 선택 & 다양성 보정**  
   - 문서/구획 다양성 확보(한 문서만 과다 노출 방지)
4. **후처리 재랭킹**  
   - 생성 단계에서 활용하기 쉬운 **핵심 근거 텍스트**를 우선 배치  
   - 메타데이터(관련 코드 일치, 언어 일치 등)로 가중치 조정


### 3.5 생성 단계로 전달하는 컨텍스트 형식
- **문단 본문**(정제된 텍스트)  
- **출처명·위치**(source_name, source_loc)  
- **연관 코드 목록**(related_codes)  
- **계층 메타데이터**(가능 시)

> 생성 프롬프트에는 “반드시 입력과 **전달된 근거 텍스트**에서 논리적으로 도출 가능한 코드만 추천하라”는 규칙을 포함합니다.

### 3.6 검증(Validation)과의 연계
- **코드 유효성 검사**: `hs_list.csv`와 대조하여 존재/자릿수/계층 일관성 확인  
- **근거-응답 일치성 점수화**: 생성 결과가 전달된 **근거 텍스트**와 모순되지 않는지 확인  
- **스키마/룰 검사**: 필수 키 존재, 타입/길이/금지 표현 점검  
- **자동 재시도 루프**: 실패 사유를 모델에 피드백하고 최대 N회 재생성

### 3.7 데이터 디렉터리 구조(예시)
```
data/
├─ raw/
│  ├─ hs_list_original.xlsx
│  ├─ explanatory_pdf/...
│  └─ cases_html/...
├─ processed/
│  ├─ hs_list.csv
│  ├─ explanatory.parquet
│  └─ cases.parquet
└─ index/
   ├─ chroma/...
   └─ faiss/...
```

### 3.8 품질 관리 체크리스트
- [ ] 문단 길이 300~1200자 준수  
- [ ] 중복 문단 제거(해시 기준)  
- [ ] 언어 태그 정확  
- [ ] 코드 표기 통일(`NNNN.NN.NNNN`)  
- [ ] 출처명/위치 누락 없음  
- [ ] 관련 코드 있는 경우 메타데이터 포함  
- [ ] 인덱스 빌드 로그에 에러/누락 없음

---

## 4) 설치 및 실행

### 4.1 요구사항
- Python 3.10+
- 인터넷 연결(LLM·임베딩 모델 사용 시)

### 4.2 의존성 설치
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4.3 환경 변수 설정
`.env.example`를 복사해 `.env`를 작성합니다.
```env
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large
VECTOR_DB=chroma                 # or faiss
INDEX_DIR=./data/index
CASE_DATA=./data/processed/cases.parquet
HS_LIST=./data/processed/hs_list.csv
TOP_N=3
```

### 4.4 데이터 정제 & 인덱스 구축
```bash
python scripts/prepare_data.py --raw ./data/raw --out ./data/processed
python scripts/build_index.py --input ./data/processed --out ./data/index --db chroma
```

### 4.5 API 서버 실행(FastAPI)
```bash
uvicorn src.api.server:app --reload --port 8080
```
- 문서: http://localhost:8080/docs

### 4.6 CLI 실행(예시)
```bash
python scripts/run_cli.py \
  --product_name "스테인리스 보온 텀블러 350ml" \
  --product_desc "진공 2중 구조, 손잡이 없음, 식품용"
```

---

## 5) 입력/출력(JSON 스키마)

### 5.1 요청(JSON)
```json
{
  "product_name": "string (optional)",
  "product_desc": "string (required)",
  "top_n": 3
}
```

### 5.2 응답(JSON) — **세율/FTA 및 이미지 관련 키 없음**
```json
{
  "candidates": [
    {
      "hs_code": "string",
      "title": "string",
      "hierarchy": {
        "chapter": "string",
        "heading": "string",
        "subheading": "string",
        "national": "string"
      },
      "evidence": [
        {
          "source_id": "string",
          "source_title": "string",
          "evidence_text": "string",
          "loc": "string"
        }
      ],
      "confidence": {
        "retrieval_score": 0.0,
        "entailment_score": 0.0
      }
    }
  ],
  "meta": {
    "top_n_requested": 3,
    "top_k_retrieval": 8,
    "latency_ms": 1234
  }
}
```

> **용어 정책**: “스니펫” 대신 `evidence_text`(근거 텍스트) 필드만 사용합니다.

---

## 6) 검증(Validation) 로직

1. **코드 유효성**  
   - 형식(숫자·구분점·자릿수)  
   - 존재 여부(공식 목록 대조)  
   - 계층 규칙(4→6→10자리 일관성)

2. **근거-응답 일치도**  
   - 검색된 **근거 텍스트** 대비 semantic entailment/정합성 점수 산출  
   - 임계치 미달 시 후보 제외 또는 재생성

3. **JSON 스키마 검사**  
   - 필수 키/타입/길이 제한/금지 표현(모호·추정 어휘) 검사

4. **재생성 루프**  
   - 실패 사유를 프롬프트 피드백 → 최대 N회까지 자동 재시도

---
