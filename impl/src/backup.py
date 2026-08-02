"""
Backup lógico do banco para armazenamento de objetos.

Por que não o backup do Railway: o plano da conta permite zero backups de
volume (`maxBackupsCount: 0`). O banco guarda o progresso de aprendizagem, que
não se recupera reimportando nada — precisa de cópia própria.

Por que exportação lógica em vez de `pg_dump`: o `pg_dump` precisa de versão
igual ou maior que a do servidor, e a imagem passaria a depender do repositório
do PostgreSQL só para isso. A exportação por SQLAlchemy funciona com qualquer
versão do servidor e, de quebra, permite a verificação que importa — contar as
linhas gravadas e conferir com a origem. O esquema não vem no arquivo porque
quem o reconstrói é o Alembic; restaurar é `alembic upgrade head` e depois
carregar os dados.

Regra herdada de tools/backup.py: **backup não verificado não é backup**. Cada
cópia é relida do armazenamento depois de enviada e as contagens são conferidas
tabela por tabela antes de o backup ser declarado válido.

Uso pela linha de comando:
    python -m src.backup criar
    python -m src.backup listar
    python -m src.backup verificar <chave>
"""
import datetime
import decimal
import gzip
import io
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from src.database import AsyncSessionLocal
from src.models import Base

PREFIXO = "postgres/"
RETENCAO_DIARIA = int(os.getenv("BACKUP_RETENCAO", "14"))


def _cliente():
    """
    Cliente S3 do bucket. Devolve None quando não há credencial configurada —
    ausência de bucket não pode derrubar o worker; vira aviso no log.
    """
    chave = os.getenv("BACKUP_S3_ACCESS_KEY_ID", "").strip()
    segredo = os.getenv("BACKUP_S3_SECRET_ACCESS_KEY", "").strip()
    endpoint = os.getenv("BACKUP_S3_ENDPOINT", "").strip()
    balde = os.getenv("BACKUP_S3_BUCKET", "").strip()
    if not (chave and segredo and endpoint and balde):
        return None, None
    try:
        import boto3
    except ImportError:
        return None, None
    cliente = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=chave,
        aws_secret_access_key=segredo,
        region_name=os.getenv("BACKUP_S3_REGION", "auto"),
    )
    return cliente, balde


def _serializar(valor: Any) -> Any:
    """JSON não conhece UUID, datetime nem Decimal; a restauração desfaz."""
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return {"__tipo__": "datetime", "v": valor.isoformat()}
    if isinstance(valor, uuid.UUID):
        return {"__tipo__": "uuid", "v": str(valor)}
    if isinstance(valor, decimal.Decimal):
        return {"__tipo__": "decimal", "v": str(valor)}
    if isinstance(valor, bytes):
        return {"__tipo__": "bytes", "v": valor.hex()}
    return valor


async def _exportar() -> tuple:
    """
    Percorre as tabelas na ordem de dependência e devolve (conteúdo, contagens).
    A ordem importa: restaurar fora dela viola chave estrangeira.
    """
    linhas_saida: List[str] = []
    contagens: Dict[str, int] = {}

    async with AsyncSessionLocal() as db:
        for tabela in Base.metadata.sorted_tables:
            total = 0
            resultado = await db.execute(select(tabela))
            for registro in resultado.mappings():
                linhas_saida.append(json.dumps(
                    {"__tabela__": tabela.name,
                     "d": {k: _serializar(v) for k, v in dict(registro).items()}},
                    ensure_ascii=False,
                ))
                total += 1
            contagens[tabela.name] = total

    return "\n".join(linhas_saida), contagens


