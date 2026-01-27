# Multi-Agent Architecture Plan

이 문서는 Capora AI Ontology Bot의 현재 Single Agent 아키텍처와 제안된 Multi-Agent 아키텍처를 설명합니다.

---

## 1. ReAct Agent Loop (LangGraph Flow)

LangGraph 기반 ReAct Agent의 실행 흐름입니다.

```
                            [START]
                               │
                               ▼
                   ┌──────────────────────┐
                   │   REASON NODE        │
                   │  (LLM Invocation)    │
                   │                      │
                   │ Receives:            │
                   │ • System Prompt      │
                   │ • Message History    │
                   │ • Tool Definitions   │
                   │   (JSON Schema)      │
                   │                      │
                   │ Outputs:             │
                   │ • tool_calls OR      │
                   │ • final answer       │
                   └──────────────────────┘
                               │
                               ▼
                   ┌──────────────────────────────┐
                   │  should_continue?            │
                   │  (Conditional Edge)          │
                   └──────────────────────────────┘
                       /                      \
                  YES /                        \ NO
                     /                          \
                    ▼                            ▼
      ┌──────────────────────┐      ┌──────────────────────┐
      │   TOOLS NODE         │      │   END                │
      │  (Execute Selected   │      │ (Return Final Answer)│
      │   Tool Calls)        │      └──────────────────────┘
      │                      │
      │ cypher_query         │
      │ vector_search        │
      │ hybrid_search        │
      │ get_schema           │
      │ user_memory          │
      └──────────────────────┘
                │
                ▼
      ┌──────────────────────┐
      │ UPDATE_RESULTS NODE  │
      │ (Record for Logging) │
      └──────────────────────┘
                │
                └─────────────────┐
                                  │ (Loop back)
                                  ▼
                          [REASON NODE]
```

---

## 2. Multi-Protocol Architecture

3가지 프로토콜(REST, MCP, A2A)을 통해 클라이언트 인터페이스를 제공합니다.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        CLIENT INTERFACES (3 Protocols)                         │
└───────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
    │   REST API       │    │   MCP SERVER     │    │   A2A SERVER     │
    │ (HTTP/JSON)      │    │ (stdio/JSON-RPC) │    │ (HTTP/JSON-RPC)  │
    │                  │    │                  │    │                  │
    │ POST /agent/     │    │ agent_query      │    │ message/send     │
    │ query            │    │ (tool)           │    │ (RPC method)     │
    │                  │    │                  │    │                  │
    │ Response:        │    │ Response:        │    │ Response:        │
    │ {answer, ...}    │    │ JSON (MCP)       │    │ TextPart +       │
    │                  │    │                  │    │ DataPart (A2A)   │
    └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────────┐
                        │    AgentService            │
                        │ (Core Query Interface)     │
                        │                            │
                        │ • query()                  │
                        │ • query_async()            │
                        │ • query_stream()           │
                        └────────────┬───────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │   Cache      │  │  Coalescer   │  │  Semaphore   │
            │ (Query LRU)  │  │ (Dedup)      │  │ (Rate limit) │
            └──────────────┘  └──────────────┘  └──────────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────────┐
                    │   LangGraph StateGraph             │
                    │   (ReAct Loop)                     │
                    │                                    │
                    │  Nodes:                            │
                    │  • reason_node                     │
                    │  • tool_node                       │
                    │  • update_results_node             │
                    └────────────┬───────────────────────┘
                                 │
                    ┌────────────┴──────────────┐
                    │                           │
                    ▼                           ▼
        ┌──────────────────────┐    ┌──────────────────────┐
        │ GraphRAGService      │    │ Tool Factory         │
        │ (Business Logic)     │    │ (Tool Definitions)   │
        │                      │    │                      │
        │ • Query Routing      │    │ 5 Tools:             │
        │ • Pipeline Selection │    │ • cypher_query       │
        │ • History Mgmt       │    │ • vector_search      │
        │ • Neo4j Interface    │    │ • hybrid_search      │
        │                      │    │ • get_schema         │
        │                      │    │ • user_memory        │
        └──────────────────────┘    └──────────────────────┘
                    │                           │
                    └────────────┬──────────────┘
                                 │
                    ┌────────────┴──────────────┐
                    │                           │
                    ▼                           ▼
            ┌──────────────────────┐   ┌──────────────────────┐
            │   Neo4j Database     │   │   LLM Provider       │
            │   (Persistence)      │   │   (OpenAI/Bedrock)   │
            └──────────────────────┘   └──────────────────────┘
