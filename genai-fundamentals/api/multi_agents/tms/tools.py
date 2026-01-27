"""
TMS Agent Tools Module

TMS (운송 관리 시스템) 도메인 전용 도구를 정의합니다.
Neo4j Cypher 쿼리와 시맨틱 검색을 활용합니다.

Tools:
- tms_shipment_status: 배송 현황 조회
- tms_route_optimization: 경로 최적화 제안
- tms_carrier_search: 운송사 검색
- tms_dispatch_query: 배차 현황 조회
- tms_delay_analysis: 지연 분석

Usage:
    from genai_fundamentals.api.multi_agents.tms.tools import create_tms_tools

    tools = create_tms_tools(graphrag_service)
"""

import logging
from typing import List, Optional
from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


def create_tms_tools(graphrag_service) -> List[BaseTool]:
    """
    TMS 도메인 전용 도구 생성

    Args:
        graphrag_service: GraphRAGService 인스턴스

    Returns:
        TMS 전용 도구 리스트
    """

    @tool
    def tms_shipment_status(query: str, status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        배송 현황을 조회합니다.

        특정 배송 건, 화주별 배송, 운송사별 배송 등을 조회할 수 있습니다.
        status_filter로 특정 상태의 배송만 필터링할 수 있습니다.

        Args:
            query: 조회 조건 (예: "서울 물류센터 발송 배송", "한진상사 화주 배송")
            status_filter: 배송 상태 필터 (requested, matched, pickup_pending, in_transit, delivered, cancelled)
            limit: 최대 결과 수

        Returns:
            배송 현황 정보 (배송ID, 상태, 출발지, 목적지, 화주, 운송사, 차량)
        """
        try:
            # Cypher 쿼리 생성
            cypher = """
            MATCH (s:Shipment)
            OPTIONAL MATCH (s)-[:REQUESTED_BY]->(shipper:Shipper)
            OPTIONAL MATCH (s)-[:FULFILLED_BY]->(carrier:Carrier)
            OPTIONAL MATCH (s)-[:ASSIGNED_TO]->(v:Vehicle)
            OPTIONAL MATCH (s)-[:ORIGIN]->(origin)
            OPTIONAL MATCH (s)-[:DESTINATION]->(dest)
            """

            if status_filter:
                cypher += f"\nWHERE s.status = '{status_filter}'"

            cypher += f"""
            RETURN s.uri as shipment_id,
                   s.status as status,
                   origin.name as origin,
                   dest.name as destination,
                   shipper.name as shipper,
                   carrier.name as carrier,
                   v.licensePlate as vehicle
            LIMIT {limit}
            """

            # GraphRAG 서비스를 통해 쿼리 실행
            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"조건에 맞는 배송이 없습니다. (query: {query}, status: {status_filter})"

            # 결과 포맷팅
            output = f"## 배송 현황 ({len(result)}건)\n\n"
            for i, row in enumerate(result, 1):
                output += f"### {i}. {row.get('shipment_id', 'N/A')}\n"
                output += f"- 상태: {row.get('status', 'N/A')}\n"
                output += f"- 출발지: {row.get('origin', 'N/A')}\n"
                output += f"- 목적지: {row.get('destination', 'N/A')}\n"
                output += f"- 화주: {row.get('shipper', 'N/A')}\n"
                output += f"- 운송사: {row.get('carrier', 'N/A')}\n"
                output += f"- 차량: {row.get('vehicle', 'N/A')}\n\n"

            output += f"\n\nCypher Query:\n{cypher.strip()}"
            return output

        except Exception as e:
            logger.error(f"tms_shipment_status error: {e}")
            return f"배송 현황 조회 중 오류 발생: {str(e)}"

    @tool
    def tms_carrier_search(query: str, region: Optional[str] = None, limit: int = 10) -> str:
        """
        운송사를 검색합니다.

        운송사 이름, 서비스 지역, 보유 차량 등의 조건으로 검색할 수 있습니다.

        Args:
            query: 검색 조건 (예: "냉동차 보유 운송사", "서울 지역 운송사")
            region: 서비스 지역 필터 (옵션)
            limit: 최대 결과 수

        Returns:
            운송사 정보 (이름, 연락처, 서비스지역, 보유차량수)
        """
        try:
            cypher = """
            MATCH (c:Carrier)
            OPTIONAL MATCH (c)-[:OPERATES]->(v:Vehicle)
            OPTIONAL MATCH (c)-[:SERVES_REGION]->(region)
            """

            if region:
                cypher += f"\nWHERE region.name CONTAINS '{region}'"

            cypher += f"""
            WITH c, collect(DISTINCT v) as vehicles, collect(DISTINCT region.name) as regions
            RETURN c.name as name,
                   c.contact as contact,
                   regions as service_regions,
                   size(vehicles) as vehicle_count
            ORDER BY vehicle_count DESC
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"조건에 맞는 운송사가 없습니다. (query: {query}, region: {region})"

            output = f"## 운송사 검색 결과 ({len(result)}건)\n\n"
            for i, row in enumerate(result, 1):
                regions = row.get('service_regions', [])
                regions_str = ", ".join(r for r in regions if r) if regions else "N/A"
                output += f"### {i}. {row.get('name', 'N/A')}\n"
                output += f"- 연락처: {row.get('contact', 'N/A')}\n"
                output += f"- 서비스 지역: {regions_str}\n"
                output += f"- 보유 차량: {row.get('vehicle_count', 0)}대\n\n"

            output += f"\n\nCypher Query:\n{cypher.strip()}"
            return output

        except Exception as e:
            logger.error(f"tms_carrier_search error: {e}")
            return f"운송사 검색 중 오류 발생: {str(e)}"

    @tool
    def tms_dispatch_query(date_filter: Optional[str] = None, carrier_name: Optional[str] = None, limit: int = 20) -> str:
        """
        배차 현황을 조회합니다.

        특정 날짜, 운송사별 배차 현황을 조회할 수 있습니다.

        Args:
            date_filter: 날짜 필터 (예: "2024-01-15") - 옵션
            carrier_name: 운송사 이름 필터 - 옵션
            limit: 최대 결과 수

        Returns:
            배차 현황 (차량, 운송사, 배정된 배송 목록)
        """
        try:
            cypher = """
            MATCH (carrier:Carrier)-[:OPERATES]->(v:Vehicle)
            OPTIONAL MATCH (v)<-[:ASSIGNED_TO]-(s:Shipment)
            """

            where_clauses = []
            if carrier_name:
                where_clauses.append(f"carrier.name CONTAINS '{carrier_name}'")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            WITH carrier, v, collect(s) as shipments
            RETURN carrier.name as carrier,
                   v.licensePlate as vehicle,
                   v.vehicleType as vehicle_type,
                   size(shipments) as assigned_count,
                   [s IN shipments | s.status] as statuses
            ORDER BY assigned_count DESC
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"배차 현황이 없습니다. (carrier: {carrier_name}, date: {date_filter})"

            output = f"## 배차 현황 ({len(result)}건)\n\n"
            for i, row in enumerate(result, 1):
                statuses = row.get('statuses', [])
                status_str = ", ".join(s for s in statuses if s) if statuses else "없음"
                output += f"### {i}. {row.get('vehicle', 'N/A')} ({row.get('vehicle_type', 'N/A')})\n"
                output += f"- 운송사: {row.get('carrier', 'N/A')}\n"
                output += f"- 배정 건수: {row.get('assigned_count', 0)}건\n"
                output += f"- 배송 상태: {status_str}\n\n"

            output += f"\n\nCypher Query:\n{cypher.strip()}"
            return output

        except Exception as e:
            logger.error(f"tms_dispatch_query error: {e}")
            return f"배차 현황 조회 중 오류 발생: {str(e)}"

    @tool
    def tms_route_info(origin: str, destination: str, limit: int = 5) -> str:
        """
        특정 경로의 배송 정보를 조회합니다.

        출발지와 목적지 간의 배송 현황과 운송사 정보를 제공합니다.

        Args:
            origin: 출발지 이름 (예: "서울 물류센터", "부산항")
            destination: 목적지 이름
            limit: 최대 결과 수

        Returns:
            해당 경로의 배송 정보 및 이용 가능 운송사
        """
        try:
            cypher = f"""
            MATCH (s:Shipment)-[:ORIGIN]->(origin)
            MATCH (s)-[:DESTINATION]->(dest)
            WHERE origin.name CONTAINS '{origin}' AND dest.name CONTAINS '{destination}'
            OPTIONAL MATCH (s)-[:FULFILLED_BY]->(carrier:Carrier)
            OPTIONAL MATCH (s)-[:ASSIGNED_TO]->(v:Vehicle)
            RETURN s.uri as shipment_id,
                   s.status as status,
                   origin.name as origin_name,
                   dest.name as dest_name,
                   carrier.name as carrier,
                   v.vehicleType as vehicle_type
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"'{origin}' → '{destination}' 경로의 배송 정보가 없습니다."

            output = f"## {origin} → {destination} 경로 배송 ({len(result)}건)\n\n"
            for i, row in enumerate(result, 1):
                output += f"### {i}. {row.get('shipment_id', 'N/A')}\n"
                output += f"- 상태: {row.get('status', 'N/A')}\n"
                output += f"- 운송사: {row.get('carrier', 'N/A')}\n"
                output += f"- 차량 유형: {row.get('vehicle_type', 'N/A')}\n\n"

            output += f"\n\nCypher Query:\n{cypher.strip()}"
            return output

        except Exception as e:
            logger.error(f"tms_route_info error: {e}")
            return f"경로 정보 조회 중 오류 발생: {str(e)}"

    @tool
    def tms_shipper_shipments(shipper_name: str, status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        특정 화주의 배송 목록을 조회합니다.

        Args:
            shipper_name: 화주 이름 (예: "한진상사", "포스코")
            status_filter: 배송 상태 필터 (옵션)
            limit: 최대 결과 수

        Returns:
            해당 화주의 배송 목록
        """
        try:
            cypher = f"""
            MATCH (shipper:Shipper)<-[:REQUESTED_BY]-(s:Shipment)
            WHERE shipper.name CONTAINS '{shipper_name}'
            """

            if status_filter:
                cypher += f"\nAND s.status = '{status_filter}'"

            cypher += f"""
            OPTIONAL MATCH (s)-[:FULFILLED_BY]->(carrier:Carrier)
            OPTIONAL MATCH (s)-[:ORIGIN]->(origin)
            OPTIONAL MATCH (s)-[:DESTINATION]->(dest)
            RETURN shipper.name as shipper,
                   s.uri as shipment_id,
                   s.status as status,
                   origin.name as origin,
                   dest.name as destination,
                   carrier.name as carrier
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"'{shipper_name}' 화주의 배송 정보가 없습니다."

            shipper_actual = result[0].get('shipper', shipper_name)
            output = f"## {shipper_actual} 화주 배송 현황 ({len(result)}건)\n\n"
            for i, row in enumerate(result, 1):
                output += f"### {i}. {row.get('shipment_id', 'N/A')}\n"
                output += f"- 상태: {row.get('status', 'N/A')}\n"
                output += f"- 출발지: {row.get('origin', 'N/A')}\n"
                output += f"- 목적지: {row.get('destination', 'N/A')}\n"
                output += f"- 운송사: {row.get('carrier', 'N/A')}\n\n"

            output += f"\n\nCypher Query:\n{cypher.strip()}"
            return output

        except Exception as e:
            logger.error(f"tms_shipper_shipments error: {e}")
            return f"화주 배송 조회 중 오류 발생: {str(e)}"

    @tool
    def tms_statistics(stat_type: str = "overview") -> str:
        """
        TMS 통계를 조회합니다.

        Args:
            stat_type: 통계 유형
                - "overview": 전체 현황 (배송 상태별 건수, 운송사 수, 차량 수)
                - "carrier": 운송사별 배송 건수
                - "status": 상태별 배송 건수
                - "route": 주요 경로별 배송 건수

        Returns:
            요청한 통계 정보
        """
        try:
            if stat_type == "overview":
                cypher = """
                MATCH (s:Shipment)
                WITH count(s) as total_shipments
                MATCH (c:Carrier)
                WITH total_shipments, count(c) as total_carriers
                MATCH (v:Vehicle)
                WITH total_shipments, total_carriers, count(v) as total_vehicles
                MATCH (shipper:Shipper)
                RETURN total_shipments, total_carriers, total_vehicles, count(shipper) as total_shippers
                """
                result = graphrag_service.execute_cypher(cypher)

                if result:
                    r = result[0]
                    return f"""## TMS 전체 현황

- 총 배송 건수: {r.get('total_shipments', 0)}건
- 등록 운송사: {r.get('total_carriers', 0)}개
- 등록 차량: {r.get('total_vehicles', 0)}대
- 등록 화주: {r.get('total_shippers', 0)}개

Cypher Query:
{cypher.strip()}"""

            elif stat_type == "carrier":
                cypher = """
                MATCH (carrier:Carrier)<-[:FULFILLED_BY]-(s:Shipment)
                RETURN carrier.name as carrier, count(s) as shipment_count
                ORDER BY shipment_count DESC
                LIMIT 10
                """
                result = graphrag_service.execute_cypher(cypher)

                output = "## 운송사별 배송 건수 (Top 10)\n\n"
                for i, row in enumerate(result, 1):
                    output += f"{i}. {row.get('carrier', 'N/A')}: {row.get('shipment_count', 0)}건\n"
                output += f"\n\nCypher Query:\n{cypher.strip()}"
                return output

            elif stat_type == "status":
                cypher = """
                MATCH (s:Shipment)
                RETURN s.status as status, count(s) as count
                ORDER BY count DESC
                """
                result = graphrag_service.execute_cypher(cypher)

                output = "## 상태별 배송 건수\n\n"
                for row in result:
                    output += f"- {row.get('status', 'N/A')}: {row.get('count', 0)}건\n"
                output += f"\n\nCypher Query:\n{cypher.strip()}"
                return output

            elif stat_type == "route":
                cypher = """
                MATCH (s:Shipment)-[:ORIGIN]->(origin)
                MATCH (s)-[:DESTINATION]->(dest)
                RETURN origin.name as origin, dest.name as destination, count(s) as count
                ORDER BY count DESC
                LIMIT 10
                """
                result = graphrag_service.execute_cypher(cypher)

                output = "## 주요 경로별 배송 건수 (Top 10)\n\n"
                for i, row in enumerate(result, 1):
                    output += f"{i}. {row.get('origin', 'N/A')} → {row.get('destination', 'N/A')}: {row.get('count', 0)}건\n"
                output += f"\n\nCypher Query:\n{cypher.strip()}"
                return output

            else:
                return f"알 수 없는 통계 유형: {stat_type}. 지원하는 유형: overview, carrier, status, route"

        except Exception as e:
            logger.error(f"tms_statistics error: {e}")
            return f"통계 조회 중 오류 발생: {str(e)}"

    return [
        tms_shipment_status,
        tms_carrier_search,
        tms_dispatch_query,
        tms_route_info,
        tms_shipper_shipments,
        tms_statistics,
    ]
