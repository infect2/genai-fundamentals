"""
FMS Agent Tools Module

FMS (차량 관리 시스템) 도메인 전용 도구를 정의합니다.

Tools:
- fms_vehicle_status: 차량 상태 조회
- fms_maintenance_schedule: 정비 일정 조회
- fms_driver_info: 운전자 정보 조회
- fms_fuel_consumption: 연비/주유 기록 조회
- fms_consumable_status: 소모품 상태 조회
"""

import logging
from typing import List, Optional
from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


def create_fms_tools(graphrag_service) -> List[BaseTool]:
    """
    FMS 도메인 전용 도구 생성
    """

    @tool
    def fms_vehicle_status(vehicle_plate: Optional[str] = None, status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        차량 상태를 조회합니다.

        Args:
            vehicle_plate: 차량 번호판 필터 (옵션)
            status_filter: 상태 필터 (active, inactive, maintenance, retired)
            limit: 최대 결과 수

        Returns:
            차량 상태 정보
        """
        try:
            cypher = """
            MATCH (v:Vehicle)
            OPTIONAL MATCH (v)<-[:ASSIGNED_TO]-(d:Driver)
            """

            where_clauses = []
            if vehicle_plate:
                where_clauses.append(f"v.license_plate CONTAINS '{vehicle_plate}'")
            if status_filter:
                where_clauses.append(f"v.status = '{status_filter}'")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN v.license_plate as plate, v.vehicle_type as type,
                   v.status as status, v.mileage as mileage, d.name as driver
            ORDER BY v.license_plate
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "조회된 차량 정보가 없습니다."

            output = f"## 차량 현황 ({len(result)}건)\n\n"
            for row in result:
                output += f"- **{row.get('plate', 'N/A')}** ({row.get('type', 'N/A')})\n"
                output += f"  - 상태: {row.get('status', 'N/A')}, 주행거리: {row.get('mileage', 'N/A')}km\n"
                output += f"  - 배정 운전자: {row.get('driver', '미배정')}\n"

            return output

        except Exception as e:
            logger.error(f"fms_vehicle_status error: {e}")
            return f"차량 상태 조회 중 오류 발생: {str(e)}"

    @tool
    def fms_maintenance_schedule(vehicle_plate: Optional[str] = None, include_completed: bool = False, limit: int = 10) -> str:
        """
        정비 일정을 조회합니다.

        Args:
            vehicle_plate: 차량 번호판 필터 (옵션)
            include_completed: 완료된 정비 포함 여부
            limit: 최대 결과 수

        Returns:
            정비 일정 정보
        """
        try:
            cypher = """
            MATCH (v:Vehicle)-[:HAS_MAINTENANCE]->(m:MaintenanceRecord)
            """

            where_clauses = []
            if vehicle_plate:
                where_clauses.append(f"v.license_plate CONTAINS '{vehicle_plate}'")
            if not include_completed:
                where_clauses.append("m.next_due_date >= date()")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN v.license_plate as plate, m.maintenance_type as type,
                   m.next_due_date as due_date, m.date as last_date, m.description as desc
            ORDER BY m.next_due_date
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "정비 예정 정보가 없습니다."

            output = f"## 정비 일정 ({len(result)}건)\n\n"
            for row in result:
                output += f"- **{row.get('plate', 'N/A')}** - {row.get('type', 'N/A')}\n"
                output += f"  - 예정일: {row.get('due_date', 'N/A')}, 최근 정비: {row.get('last_date', 'N/A')}\n"
                if row.get('desc'):
                    output += f"  - 내용: {row.get('desc')}\n"

            return output

        except Exception as e:
            logger.error(f"fms_maintenance_schedule error: {e}")
            return f"정비 일정 조회 중 오류 발생: {str(e)}"

    @tool
    def fms_driver_info(driver_name: Optional[str] = None, limit: int = 10) -> str:
        """
        운전자 정보를 조회합니다.

        Args:
            driver_name: 운전자 이름 필터 (옵션)
            limit: 최대 결과 수

        Returns:
            운전자 정보
        """
        try:
            cypher = """
            MATCH (d:Driver)
            OPTIONAL MATCH (d)-[:ASSIGNED_TO]->(v:Vehicle)
            """

            if driver_name:
                cypher += f"\nWHERE d.name CONTAINS '{driver_name}'"

            cypher += f"""
            RETURN d.name as name, d.phone as phone, d.rating as rating,
                   d.license_expiry as license_expiry, collect(v.license_plate) as vehicles
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "조회된 운전자 정보가 없습니다."

            output = f"## 운전자 정보 ({len(result)}건)\n\n"
            for row in result:
                vehicles = row.get('vehicles', [])
                vehicle_str = ", ".join(v for v in vehicles if v) if vehicles else "미배정"
                output += f"- **{row.get('name', 'N/A')}** (평점: {row.get('rating', 'N/A')})\n"
                output += f"  - 연락처: {row.get('phone', 'N/A')}\n"
                output += f"  - 면허 만료: {row.get('license_expiry', 'N/A')}\n"
                output += f"  - 배정 차량: {vehicle_str}\n"

            return output

        except Exception as e:
            logger.error(f"fms_driver_info error: {e}")
            return f"운전자 정보 조회 중 오류 발생: {str(e)}"

    @tool
    def fms_consumable_status(vehicle_plate: Optional[str] = None, warning_only: bool = False, limit: int = 20) -> str:
        """
        소모품 상태를 조회합니다.

        Args:
            vehicle_plate: 차량 번호판 필터 (옵션)
            warning_only: 교체 필요 항목만 표시
            limit: 최대 결과 수

        Returns:
            소모품 상태 정보
        """
        try:
            cypher = """
            MATCH (v:Vehicle)-[:HAS_CONSUMABLE]->(c:Consumable)
            """

            where_clauses = []
            if vehicle_plate:
                where_clauses.append(f"v.license_plate CONTAINS '{vehicle_plate}'")
            if warning_only:
                where_clauses.append("c.status IN ['warning', 'replace_soon', 'overdue']")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN v.license_plate as plate, c.name as consumable,
                   c.status as status, c.current_life_km as current_km, c.expected_life_km as expected_km
            ORDER BY c.status DESC
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "소모품 정보가 없습니다."

            output = f"## 소모품 상태 ({len(result)}건)\n\n"
            for row in result:
                status_emoji = {"good": "", "warning": "", "replace_soon": "", "overdue": ""}.get(row.get('status', ''), '')
                output += f"- **{row.get('plate', 'N/A')}** - {row.get('consumable', 'N/A')} {status_emoji}\n"
                output += f"  - 상태: {row.get('status', 'N/A')}\n"
                output += f"  - 사용: {row.get('current_km', 0)}/{row.get('expected_km', 0)}km\n"

            return output

        except Exception as e:
            logger.error(f"fms_consumable_status error: {e}")
            return f"소모품 상태 조회 중 오류 발생: {str(e)}"

    @tool
    def fms_statistics(stat_type: str = "overview") -> str:
        """
        FMS 통계를 조회합니다.

        Args:
            stat_type: 통계 유형 (overview, status, maintenance)

        Returns:
            통계 정보
        """
        try:
            if stat_type == "overview":
                cypher = """
                MATCH (v:Vehicle)
                WITH count(v) as total_vehicles
                MATCH (d:Driver)
                WITH total_vehicles, count(d) as total_drivers
                MATCH (v:Vehicle) WHERE v.status = 'maintenance'
                RETURN total_vehicles, total_drivers, count(v) as in_maintenance
                """
                result = graphrag_service.execute_cypher(cypher)

                if result:
                    r = result[0]
                    return f"""## FMS 전체 현황

- 총 차량: {r.get('total_vehicles', 0)}대
- 총 운전자: {r.get('total_drivers', 0)}명
- 정비 중: {r.get('in_maintenance', 0)}대
"""

            elif stat_type == "status":
                cypher = """
                MATCH (v:Vehicle)
                RETURN v.status as status, count(v) as count
                ORDER BY count DESC
                """
                result = graphrag_service.execute_cypher(cypher)

                output = "## 차량 상태 통계\n\n"
                for row in result:
                    output += f"- {row.get('status', 'N/A')}: {row.get('count', 0)}대\n"
                return output

            return "지원하지 않는 통계 유형입니다."

        except Exception as e:
            logger.error(f"fms_statistics error: {e}")
            return f"통계 조회 중 오류 발생: {str(e)}"

    return [
        fms_vehicle_status,
        fms_maintenance_schedule,
        fms_driver_info,
        fms_consumable_status,
        fms_statistics,
    ]
