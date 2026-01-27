"""
Unified Ontology Module

물류 시스템 통합 온톨로지를 정의합니다.
상위 개념(Upper Ontology)과 도메인별 TBox를 제공합니다.

Usage:
    from genai_fundamentals.api.ontology import (
        get_upper_ontology,
        get_cross_domain_mappings,
        get_wms_schema,
        get_tms_schema,
        get_fms_schema,
        get_tap_schema
    )

    # 상위 온톨로지
    upper = get_upper_ontology()

    # 도메인별 스키마
    tms_schema = get_tms_schema()

    # 크로스 도메인 매핑
    mappings = get_cross_domain_mappings()
"""

from .upper import (
    get_upper_ontology,
    get_cross_domain_mappings,
    UPPER_ONTOLOGY,
    CROSS_DOMAIN_MAPPINGS,
)

# 도메인별 스키마는 해당 모듈에서 import
# from .tms_schema import get_tms_schema
# from .wms_schema import get_wms_schema
# from .fms_schema import get_fms_schema
# from .tap_schema import get_tap_schema

__all__ = [
    # Upper Ontology
    "get_upper_ontology",
    "get_cross_domain_mappings",
    "UPPER_ONTOLOGY",
    "CROSS_DOMAIN_MAPPINGS",
]
