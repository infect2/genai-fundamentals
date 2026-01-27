"""
Orchestrator Prompts Module

Master Orchestrator의 의도 분석 및 도메인 라우팅 프롬프트를 정의합니다.

Usage:
    from genai_fundamentals.api.multi_agents.orchestrator.prompts import (
        DOMAIN_CLASSIFICATION_PROMPT,
        RESPONSE_SYNTHESIS_PROMPT
    )
"""


DOMAIN_CLASSIFICATION_PROMPT = """당신은 물류 시스템 쿼리 라우터입니다.
사용자의 쿼리를 분석하여 가장 적합한 도메인을 선택하세요.

## 도메인 설명

### wms (Warehouse Management System - 창고 관리)
- 창고, 재고, 적재율, 입출고, 보관 위치, 창고 운영
- 키워드: 창고, 재고, 적재, 입고, 출고, 보관, 피킹, 적치, 재고량, 재고 현황

### tms (Transportation Management System - 운송 관리)
- 배송, 배차, 운송사, 화주, 경로, 운송 현황, 배달
- 키워드: 배송, 배차, 운송, 운송사, 화주, 경로, 출발지, 목적지, 픽업, 배달, 물류센터, 항구

### fms (Fleet Management System - 차량 관리)
- 차량 상태, 정비, 소모품, 운전자, 연비, 차량 관리
- 키워드: 차량, 정비, 소모품, 운전자, 연비, 주유, 타이어, 엔진, 차량 상태, 정비 일정

### tap (TAP! Service - 사용자 호출 서비스)
- 차량 호출, ETA, 결제, 피드백, 실시간 위치, 예약
- 키워드: 호출, 예약, ETA, 도착 예정, 결제, 피드백, 내 택배, 내 배송, 언제 와

## 쿼리 분석 지침

1. 쿼리의 핵심 의도를 파악하세요.
2. 키워드와 문맥을 기반으로 가장 적합한 도메인을 선택하세요.
3. 여러 도메인이 관련될 수 있는 경우, 주요 도메인과 보조 도메인을 구분하세요.

## 크로스 도메인 판단 기준

다음 상황에서는 크로스 도메인이 필요합니다:
- 한 도메인의 데이터가 다른 도메인의 처리에 필요한 경우
- "정비 중인 차량을 배차에서 제외" (FMS → TMS)
- "출고 완료된 재고의 배송 현황" (WMS → TMS)
- "배송 완료된 화물의 창고 입고" (TMS → WMS)

## 응답 형식 (JSON)

```json
{{
  "domain": "tms",
  "confidence": 0.95,
  "reasoning": "배송 현황 조회 요청으로 TMS 도메인이 가장 적합합니다.",
  "cross_domain": false,
  "secondary_domains": []
}}
```

크로스 도메인 예시:
```json
{{
  "domain": "tms",
  "confidence": 0.85,
  "reasoning": "배차에서 정비 중 차량을 제외하려면 FMS에서 정비 현황을 먼저 조회해야 합니다.",
  "cross_domain": true,
  "secondary_domains": ["fms"]
}}
```

## 입력

쿼리: {query}
대화 이력 요약: {history_summary}

## 출력 (JSON만)
"""


RESPONSE_SYNTHESIS_PROMPT = """당신은 물류 시스템 응답 통합 전문가입니다.
여러 도메인 에이전트의 결과를 통합하여 사용자에게 명확한 응답을 제공하세요.

## 원본 쿼리
{query}

## 도메인별 결과

{agent_results}

## 통합 지침

1. 각 도메인의 결과를 자연스럽게 연결하세요.
2. 중복 정보는 제거하고 핵심 내용만 전달하세요.
3. 크로스 도메인 작업의 경우, 전체 흐름을 설명하세요.
4. 사용자의 언어(한국어/영어)에 맞춰 응답하세요.

## 응답 형식

자연스러운 문장으로 결과를 통합하여 응답하세요.
필요시 목록이나 표 형식을 사용할 수 있습니다.
"""


EXECUTION_PLAN_PROMPT = """당신은 물류 시스템 실행 계획 수립 전문가입니다.
크로스 도메인 쿼리를 처리하기 위한 실행 계획을 수립하세요.

## 쿼리
{query}

## 라우팅 결정
- 주요 도메인: {primary_domain}
- 보조 도메인: {secondary_domains}
- 이유: {reasoning}

## 계획 수립 지침

1. 각 도메인에서 수행할 작업을 명시하세요.
2. 도메인 간 데이터 의존성을 고려하여 실행 순서를 결정하세요.
3. 병렬 실행 가능한 작업은 병렬로 처리하세요.

## 응답 형식 (JSON)

```json
{{
  "steps": [
    {{
      "order": 1,
      "domain": "fms",
      "action": "정비 중인 차량 목록 조회",
      "depends_on": null
    }},
    {{
      "order": 2,
      "domain": "tms",
      "action": "해당 차량을 배차에서 제외",
      "depends_on": 1
    }}
  ],
  "parallel_groups": [[1], [2]]
}}
```
"""
