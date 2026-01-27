"""
TAP! Agent Tools Module

TAP! (사용자 호출 서비스) 도메인 전용 도구를 정의합니다.

Tools:
- tap_call_status: 호출 현황 조회
- tap_eta_query: ETA 조회
- tap_booking_status: 예약 현황 조회
- tap_payment_history: 결제 내역 조회
- tap_feedback_submit: 피드백 조회
"""

import logging
from typing import List, Optional
from langchain_core.tools import tool, BaseTool

logger = logging.getLogger(__name__)


def create_tap_tools(graphrag_service) -> List[BaseTool]:
    """
    TAP! 도메인 전용 도구 생성
    """

    @tool
    def tap_call_status(customer_id: Optional[str] = None, request_id: Optional[str] = None, status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        호출 현황을 조회합니다.

        Args:
            customer_id: 고객 ID 필터 (옵션)
            request_id: 요청 ID 필터 (옵션)
            status_filter: 상태 필터 (pending, matched, arriving, in_progress, completed)
            limit: 최대 결과 수

        Returns:
            호출 현황 정보
        """
        try:
            cypher = """
            MATCH (cr:CallRequest)-[:REQUESTED_BY]->(c:Customer)
            OPTIONAL MATCH (cr)-[:FULFILLED_BY]->(v:Vehicle)
            OPTIONAL MATCH (cr)-[:DRIVEN_BY]->(d:Driver)
            OPTIONAL MATCH (cr)-[:PICKUP_AT]->(pickup:Location)
            OPTIONAL MATCH (cr)-[:DROPOFF_AT]->(dropoff:Location)
            """

            where_clauses = []
            if customer_id:
                where_clauses.append(f"c.customer_id = '{customer_id}'")
            if request_id:
                where_clauses.append(f"cr.request_id = '{request_id}'")
            if status_filter:
                where_clauses.append(f"cr.status = '{status_filter}'")
            else:
                where_clauses.append("cr.status IN ['pending', 'matched', 'arriving', 'in_progress']")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN cr.request_id as request_id, cr.status as status, cr.eta as eta,
                   c.name as customer, v.license_plate as vehicle, d.name as driver,
                   pickup.address as pickup, dropoff.address as dropoff
            ORDER BY cr.request_time DESC
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "조회된 호출 정보가 없습니다."

            output = f"## 호출 현황 ({len(result)}건)\n\n"
            for row in result:
                output += f"### {row.get('request_id', 'N/A')} [{row.get('status', 'N/A')}]\n"
                output += f"- 고객: {row.get('customer', 'N/A')}\n"
                output += f"- 픽업: {row.get('pickup', 'N/A')}\n"
                output += f"- 목적지: {row.get('dropoff', 'N/A')}\n"
                if row.get('vehicle'):
                    output += f"- 차량: {row.get('vehicle', 'N/A')} (운전자: {row.get('driver', 'N/A')})\n"
                if row.get('eta'):
                    output += f"- ETA: {row.get('eta')}\n"
                output += "\n"

            return output

        except Exception as e:
            logger.error(f"tap_call_status error: {e}")
            return f"호출 현황 조회 중 오류 발생: {str(e)}"

    @tool
    def tap_eta_query(request_id: str) -> str:
        """
        특정 호출의 ETA(예상 도착 시간)를 조회합니다.

        Args:
            request_id: 호출 요청 ID

        Returns:
            ETA 정보
        """
        try:
            cypher = f"""
            MATCH (cr:CallRequest {{request_id: '{request_id}'}})-[:FULFILLED_BY]->(v:Vehicle)
            OPTIONAL MATCH (cr)-[:DRIVEN_BY]->(d:Driver)
            RETURN cr.status as status, cr.eta as eta,
                   v.license_plate as vehicle, v.current_location as location,
                   d.name as driver, d.phone as driver_phone
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"요청 ID '{request_id}'를 찾을 수 없습니다."

            row = result[0]
            status = row.get('status', 'N/A')

            output = f"## 배정 정보 (요청: {request_id})\n\n"
            output += f"- 상태: {status}\n"
            output += f"- ETA: {row.get('eta', '계산 중...')}\n"
            output += f"- 차량: {row.get('vehicle', 'N/A')}\n"
            output += f"- 운전자: {row.get('driver', 'N/A')} ({row.get('driver_phone', 'N/A')})\n"

            if status == 'arriving':
                output += "\n**차량이 픽업 장소로 이동 중입니다.**\n"
            elif status == 'in_progress':
                output += "\n**현재 이동 중입니다.**\n"

            return output

        except Exception as e:
            logger.error(f"tap_eta_query error: {e}")
            return f"ETA 조회 중 오류 발생: {str(e)}"

    @tool
    def tap_booking_status(customer_id: Optional[str] = None, status_filter: Optional[str] = None, limit: int = 10) -> str:
        """
        예약 현황을 조회합니다.

        Args:
            customer_id: 고객 ID 필터 (옵션)
            status_filter: 상태 필터 (confirmed, pending_payment, cancelled, completed)
            limit: 최대 결과 수

        Returns:
            예약 현황 정보
        """
        try:
            cypher = """
            MATCH (b:Booking)-[:BOOKED_BY]->(c:Customer)
            OPTIONAL MATCH (b)-[:PICKUP_AT]->(pickup:Location)
            OPTIONAL MATCH (b)-[:DROPOFF_AT]->(dropoff:Location)
            """

            where_clauses = []
            if customer_id:
                where_clauses.append(f"c.customer_id = '{customer_id}'")
            if status_filter:
                where_clauses.append(f"b.status = '{status_filter}'")

            if where_clauses:
                cypher += "\nWHERE " + " AND ".join(where_clauses)

            cypher += f"""
            RETURN b.booking_id as booking_id, b.status as status,
                   b.scheduled_time as scheduled, c.name as customer,
                   pickup.address as pickup, dropoff.address as dropoff
            ORDER BY b.scheduled_time
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "조회된 예약 정보가 없습니다."

            output = f"## 예약 현황 ({len(result)}건)\n\n"
            for row in result:
                output += f"- **{row.get('booking_id', 'N/A')}** [{row.get('status', 'N/A')}]\n"
                output += f"  - 예약시간: {row.get('scheduled', 'N/A')}\n"
                output += f"  - 픽업: {row.get('pickup', 'N/A')}\n"
                output += f"  - 목적지: {row.get('dropoff', 'N/A')}\n"

            return output

        except Exception as e:
            logger.error(f"tap_booking_status error: {e}")
            return f"예약 현황 조회 중 오류 발생: {str(e)}"

    @tool
    def tap_payment_history(customer_id: str, limit: int = 10) -> str:
        """
        고객의 결제 내역을 조회합니다.

        Args:
            customer_id: 고객 ID
            limit: 최대 결과 수

        Returns:
            결제 내역 정보
        """
        try:
            cypher = f"""
            MATCH (c:Customer {{customer_id: '{customer_id}'}})<-[:REQUESTED_BY]-(cr:CallRequest)-[:PAID_WITH]->(p:Payment)
            RETURN cr.request_id as request_id, p.amount as amount,
                   p.method as method, p.status as status, p.paid_at as paid_at
            ORDER BY p.paid_at DESC
            LIMIT {limit}
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return f"고객 '{customer_id}'의 결제 내역이 없습니다."

            output = f"## 결제 내역 ({len(result)}건)\n\n"
            total = 0
            for row in result:
                amount = row.get('amount', 0) or 0
                total += amount
                output += f"- {row.get('paid_at', 'N/A')}: {amount:,}원 ({row.get('method', 'N/A')})\n"
                output += f"  - 요청: {row.get('request_id', 'N/A')}, 상태: {row.get('status', 'N/A')}\n"

            output += f"\n**총 결제 금액: {total:,}원**\n"
            return output

        except Exception as e:
            logger.error(f"tap_payment_history error: {e}")
            return f"결제 내역 조회 중 오류 발생: {str(e)}"

    @tool
    def tap_feedback_stats() -> str:
        """
        서비스 피드백 통계를 조회합니다.

        Returns:
            피드백 통계 정보
        """
        try:
            cypher = """
            MATCH (fb:Feedback)
            RETURN fb.category as category, avg(fb.rating) as avg_rating, count(fb) as count
            ORDER BY avg_rating DESC
            """

            result = graphrag_service.execute_cypher(cypher)

            if not result:
                return "피드백 정보가 없습니다."

            output = "## 피드백 통계\n\n"
            for row in result:
                rating = row.get('avg_rating', 0)
                stars = "★" * int(round(rating)) + "☆" * (5 - int(round(rating)))
                output += f"- **{row.get('category', 'N/A')}**: {rating:.1f} {stars} ({row.get('count', 0)}건)\n"

            return output

        except Exception as e:
            logger.error(f"tap_feedback_stats error: {e}")
            return f"피드백 통계 조회 중 오류 발생: {str(e)}"

    return [
        tap_call_status,
        tap_eta_query,
        tap_booking_status,
        tap_payment_history,
        tap_feedback_stats,
    ]
