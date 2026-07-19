import re
import uuid
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src import models
from src.cce import DEFAULT_CHALLENGE_BANK

async def seed_challenge_bank(db: AsyncSession) -> int:
    """
    Insere o banco de desafios padrão (CCE) para as KUs existentes no banco.
    Idempotente: só insere desafios de KUs presentes e que ainda não os possuem.
    Retorna o número de desafios inseridos.
    """
    inserted = 0
    for ku_id, challenges in DEFAULT_CHALLENGE_BANK.items():
        ku = await db.get(models.KnowledgeUnit, ku_id)
        if not ku:
            continue
        existing = await db.execute(
            select(models.Challenge.id).where(models.Challenge.ku_id == ku_id)
        )
        if existing.first():
            continue
        for ch in challenges:
            db.add(models.Challenge(ku_id=ku_id, **ch))
            inserted += 1
    await db.commit()
    return inserted

RAW_CURRICULUM = """
10655 - ADMINISTRAÇÃO DA PRODUÇÃO 2025/2 40 AE* Aprovado DOUGLAS ALMENDRO - Doutorado
5748 - AMBIENTAÇÃO DIGITAL 2025/2 10 ****** Pendente ADEMIR BENEDITO DOS SANTOS JUNIOR - Especialização
9588 - ATIVIDADE DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS PARA TRANSFORMAR O EU, O OUTRO E A SOCIEDADE 2025/2 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
12673 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO I 2025/2 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10659 - GEOMETRIA ANALÍTICA E ÁLGEBRA LINEAR 2025/2 40 ****** Pendente CARLOS EDUARDO BONANCEA - Doutorado
3542 - GESTÃO DE TECNOLOGIA E INOVAÇÃO PARA ENGENHARIA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11010 - LEGISLAÇÃO E ÉTICA PROFISSIONAL 2025/2 40 AE* Aprovado DOUGLAS ALMENDRO - Doutorado
886 - LÍNGUA BRASILEIRA DE SINAIS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11009 - ORIENTAÇÃO A OBJETOS 2025/2 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11212 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO I 2025/2 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3543 - TÓPICOS DE CIÊNCIAS EXATAS 2025/2 60 ****** Pendente VICTOR BARBOSA FELIX - Doutorado
11099 - ALGORITMOS DE COMPUTAÇÃO **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11061 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO I **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11012 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO II **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10666 - CÁLCULO DIFERENCIAL E INTEGRAL I **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10578 - DESENHO TÉCNICO **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10667 - FÍSICA GERAL E EXPERIMENTAL I **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10669 - FÍSICA GERAL E EXPERIMENTAL II **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11174 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO II **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1393 - QUÍMICA APLICADA **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11082 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO II **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11013 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO III **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10692 - CÁLCULO DIFERENCIAL E INTEGRAL II **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10690 - CÁLCULO NUMÉRICO **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11102 - FENÔMENOS DE TRANSPORTE **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11105 - MECÂNICA GERAL **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3802 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO III **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11216 - TÉCNICAS DE PROGRAMAÇÃO EM LINGUAGEM C **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11089 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO III **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11019 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO IV **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3800 - CIRCUITOS LÓGICOS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11106 - ENGENHARIA DE SOFTWARE **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3733 - ESTRUTURAS DE DADOS LINEARES **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3801 - FUNDAMENTOS DE MICROPROCESSADORES **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11108 - INTERNET DAS COISAS E APLICAÇÕES **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11175 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO IV **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11107 - REDES DE COMPUTADORES **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1446 - SISTEMAS OPERACIONAIS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11092 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO IV **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10683 - AUTOMAÇÃO DA MANUFATURA **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11020 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO V **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3554 - ELETRICIDADE **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11170 - ELETRÔNICA GERAL **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3706 - ESTRUTURAS DE DADOS NÃO-LINEARES **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
2001 - PESQUISA OPERACIONAL **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11176 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO V **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3793 - SEGURANÇA DE SISTEMAS COMPUTACIONAIS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11093 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO V **** 30 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11022 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VI **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11171 - BANCO DE DADOS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
5255 - COMPUTABILIDADE E COMPLEXIDADE DE ALGORITMOS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
2065 - ELETRÔNICA DIGITAL **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1985 - INTELIGÊNCIA ARTIFICIAL **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1983 - MICROPROCESSADORES **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11179 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO VI **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11172 - TÓPICOS ESPECIAIS EM ENGENHARIA DE COMPUTAÇÃO I **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11094 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VI **** 30 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11026 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VII **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11183 - LINGUAGENS FORMAIS E AUTÔMATOS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11180 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO VII **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3791 - PROCESSAMENTO DE SINAIS E IMAGENS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11229 - SISTEMAS DE TEMPO REAL **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3792 - TEORIA DOS GRAFOS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11173 - TÓPICOS ESPECIAIS EM ENGENHARIA DE COMPUTAÇÃO II **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1988 - TÓPICOS ESPECIAIS EM ROBÓTICA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
2067 - ANÁLISE DE CIRCUITOS ELÉTRICOS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11095 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VII **** 30 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11055 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VIII **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3788 - COMPILADORES E INTERPRETADORES **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3785 - COMPUTAÇÃO PARALELA E DISTRIBUÍDA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10062 - METODOLOGIA DE PESQUISA 2025/2 40 AE* Aprovado DOUGLAS ALMENDRO - Doutorado
11189 - MODELOS PROBABILÍSTICOS APLICADOS À ENGENHARIA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11181 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO VIII **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11190 - ROBÓTICA APLICADA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11191 - TRABALHO DE CONCLUSÃO DE CURSO EM ENGENHARIA DE COMPUTAÇÃO I **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11096 - ATIVIDADES DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO VIII **** 30 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11056 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO IX **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11182 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO IX **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3888 - PROGRAMAÇÃO PARA DISPOSITIVOS MÓVEIS **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11205 - PROJETO INTEGRADOR TRANSDISCIPLINAR EM ENGENHARIA DE COMPUTAÇÃO **** 20 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11201 - SISTEMAS CLIENTE/SERVIDOR **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
3803 - SISTEMAS EMBARCADOS **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
11192 - TRABALHO DE CONCLUSÃO DE CURSO EM ENGENHARIA DE COMPUTAÇÃO II **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
6977 - ATIVIDADE DE EXTENSÃO: INTEGRAÇÃO DE COMPETÊNCIAS PARA TRANSFORMAR O EU **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10965 - AVALIAÇÃO INTEGRADA DE COMPETÊNCIAS EM ENGENHARIA DE COMPUTAÇÃO **** 0 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10641 - CIÊNCIAS ECONÔMICAS E ADMINISTRATIVAS 2025/2 40 AE* Aprovado DOUGLAS ALMENDRO - Doutorado
10102 - ERGONOMIA E SEGURANÇA DO TRABALHO **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10265 - GESTÃO AMBIENTAL E RESPONSABILIDADE SOCIAL 2025/2 40 AE* Aprovado DOUGLAS ALMENDRO - Doutorado
927 - LÍNGUA PORTUGUESA **** 40 ****** Pendente DOUGLAS ALMENDRO - Doutorado
1151 - ORGANIZAÇÃO E ARQUITETURA DE COMPUTADORES **** 60 ****** Pendente DOUGLAS ALMENDRO - Doutorado
10958 - PLANO DE ACOMPANHAMENTO DE CARREIRA EM ENGENHARIA DE COMPUTAÇÃO **** 10 ****** Pendente DOUGLAS ALMENDRO - Doutorado
"""