```

---

## 3. Tool Execution Flow

Agent가 도구를 실행하는 순서를 보여줍니다.

**User Query:** "Find entities connected to X with similar properties"

```
              │
              ▼
      ┌──────────────────────┐
      │ Agent Reason Node    │
      │                      │
      │ LLM Analyzes Query   │
      │ with Tool Context    │
      └──────────────────────┘
              │
  ┌───────────┴───────────┐
  │                       │
  ▼                       ▼
Needs Entity        Needs Similar
Info (Cypher)       Properties (Vector)
  │                       │
  ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│ cypher_query     │   │ vector_search    │
│ tool invoked     │   │ tool invoked     │
│                  │   │                  │
│ @tool            │   │ @tool            │
│ def cypher_...   │   │ def vector_...   │
│   service.query( │   │   service.query( │
│     force_route  │   │     force_route  │
│     ="cypher"    │   │     ="vector"    │
│   )              │   │   )              │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────┐
│    GraphRAGService.query()           │
│                                      │
│ • Router bypassed (force_route set)  │
│ • Execute Cypher RAG pipeline        │
│ • Execute Vector RAG pipeline        │
│                                      │
│ Returns: QueryResult                 │
│ {answer, cypher, context}            │
└─────────────────────────────────────┘
         │                      │
         └─────────────┬────────┘
                       │
                       ▼
            ┌────────────────────────┐
            │ Tool Results Updated   │
            │ Back to Agent State    │
            │                        │
            │ Tool Results:          │
            │ • "Connected to X:     │
            │   A, B, C"             │
            │ • "Similar entities:   │
            │   X1, X2, X3"          │
            └────────────────────────┘
                       │
                       ▼
            ┌────────────────────────┐
            │ Agent Reason Node      │
            │ (Next Iteration)       │
            │                        │
            │ Analyzes new info,     │
            │ Generates final answer │
            └────────────────────────┘
                       │
                       ▼
            Final Answer Generated
```

---

## 4. Single vs Multi-Agent Architecture

### Current Architecture (Single Agent)

```
    User Query
         │
         ▼
    ┌─────────────────┐
    │ Protocol Layer  │  (REST/MCP/A2A)
    │  (adapter)      │
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────┐
    │ Capora AI Ontology   │
    │ ReAct Agent          │
    │                      │
    │ • Reasoning          │
    │ • Entity Queries     │
    │ • Vector Searches    │
    │ • User Memory        │
    └────────┬─────────────┘
             │
             ▼
    ┌─────────────────┐
    │ Answer          │
    └─────────────────┘
```

### Proposed Architecture (Multi-Agent)

```
    User Query ("Find X warehouse inventory and shipment status")
         │
         ▼
    ┌──────────────────────┐
    │ Query Orchestrator   │
    │ • Route by domain    │
    │ • Decompose query    │
    └────────┬─────────────┘
             │
    ┌────────┴────────┬──────────────┐
    │                 │              │
    ▼                 ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  WMS Agent   │ │  TMS Agent   │ │  FMS Agent   │
│              │ │              │ │              │
│ • Inventory  │ │ • Shipment   │ │ • Costs      │
│ • Stock      │ │   Status     │ │ • Pricing    │
│ • Warehouse  │ │ • Routes     │ │ • Budgets    │
│              │ │              │ │              │
│ Domain:      │ │ Domain:      │ │ Domain:      │
│ Warehouse    │ │ Transport    │ │ Financial    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
            ┌──────────────────────────┐
            │ Result Aggregator        │
            │ • Merge results          │
            │ • Resolve conflicts      │
            │ • Generate unified view  │
            └──────────┬───────────────┘
                       │
                       ▼
            ┌─────────────────────────┐
            │ Unified Answer          │
            │ (WMS + TMS + FMS data)  │
            └─────────────────────────┘
