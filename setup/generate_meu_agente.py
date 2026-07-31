#!/usr/bin/env python3
"""
generate_meu_agente.py — Gera os arquivos finais de execução em ~/meu-agente/ (Etapa 6)

Suporta dois modos:
  --modo watcher  (padrão) — Evolution API, polling local
  --modo webhook            — Meta Cloud API, webhook HTTPS
"""
import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent


def fix_imports(content: str) -> str:
    """Ajusta imports dos templates para funcionarem em ~/meu-agente/ (módulos lado a lado)."""
    content = content.replace(
        'sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))',
        'sys.path.insert(0, str(Path(__file__).parent))'
    )
    content = content.replace("agent_core_template", "agent_core")
    content = content.replace("sessions_template", "sessions")
    return content


def load_config() -> dict:
    config_path = Path.home() / ".meu-agente" / "config.json"
    if not config_path.exists():
        print("❌ ~/.meu-agente/config.json não encontrado!")
        sys.exit(1)
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Erro ao ler config.json: {e}")
        sys.exit(1)


def generate_watcher_mode(dest_dir: Path, cfg: dict):
    """Gera watcher.py para modo Evolution API."""
    watcher_path = REPO / "templates" / "whatsapp" / "watcher_template.py"
    if not watcher_path.exists():
        print(f"❌ Template não encontrado: {watcher_path}")
        sys.exit(1)

    print("  Gerando watcher.py...")
    content = fix_imports(watcher_path.read_text(encoding="utf-8"))
    (dest_dir / "watcher.py").write_text(content, encoding="utf-8")
    print("    ✅ watcher.py gerado.")


def generate_webhook_mode(dest_dir: Path, cfg: dict):
    """Gera webhook_server.py para modo Meta Cloud API."""
    server_path = REPO / "templates" / "whatsapp" / "webhook_server_template.py"
    if not server_path.exists():
        print(f"❌ Template não encontrado: {server_path}")
        sys.exit(1)

    print("  Gerando webhook_server.py...")
    content = fix_imports(server_path.read_text(encoding="utf-8"))
    (dest_dir / "webhook_server.py").write_text(content, encoding="utf-8")
    print("    ✅ webhook_server.py gerado.")


def main():
    parser = argparse.ArgumentParser(description="Gera os arquivos do agente em ~/meu-agente/")
    parser.add_argument("--modo", choices=["watcher", "webhook"], default="watcher",
                        help="watcher = Evolution API (padrão) | webhook = Meta Cloud API")
    args = parser.parse_args()

    print("=" * 60)
    print(f"Geração dos Arquivos do Agente (modo: {args.modo})")
    print("=" * 60)

    cfg = load_config()

    dest_dir = Path.home() / "meu-agente"
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Destino: {dest_dir}")

    shared = REPO / "templates" / "shared"
    whatsapp = REPO / "templates" / "whatsapp"

    # ── client_config.py ──────────────────────────────────────────────────────
    print("  Copiando client_config.py...")
    content = (shared / "client_config_template.py").read_text(encoding="utf-8")
    (dest_dir / "client_config.py").write_text(content, encoding="utf-8")
    print("    ✅ client_config.py copiado.")

    # ── agent_core.py ─────────────────────────────────────────────────────────
    print("  Gerando agent_core.py...")
    content = (shared / "agent_core_template.py").read_text(encoding="utf-8")
    content = fix_imports(content)
    (dest_dir / "agent_core.py").write_text(content, encoding="utf-8")
    print("    ✅ agent_core.py gerado.")

    # ── sessions.py ───────────────────────────────────────────────────────────
    print("  Gerando sessions.py...")
    content = (shared / "sessions_template.py").read_text(encoding="utf-8")
    content = fix_imports(content)
    (dest_dir / "sessions.py").write_text(content, encoding="utf-8")
    print("    ✅ sessions.py gerado.")

    # ── agent.py ──────────────────────────────────────────────────────────────
    print("  Gerando agent.py...")
    content = (whatsapp / "agent_template.py").read_text(encoding="utf-8")
    content = fix_imports(content)
    (dest_dir / "agent.py").write_text(content, encoding="utf-8")
    print("    ✅ agent.py gerado.")

    # ── watcher.py ou webhook_server.py ───────────────────────────────────────
    if args.modo == "watcher":
        generate_watcher_mode(dest_dir, cfg)
    else:
        generate_webhook_mode(dest_dir, cfg)

    # ── .env (resumo das configurações para referência) ───────────────────────
    print("  Gerando .env...")
    env_lines = [
        f"AI_PROVIDER={cfg.get('ai_provider', '')}",
        f"AI_MODEL={cfg.get('ai_model', '')}",
        f"CHECKOUT_LINK={cfg.get('checkout_link', '')}",
        f"PRODUCT_NAME={cfg.get('product_name', '')}",
    ]
    if args.modo == "watcher":
        env_lines += [
            f"EVOLUTION_URL={cfg.get('evolution_url', 'http://localhost:8080')}",
            f"INSTANCE_NAME={cfg.get('instance_name', 'meu-agente')}",
        ]
    else:
        env_lines += [
            f"META_PHONE_NUMBER_ID={cfg.get('meta_phone_number_id', '')}",
            f"WEBHOOK_URL={cfg.get('webhook_url', '')}",
        ]
    (dest_dir / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    print("    ✅ .env gerado.")

    # ── Instruções finais ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✅ Arquivos gerados em {dest_dir}")

    if args.modo == "watcher":
        print("""
Para iniciar o agente:
  python3 ~/meu-agente/watcher.py
""")
    else:
        print("""
Para iniciar o servidor webhook:
  pip install fastapi uvicorn
  python3 ~/meu-agente/webhook_server.py
""")
    print("=" * 60)


if __name__ == "__main__":
    main()