async def seed_user_curriculum(db: AsyncSession):
    # Regex to capture id, title, period, hours
    # e.g., "11106 - ENGENHARIA DE SOFTWARE **** 60 ****** Pendente"
    pattern = re.compile(r'(\d+)\s+-\s+(.*?)\s+(2025/2|\*\*\*\*)\s+(\d+)')
    
    matches = pattern.findall(RAW_CURRICULUM)
    
    all_ku_ids = []
    
    for match in matches:
        code = match[0]
        title = match[1].strip()
        hours = int(match[3])
        
        # We'll skip some administrative tasks from KUs
        if "AVALIAÇÃO INTEGRADA" in title or "PLANO DE ACOMPANHAMENTO" in title or "ATIVIDADE DE EXTENSÃO" in title:
            continue
            
        ku_id = f"ku:ce:{code}"
        all_ku_ids.append(ku_id)
        
        # Create Knowledge Unit
        ku = models.KnowledgeUnit(
            id=ku_id,
            title=title,
            domain="Computer Engineering",
            concept=title,
            level="intermediate" if hours > 40 else "foundational",
            definition=f"Estudo fundamental de {title.title()} abordando os conceitos primários com carga horária de {hours} horas.",
            element_interactivity=6 if hours > 40 else 4,
            domain_decay_rate=0.03
        )
        db.add(ku)
        
        # Create Dummy Study Materials (Base Infinita)
        material1 = models.StudyMaterial(
            ku_id=ku_id,
            title=f"Vídeo Aula: Introdução a {title.title()}",
            type="video",
            url=f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}",
            quality_score=0.9
        )
        material2 = models.StudyMaterial(
            ku_id=ku_id,
            title=f"Artigo e PDF: Fundamentos de {title.title()}",
            type="article",
            url=f"https://scholar.google.com/scholar?q={title.replace(' ', '+')}",
            quality_score=0.95
        )
        db.add(material1)
        db.add(material2)

    await db.flush()
    
    # Simple Heuristic for prerequisites
    # "CÁLCULO I" -> "CÁLCULO II"
    # "ESTRUTURAS DE DADOS LINEARES" -> "NÃO-LINEARES"
    
    def add_prereq(source_title_part, target_title_part):
        source = next((m for m in matches if source_title_part in m[1]), None)
        target = next((m for m in matches if target_title_part in m[1]), None)
        if source and target:
            db.add(models.KURelation(
                source_id=f"ku:ce:{source[0]}",
                target_id=f"ku:ce:{target[0]}",
                type="prerequisite",
                weight=1.0
            ))
            
    add_prereq("CÁLCULO DIFERENCIAL E INTEGRAL I", "CÁLCULO DIFERENCIAL E INTEGRAL II")
    add_prereq("FÍSICA GERAL E EXPERIMENTAL I", "FÍSICA GERAL E EXPERIMENTAL II")
    add_prereq("ESTRUTURAS DE DADOS LINEARES", "ESTRUTURAS DE DADOS NÃO-LINEARES")
    add_prereq("ALGORITMOS DE COMPUTAÇÃO", "ESTRUTURAS DE DADOS LINEARES")
    add_prereq("TÉCNICAS DE PROGRAMAÇÃO EM LINGUAGEM C", "ESTRUTURAS DE DADOS LINEARES")
    add_prereq("ORIENTAÇÃO A OBJETOS", "ENGENHARIA DE SOFTWARE")
    add_prereq("BANCO DE DADOS", "SISTEMAS CLIENTE/SERVIDOR")
    add_prereq("GEOMETRIA ANALÍTICA E ÁLGEBRA LINEAR", "PROCESSAMENTO DE SINAIS E IMAGENS")
    add_prereq("CIRCUITOS LÓGICOS", "ORGANIZAÇÃO E ARQUITETURA DE COMPUTADORES")
    add_prereq("ORGANIZAÇÃO E ARQUITETURA DE COMPUTADORES", "SISTEMAS OPERACIONAIS")
    
    # Create an overarching Mission for the whole course
    mission = models.Mission(
        id="mission:ce:graduation",
        label="Engenharia de Computação Completa",
        required_kus=all_ku_ids,
        terminal_threshold=0.85,
        critical_kus=all_ku_ids[:5], # First few are critical just as an example
        critical_threshold=0.90
    )
    db.add(mission)
    
    await db.commit()
