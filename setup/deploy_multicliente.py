#!/usr/bin/env python3
"""
deploy_multicliente.py — Publica o agente no formato multi-cliente.

Estrutura criada no servidor:

    /opt/agente/                  ← O PROGRAMA, um só, compartilhado
        client_config.py
        agent_core.py
        sessions.py
        agent.py
        watcher.py

    /opt/clientes/<cliente>/      ← A "cápsula" de cada cliente
        config.json
        dados.sqlite
        watcher_state.json
        watcher.log

Cada cliente roda como `agente@<cliente>.service`, isolado dos demais.
Corrigir um bug no programa passa a valer para todos de uma vez.

Uso:
    python setup/deploy_multicliente.py            # publica o programa
    python setup/deploy_multicliente.py --cliente agil-persianas
"""

import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PROGRAM_DIR = "/opt/agente"
CLIENTS_DIR = "/opt/clientes"

SYSTEMD_UNIT = """[Unit]
Description=Agente de Vendas WhatsApp - cliente %i
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
Environment=AGENTE_CLIENTE=%i
Environment=AGENTE_CLIENTES_DIR=/opt/clientes
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/opt/agente
ExecStart=/usr/bin/python3 /opt/agente/watcher.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/clientes/%i/service.log
StandardError=append:/opt/clientes/%i/service.log

[Install]
WantedBy=multi-user.target
"""


def build_program_files() -> dict:
    """Monta os arquivos do programa a partir dos templates, sem placeholders de cliente."""
    shared = REPO / "templates" / "shared"
    whatsapp = REPO / "templates" / "whatsapp"

    client_config = (shared / "client_config_template.py").read_text(encoding="utf-8")
    agent_core = (shared / "agent_core_template.py").read_text(encoding="utf-8")
    sessions = (shared / "sessions_template.py").read_text(encoding="utf-8")
    agent = (whatsapp / "agent_template.py").read_text(encoding="utf-8")
    watcher = (whatsapp / "watcher_template.py").read_text(encoding="utf-8")

    # Os módulos passam a viver lado a lado em /opt/agente
    agent = agent.replace(
        'sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))',
        'sys.path.insert(0, str(Path(__file__).parent))'
    )
    for mod in (agent, watcher):
        pass
    agent = agent.replace("agent_core_template", "agent_core").replace("sessions_template", "sessions")
    watcher = watcher.replace("agent_core_template", "agent_core").replace("sessions_template", "sessions")

    return {
        "client_config.py": client_config,
        "agent_core.py": agent_core,
        "sessions.py": sessions,
        "agent.py": agent,
        "watcher.py": watcher,
    }


def main():
    parser = argparse.ArgumentParser(description="Publica o agente multi-cliente")
    parser.add_argument("--print-only", action="store_true",
                        help="Só mostra os arquivos que seriam publicados")
    args = parser.parse_args()

    files = build_program_files()
    print("=" * 60)
    print("Arquivos do programa compartilhado (/opt/agente):")
    for name, content in files.items():
        print(f"  {name:20s} {len(content):>7,} bytes")
    print("=" * 60)
    print("\nUnidade systemd (agente@.service):")
    print(SYSTEMD_UNIT)

    if args.print_only:
        return

    print("Para publicar no servidor, use o script de deploy com paramiko.")
    print(f"Programa -> {PROGRAM_DIR}")
    print(f"Clientes -> {CLIENTS_DIR}/<nome>/config.json")


if __name__ == "__main__":
    main()
