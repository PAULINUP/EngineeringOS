"""
Memory Framework — EngineeringOS

Responsável pela persistência e auditoria do estado cognitivo.
Todo o estado é gerido exclusivamente pelo banco de dados relacional (PostgreSQL).
Nenhuma operação de I/O em ficheiros JSON é realizada.
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("memory_framework")


class MemoryManager:
    """
    Gere snapshots do estado do sistema para fins de auditoria.
    Os dados são lidos directamente do PostgreSQL — sem cache JSON intermediário.
    """

    async def get_learner_snapshot(self, session: AsyncSession, learner_id: str) -> dict:
        """Retorna um snapshot completo do estado de um aluno a partir do banco relacional."""
        result = await session.execute(
            text("SELECT id, name, created_at FROM learners WHERE id = :lid"),
            {"lid": learner_id},
        )
        row = result.mappings().first()
        if not row:
            return {"error": f"Learner {learner_id} não encontrado"}
        return dict(row)

    async def get_evidence_snapshot(self, session: AsyncSession, learner_id: str) -> list:
        """Retorna todas as evidências de um aluno a partir do banco relacional."""
        result = await session.execute(
            text(
                "SELECT id, ku_id, type, confidence, status, timestamp "
                "FROM evidence_records WHERE learner_id = :lid ORDER BY timestamp DESC"
            ),
            {"lid": learner_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_full_state(self, session: AsyncSession) -> dict:
        """
        Retorna um dicionário com o número de learners, evidências e KUs no banco.
        Utilizado para telemetria e health-check — sem ficheiros locais.
        """
        counts = {}
        for table in ("learners", "evidence_records", "knowledge_units"):
            try:
                res = await session.execute(text(f"SELECT COUNT(*) AS cnt FROM {table}"))
                counts[table] = res.scalar_one()
            except Exception as e:
                logger.warning("Tabela %s inacessível: %s", table, e)
                counts[table] = -1
        return counts
