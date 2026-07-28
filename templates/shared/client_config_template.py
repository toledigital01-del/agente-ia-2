"""
client_config.py — Localiza e carrega a configuração do cliente em execução.

Este módulo é o que torna o agente multi-cliente: o programa é único e
compartilhado, e tudo que varia de um cliente para outro (prompt de vendas,
produto, chaves, número de WhatsApp, banco de leads) vive numa pasta própria.

Layout esperado:
    /opt/agente/                     ← o programa (este código), um só
    /opt/clientes/<cliente>/
        config.json                  ← configuração daquele cliente
        dados.sqlite                 ← leads e conversas daquele cliente
        watcher_state.json
        watcher.log

Qual cliente carregar vem da variável de ambiente AGENTE_CLIENTE, definida
pelo systemd em `agente@<cliente>.service`. Rodando na mão:

    AGENTE_CLIENTE=agil-persianas python3 watcher.py

Se AGENTE_CLIENTE não estiver definida, cai no layout antigo de instalação
única (~/meu-agente + ~/.meu-agente/config.json) para não quebrar setups
existentes.
"""

import json
import os
import sys
from pathlib import Path

CLIENTS_ROOT = Path(os.environ.get("AGENTE_CLIENTES_DIR", "/opt/clientes"))
CLIENT_NAME = os.environ.get("AGENTE_CLIENTE", "").strip()


def _resolve_paths():
    """Descobre a pasta do cliente e o arquivo de configuração."""
    if CLIENT_NAME:
        client_dir = CLIENTS_ROOT / CLIENT_NAME
        return client_dir, client_dir / "config.json"
    # Retrocompatibilidade: instalação única (formato antigo)
    return Path.home() / "meu-agente", Path.home() / ".meu-agente" / "config.json"


CLIENT_DIR, CONFIG_PATH = _resolve_paths()


def _load():
    if not CONFIG_PATH.exists():
        print(f"[client_config] ERRO: configuração não encontrada em {CONFIG_PATH}")
        print("[client_config] Defina AGENTE_CLIENTE=<nome> ou crie o arquivo.")
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[client_config] ERRO ao ler {CONFIG_PATH}: {e}")
        sys.exit(1)


CONFIG = _load()
CLIENT_DIR.mkdir(parents=True, exist_ok=True)

# Caminhos derivados — cada cliente tem os seus, isolados
DB_PATH = CLIENT_DIR / "dados.sqlite"
STATE_FILE = CLIENT_DIR / "watcher_state.json"
LOG_FILE = CLIENT_DIR / "watcher.log"


def get(key: str, default=None):
    """Lê um valor da configuração do cliente."""
    return CONFIG.get(key, default)


def require(key: str):
    """Lê um valor obrigatório; encerra com mensagem clara se estiver faltando."""
    value = CONFIG.get(key)
    if value in (None, ""):
        print(f"[client_config] ERRO: '{key}' não definido em {CONFIG_PATH}")
        sys.exit(1)
    return value


def label() -> str:
    """Identificação do cliente para logs."""
    return CLIENT_NAME or get("product_name", "instalação-única")
