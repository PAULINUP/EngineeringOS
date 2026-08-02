import os
import sys
# Adiciona o diretório 'impl' ao path para conseguir importar 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import urllib.request
import urllib.error
from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import Challenge

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip(' \'"\n\r')

def sync_gemini_call(prompt: str, expected_answer: str) -> bool:
    if not GEMINI_API_KEY:
        print("ERRO: GEMINI_API_KEY não configurada no ambiente.")
        return True # Default to keep if no API key
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    
    system_instruction = "Você é um auditor rigoroso de banco de dados educacional encarregado de limpar problemas corrompidos por web scraping."
    
    user_prompt = f"""
Avalie o seguinte problema e seu gabarito numérico. 
Muitos problemas foram corrompidos no processo de extração (ex: alternativas do enunciado grudaram no gabarito, ou o texto perdeu os dígitos).
Responda APENAS "SIM" se o problema for bem formulado e o gabarito fizer sentido matematicamente exato para a pergunta. 
Responda "NAO" se o problema parecer corrompido, incompleto, ou se o gabarito numérico não fizer lógica exata com a pergunta apresentada (ex: gabarito '5125' para a pergunta '0, 2/3, 5, 8.1, 125' é LIXO).

Problema: {prompt}
Gabarito Esperado: {expected_answer}
"""
    
    data = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 10}
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode("utf-8"))
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
            return "SIM" in text
        except KeyError:
            print(f"\n[Aviso] Resposta bloqueada ou sem texto (safety filter?). Retorno: {json.dumps(result)}")
            return True
    except urllib.error.HTTPError as e:
        print(f"Erro na API Gemini: HTTP Error {e.code}: {e.reason}")
        try:
            print(f"Detalhes: {e.read().decode('utf-8')}")
        except:
            pass
        return True
    except Exception as e:
        print(f"Erro na API Gemini: {e}")
        return True # Se a API falhar, assume válido por precaução

async def evaluate_challenge(prompt: str, expected_answer: str) -> bool:
    await asyncio.sleep(3) # Evita o limite de 15 requests/minuto ou limits do plano
    return await asyncio.to_thread(sync_gemini_call, prompt, expected_answer)

async def run_curation(dry_run=True):
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY não definida. Defina export GEMINI_API_KEY='sua_chave' antes de rodar.")
        return

    print(f"Iniciando curadoria de desafios... Modo DRY RUN: {dry_run}")
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Challenge))
        challenges = res.scalars().all()
        print(f"Total de desafios encontrados: {len(challenges)}")
        
        deleted = 0
        for i, ch in enumerate(challenges):
            if ch.answer_type != "numeric":
                continue
                
            # Verifica apenas com a API
            is_valid = await evaluate_challenge(ch.prompt, ch.expected_answer)
            
            if not is_valid:
                print(f"[{i+1}/{len(challenges)}] ⚠️ SUSPEITO -> Quarentena do desafio ID: {ch.id}")
                print(f"   Prompt: {ch.prompt[:150]}...")
                print(f"   Gabarito: {ch.expected_answer}")
                print("-" * 50)
                if not dry_run:
                    # Quarentena, não exclusão: o julgamento é de um modelo de
                    # linguagem, falível, e evidências já registradas apontam
                    # para este desafio. Reverter com repair_challenges.py --restore.
                    ch.active = False
                deleted += 1
            else:
                if (i + 1) % 50 == 0:
                    print(f"[{i+1}/{len(challenges)}] ...validando...")
                    
            if not dry_run and deleted > 0 and deleted % 50 == 0:
                await db.commit()
                print("   [DB] Commit intermediário realizado.")
                
        if not dry_run:
            await db.commit()
            print(f"\n✅ Curadoria concluída. {deleted} desafios postos em QUARENTENA.")
        else:
            print(f"\n✅ DRY RUN concluído. {deleted} desafios SERIAM postos em quarentena.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Aplica a quarentena no banco de dados.")
    args = parser.parse_args()
    
    asyncio.run(run_curation(dry_run=not args.execute))
