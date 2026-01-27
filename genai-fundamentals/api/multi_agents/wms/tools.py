"""
WMS Agent Tools Module

WMS (창고 관리 시스템) 도메인 전용 도구를 정의합니다.

Tools:
- wms_inventory_query: 재고 현황 조회
- wms_location_search: 재고 위치 검색
- wms_utilization: 적재율 조회
- wms_inbound_status: 입고 현황
- wms_outbound_status: 출고 현황
"""

import logging
from typing import List, Optional
from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


def create_wms_tools(graphrag_service) -> List[BaseTool]:
    """
    WMS 도메인 전용 도구 생성

    Args:
        graphrag_service: GraphRAGService 인스턴스

    Returns:
        WMS 전용 도구 리스트
    """

    @tool
    def wms_inventory_query(warehouse: Optional[str] = None, sku: Optional[str] = None, limit: int = 10) -> str:
        """
        창고 재고 현황을 조회합니다.

        Args:
            warehouse: 창고 이름 필터 (옵션)
            sku: SKU 코드 필터 (옵션)
            limit: 최대 결과 수

        Returns:
            재고 현황 정보
        """
        try:
            cypher = """
            MATCH (w:Warehouse)
            OPTIONAL MATCH (w)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)<-[:STORED_AT]-(i:InventoryItem)
            """

            where_clauses = []
            if warehouse:
                where_clauses.append(f"w.name CONTAINS '{warehouse}'")
            if sku:
                where_clauses.append(f"i.sku = '{sku}'")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN w.name as warehouse,
                   i.sku as sku,
                   sum(i.quantity) as total_qty,
                   collect(DISTINCT b.bin_id) as locations
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "조회된 재고 정보가 없습니다."

            output = f"## 재고 현황 ({len(result)}건)\n\n"
            for row in result:
                locs = row.get('locations', [])
                loc_str = ", ".join(str(l) for l in locs if l)[:50] if locs else "N/A"
                output += f"- **{row.get('sku', 'N/A')}** @ {row.get('warehouse', 'N/A')}: {row.get('total_qty', 0)}개 (위치: {loc_str})\n"

            return output

        except Exception as e:
            logger.error(f"wms_inventory_query error: {e}")
            return f"재고 조회 중 오류 발생: {str(e)}"

    @tool
    def wms_location_search(sku: str) -> str:
        """
        특정 SKU의 보관 위치를 검색합니다.

        Args:
            sku: SKU 코드

        Returns:
            SKU 보관 위치 정보
        """
        try:
            cypher = f"""
            MATCH (i:InventoryItem {{sku: '{sku}'}})-[:STORED_AT]->(b:Bin)-[:LOCATED_IN]->(z:Zone)-[:BELONGS_TO]->(w:Warehouse)
            RETURN w.name as warehouse, z.zone_type as zone, b.bin_id as bin, i.quantity as qty
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"SKU '{sku}'의 재고 정보가 없습니다."

            output = f"## SKU '{sku}' 보관 위치\n\n"
            for row in result:
                output += f"- {row.get('warehouse', 'N/A')} > {row.get('zone', 'N/A')} > {row.get('bin', 'N/A')}: {row.get('qty', 0)}개\n"

            return output

        except Exception as e:
            logger.error(f"wms_location_search error: {e}")
            return f"위치 검색 중 오류 발생: {str(e)}"

    @tool
    def wms_utilization(warehouse: Optional[str] = None) -> str:
        """
        창고 적재율을 조회합니다.

        Args:
            warehouse: 창고 이름 필터 (옵션, 없으면 전체)

        Returns:
            적재율 정보
        """
        try:
            cypher = """
            MATCH (w:Warehouse)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)
            """

            if warehouse:
                cypher += f"\nWHERE w.name CONTAINS '{warehouse}'"

            cypher += """
            WITH w, count(b) as total_bins
            MATCH (w)<-[:BELONGS_TO]-(z:Zone)<-[:LOCATED_IN]-(b:Bin)<-[:STORED_AT]-(:InventoryItem)
            WITH w, total_bins, count(DISTINCT b) as occupied_bins
            RETURN w.name as warehouse, total_bins, occupied_bins,
                   round(100.0 * occupied_bins / total_bins, 2) as utilization_pct
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "적재율 정보가 없습니다."

            output = "## 창고 적재율\n\n"
            for row in result:
                output += f"- **{row.get('warehouse', 'N/A')}**: {row.get('utilization_pct', 0)}% "
                output += f"({row.get('occupied_bins', 0)}/{row.get('total_bins', 0)} bins)\n"

            return output

        except Exception as e:
            logger.error(f"wms_utilization error: {e}")
            return f"적재율 조회 중 오류 발생: {str(e)}"

    @tool
    def wms_inbound_status(status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        입고 현황을 조회합니다.

        Args:
            status_filter: 상태 필터 (scheduled, arrived, receiving, completed)
            limit: 최대 결과 수

        Returns:
            입고 현황 정보
        """
        try:
            cypher = """
            MATCH (io:InboundOrder)-[:INBOUND_TO]->(w:Warehouse)
            """

            if status_filter:
                cypher += f"\nWHERE io.status = '{status_filter}'"
            else:
                cypher += "\nWHERE io.status IN ['scheduled', 'arrived', 'receiving']"

            cypher += f"""
            RETURN io.inbound_id as id, io.status as status,
                   io.expected_date as expected, w.name as warehouse
            ORDER BY io.expected_date
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "입고 예정 정보가 없습니다."

            output = f"## 입고 현황 ({len(result)}건)\n\n"
            for row in result:
                output += f"- **{row.get('id', 'N/A')}** [{row.get('status', 'N/A')}]: {row.get('warehouse', 'N/A')} (예정: {row.get('expected', 'N/A')})\n"

            return output

        except Exception as e:
            logger.error(f"wms_inbound_status error: {e}")
            return f"입고 현황 조회 중 오류 발생: {str(e)}"

    @tool
    def wms_outbound_status(status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        출고 현황을 조회합니다.

        Args:
            status_filter: 상태 필터 (pending, picking, packed, shipped)
            limit: 최대 결과 수

        Returns:
            출고 현황 정보
        """
        try:
            cypher = """
            MATCH (oo:OutboundOrder)-[:OUTBOUND_FROM]->(w:Warehouse)
            """

            if status_filter:
                cypher += f"\nWHERE oo.status = '{status_filter}'"
            else:
                cypher += "\nWHERE oo.status IN ['pending', 'picking', 'packed']"

            cypher += f"""
            RETURN oo.outbound_id as id, oo.status as status,
                   oo.expected_date as expected, w.name as warehouse
            ORDER BY oo.expected_date
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "출고 예정 정보가 없습니다."

            output = f"## 출고 현황 ({len(result)}건)\n\n"
            for row in result:
                output += f"- **{row.get('id', 'N/A')}** [{row.get('status', 'N/A')}]: {row.get('warehouse', 'N/A')} (예정: {row.get('expected', 'N/A')})\n"

            return output

        except Exception as e:
            logger.error(f"wms_outbound_status error: {e}")
            return f"출고 현황 조회 중 오류 발생: {str(e)}"

    return [
        wms_inventory_query,
        wms_location_search,
        wms_utilization,
        wms_inbound_status,
        wms_outbound_status,
    ]