async def criar() -> Dict[str, Any]:
    """
    Cria o backup, envia e VERIFICA relendo o objeto enviado. Só devolve
    sucesso se as contagens do arquivo remoto baterem com as da origem.
    """
    cliente, balde = _cliente()
    conteudo, contagens = await _exportar()
    total = sum(contagens.values())

    agora = datetime.datetime.now(datetime.timezone.utc)
    chave = f"{PREFIXO}{agora:%Y-%m-%dT%H-%M-%SZ}.jsonl.gz"

    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
        gz.write(conteudo.encode("utf-8"))
    bruto = buffer.getvalue()

    if cliente is None:
        return {"status": "sem_armazenamento", "linhas": total, "bytes": len(bruto),
                "erro": "credenciais do bucket ausentes — backup NÃO foi guardado"}

    manifesto = {"criado_em": agora.isoformat(), "linhas": total,
                 "contagens": contagens, "bytes": len(bruto)}
    cliente.put_object(Bucket=balde, Key=chave, Body=bruto,
                       Metadata={"linhas": str(total)})
    cliente.put_object(Bucket=balde, Key=chave + ".manifesto.json",
                       Body=json.dumps(manifesto, ensure_ascii=False).encode("utf-8"))

    conferido = verificar(chave, contagens_esperadas=contagens)
    if not conferido["ok"]:
        return {"status": "falhou_verificacao", "chave": chave, **conferido}

    removidos = _podar(cliente, balde)
    return {"status": "ok", "chave": chave, "linhas": total,
            "bytes": len(bruto), "tabelas": len(contagens), "removidos": removidos}


def verificar(chave: str, contagens_esperadas: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    Relê o objeto do bucket, descomprime e reconta linha por tabela. É isto
    que separa "o upload retornou 200" de "existe um backup restaurável".
    """
    cliente, balde = _cliente()
    if cliente is None:
        return {"ok": False, "erro": "credenciais do bucket ausentes"}

    try:
        obj = cliente.get_object(Bucket=balde, Key=chave)
        dados = gzip.decompress(obj["Body"].read()).decode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "erro": f"não foi possível reler: {e}"}

    lidas: Dict[str, int] = {}
    for linha in dados.splitlines():
        if not linha.strip():
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError as e:
            return {"ok": False, "erro": f"linha corrompida no arquivo: {e}"}
        lidas[registro["__tabela__"]] = lidas.get(registro["__tabela__"], 0) + 1

    if contagens_esperadas is None:
        return {"ok": True, "contagens": lidas, "linhas": sum(lidas.values())}

    divergencias = {
        t: {"origem": n, "backup": lidas.get(t, 0)}
        for t, n in contagens_esperadas.items() if lidas.get(t, 0) != n
    }
    if divergencias:
        return {"ok": False, "erro": "contagem divergente", "divergencias": divergencias}
    return {"ok": True, "contagens": lidas, "linhas": sum(lidas.values())}


def listar() -> List[Dict[str, Any]]:
    cliente, balde = _cliente()
    if cliente is None:
        return []
    resposta = cliente.list_objects_v2(Bucket=balde, Prefix=PREFIXO)
    itens = [
        {"chave": o["Key"], "bytes": o["Size"], "em": o["LastModified"].isoformat()}
        for o in resposta.get("Contents", []) if not o["Key"].endswith(".manifesto.json")
    ]
    return sorted(itens, key=lambda i: i["chave"], reverse=True)


def _podar(cliente, balde) -> int:
    """Mantém os RETENCAO_DIARIA mais recentes. Backup infinito vira custo."""
    itens = listar()
    velhos = itens[RETENCAO_DIARIA:]
    for item in velhos:
        cliente.delete_object(Bucket=balde, Key=item["chave"])
        cliente.delete_object(Bucket=balde, Key=item["chave"] + ".manifesto.json")
    return len(velhos)


if __name__ == "__main__":
    import argparse
    import asyncio

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("comando", choices=["criar", "listar", "verificar"])
    p.add_argument("chave", nargs="?")
    args = p.parse_args()

    if args.comando == "criar":
        print(json.dumps(asyncio.run(criar()), ensure_ascii=False, indent=2))
    elif args.comando == "listar":
        for i in listar():
            print(f"{i['em']}  {i['bytes']:>10,} B  {i['chave']}")
    else:
        if not args.chave:
            p.error("verificar exige a chave do backup")
        print(json.dumps(verificar(args.chave), ensure_ascii=False, indent=2))
