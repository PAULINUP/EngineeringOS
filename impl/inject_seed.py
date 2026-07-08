import asyncio
from sqlalchemy import select, delete
from src.database import AsyncSessionLocal
from src.models import KnowledgeUnit, Skill, Mission, KURelation
from src.eos_parser import parse_dsl_content

import sys

def title_from_id(did: str) -> str:
    parts = did.split('.')
    if len(parts) >= 2:
        return parts[1].replace("_", " ").title()
    return did

async def inject(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        dsl = f.read()

    declarations = parse_dsl_content(dsl)

    async with AsyncSessionLocal() as db:
        # Apagar currículo antigo se necessário ou apenas adicionar?
        # O ideal é não apagar para manter a física se existir, mas vamos garantir que não há conflito de IDs
        
        ku_objs = {}
        prereqs_map = {}
        enables_map = {}

        for dec in declarations:
            dtype = dec.get("type")
            did = dec.get("id")
            data = dec.get("data", {})
            
            if dtype == "SKILL":
                # Check if exists
                res = await db.execute(select(Skill).where(Skill.id == did))
                if not res.scalar_one_or_none():
                    skill = Skill(id=did, label=data.get("label", title_from_id(did)), domain=data.get("domain", "matematica_base"))
                    db.add(skill)

            elif dtype == "KNOWLEDGE":
                level = dec.get("level", "foundational").lower()
                res = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.id == did))
                ku = res.scalar_one_or_none()
                if not ku:
                    ku = KnowledgeUnit(
                        id=did,
                        title=title_from_id(did),
                        domain=data.get("domain", "matematica_base"),
                        concept=did.split(".")[1] if len(did.split(".")) > 1 else did,
                        level=level,
                        definition=data.get("definition", ""),
                        element_interactivity=data.get("interactivity", 4),
                        domain_decay_rate=data.get("decay_rate", 0.05),
                        sources=[data.get("source")] if "source" in data else []
                    )
                    db.add(ku)
                else:
                    # Update fields
                    ku.definition = data.get("definition", ku.definition)
                    ku.level = level
                    ku.element_interactivity = data.get("interactivity", ku.element_interactivity)
                ku_objs[did] = ku

                if "requires" in data:
                    prereqs_map[did] = data["requires"]
                if "enables" in data:
                    enables_map[did] = data["enables"]

            elif dtype == "MISSION":
                res = await db.execute(select(Mission).where(Mission.id == did))
                if not res.scalar_one_or_none():
                    mission = Mission(
                        id=did,
                        label=data.get("label", title_from_id(did)),
                        required_kus=data.get("requires", []),
                        terminal_threshold=data.get("threshold", 0.85),
                        critical_kus=data.get("critical", []),
                        critical_threshold=0.90,
                        cost_weights=data.get("cost", {"alpha": 0.4, "beta": 0.3, "gamma": 0.3})
                    )
                    db.add(mission)
        
        await db.flush()

        # Tratar Relações (Prerequisites)
        for target_id, reqs in prereqs_map.items():
            for source_id in reqs:
                # Check relation
                rel_res = await db.execute(
                    select(KURelation).where(KURelation.source_id == source_id, KURelation.target_id == target_id, KURelation.type == "prerequisite")
                )
                if not rel_res.scalar_one_or_none():
                    db.add(KURelation(source_id=source_id, target_id=target_id, type="prerequisite", weight=1.0))
        
        await db.commit()
        print("Injeção do currículo concluída com sucesso!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python inject_seed.py <caminho_do_arquivo.eos>")
        sys.exit(1)
    asyncio.run(inject(sys.argv[1]))