```

---

## 5. Tool Availability Matrix

각 Agent가 사용할 수 있는 도구를 정의합니다.

| Tool Name | Current (Ontology) | WMS | TMS | FMS | TAP |
|-----------|:------------------:|:---:|:---:|:---:|:---:|
| **공통 도구** |
| cypher_query | ✓ | ✓ | ✓ | ✓ | ✓ |
| vector_search | ✓ | ✓ | ✓ | ✓ | ✓ |
| hybrid_search | ✓ | ✓ | ✓ | ✓ | ✓ |
| get_schema | ✓ | ✓ | ✓ | ✓ | ✓ |
| user_memory | ✓ | ✓ | ✓ | ✓ | ✓ |
| **WMS 전용** |
| inventory_qty | | ✓ | | | |
| stock_level | | ✓ | | | |
| warehouse_loc | | ✓ | | | |
| **TMS 전용** |
| shipment_stat | | | ✓ | | |
| route_plan | | | ✓ | | |
| delivery_eta | | | ✓ | | |
| **FMS 전용** |
| cost_calc | | | | ✓ | |
| budget_check | | | | ✓ | |
| price_quote | | | | ✓ | |
| **TAP 전용** |
| report_gen | | | | | ✓ |
| trend_predict | | | | | ✓ |
| kpi_analysis | | | | | ✓ |

---

## 6. File Structure for Multi-Agent System

```
genai-fundamentals/
├── api/
│   ├── agent/              # Current: Single ReAct Agent
│   │   ├── __init__.py
│   │   ├── state.py        # REUSABLE: AgentState schema
│   │   ├── graph.py        # REUSABLE: LangGraph pattern
│   │   ├── tools.py        # Can be templated
│   │   ├── prompts.py      # Domain-specific versions
│   │   └── service.py      # REUSABLE: AgentService base
│   │
│   ├── wms/                # NEW: Warehouse Management System
│   │   ├── __init__.py
│   │   ├── service.py      # WMS domain service
│   │   ├── tools.py        # WMS-specific tools
│   │   ├── prompts.py      # WMS system prompts
│   │   └── agent.py        # WMSAgent(AgentService)
│   │
│   ├── tms/                # NEW: Transport Management System
│   │   ├── __init__.py
│   │   ├── service.py      # TMS domain service
│   │   ├── tools.py        # TMS-specific tools
│   │   ├── prompts.py      # TMS system prompts
│   │   └── agent.py        # TMSAgent(AgentService)
│   │
│   ├── fms/                # NEW: Financial Management System
│   │   ├── __init__.py
│   │   ├── service.py      # FMS domain service
│   │   ├── tools.py        # FMS-specific tools
│   │   ├── prompts.py      # FMS system prompts
│   │   └── agent.py        # FMSAgent(AgentService)
│   │
│   ├── tap/                # NEW: Trade & Analytics Platform
│   │   ├── __init__.py
│   │   ├── service.py      # TAP domain service
│   │   ├── tools.py        # TAP-specific tools
│   │   ├── prompts.py      # TAP system prompts
│   │   └── agent.py        # TAPAgent(AgentService)
│   │
│   ├── orchestrator/       # NEW: Agent Coordination
│   │   ├── __init__.py
│   │   ├── router.py       # Query → Domain routing
│   │   ├── executor.py     # Orchestrator class
│   │   └── aggregator.py   # Result merging
│   │
│   ├── config.py           # EXTEND: Add domain configs
│   ├── cache.py            # REUSABLE: Generic caching
│   │
│   ├── server.py           # UPDATE: Orchestrator endpoint
│   ├── mcp_server.py       # UPDATE: Orchestrator tools
│   └── a2a_server.py       # UPDATE: Orchestrator executor
│
└── tests/
    ├── test_agent.py       # EXISTING
    ├── test_wms_agent.py   # NEW
    ├── test_tms_agent.py   # NEW
    ├── test_fms_agent.py   # NEW
    ├── test_tap_agent.py   # NEW
    └── test_orchestrator.py # NEW
```

---

## 7. Key Metrics & Configuration

### Performance Baselines

| Metric | Value | Description |
|--------|-------|-------------|
| Query Cache Hit | ~0.01s | 317× faster than cold |
| Query Cache Miss | ~4.7s | LLM API latency |
| Cache Hit Rate | 94.64% | with query normalization |
| Max Concurrent LLM | 10 | per agent |
| Max Pool Connections | 100 | Neo4j |
| Agent Max Iterations | 10 | per query |
| History Window | 10 turns | 20 messages |
| Session Cache TTL | 30 min | |
| Schema Cache TTL | 1 hour | |

### Configuration Hierarchy

```
Environment Variables
       ↓
config.py (AppConfig dataclass)
       ↓
get_config() singleton
       ↓
Service Instances
       ↓
Agent Instances
```

### Environment Variables for Multi-Agent

```bash
# Common
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
NEO4J_URI=neo4j://...

# Per-domain (optional)
WMS_DB_URI=postgresql://...
TMS_DB_URI=mongodb://...
FMS_API_KEY=...
TAP_API_KEY=...

# Orchestrator
ORCHESTRATOR_MAX_AGENTS=4
ORCHESTRATOR_PARALLEL_EXECUTION=true
ORCHESTRATOR_RESULT_TIMEOUT=30
```
