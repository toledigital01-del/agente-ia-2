#!/usr/bin/env python3
"""
generate_meu_agente.py — Gera os arquivos finais de execução em ~/meu-agente/ (Etapa 6)
"""
import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

def main():
    print("=" * 60)
    print("Geração dos Arquivos do Agente (Etapa 6)")
    print("=" * 60)

    # 1. Carregar Configuração
    config_path = Path.home() / ".meu-agente" / "config.json"
    if not config_path.exists():
        print("❌ Arquivo de configuração ~/.meu-agente/config.json não encontrado!")
        sys.exit(1)

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Erro ao ler ~/.meu-agente/config.json: {e}")
        sys.exit(1)

    # 2. Criar diretório ~/meu-agente/
    dest_dir = Path.home() / "meu-agente"
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Diretório destino garantido: {dest_dir}")

    # Definir valores de placeholder
    ai_provider = cfg.get("ai_provider", "gemini")
    ai_model = cfg.get("ai_model", "gemini-3.6-flash")
    ai_api_key = cfg.get("ai_api_key", "")
    checkout_link = cfg.get("checkout_link", "")
    system_prompt = cfg.get("system_prompt", "")
    trigger_exact = cfg.get("lead_trigger_phrase", "")
    product_name = cfg.get("product_name", "")
    evolution_api_key = cfg.get("evolution_api_key", "")
    evolution_url = cfg.get("evolution_url", "http://localhost:8080")
    instance_name = cfg.get("instance_name", "meu-agente")
    owner_phone = cfg.get("owner_phone", "")

    # 3. Gerar agent_core.py (a partir de templates/shared/agent_core_template.py)
    core_template_path = Path("templates/shared/agent_core_template.py")
    if not core_template_path.exists():
        print(f"❌ Template não encontrado: {core_template_path}")
        sys.exit(1)

    print("  Gerando agent_core.py...")
    core_content = core_template_path.read_text(encoding="utf-8")
    core_content = core_content.replace("{{AI_PROVIDER}}", ai_provider)
    core_content = core_content.replace("{{AI_MODEL}}", ai_model)
    core_content = core_content.replace("{{AI_API_KEY}}", ai_api_key)
    core_content = core_content.replace("{{CHECKOUT_LINK}}", checkout_link)
    core_content = core_content.replace("{{SYSTEM_PROMPT}}", system_prompt)
    
    (dest_dir / "agent_core.py").write_text(core_content, encoding="utf-8")
    print("    ✅ agent_core.py gerado.")

    # 4. Gerar sessions.py (a partir de templates/shared/sessions_template.py)
    sessions_template_path = Path("templates/shared/sessions_template.py")
    if not sessions_template_path.exists():
        print(f"❌ Template não encontrado: {sessions_template_path}")
        sys.exit(1)

    print("  Gerando sessions.py...")
    sessions_content = sessions_template_path.read_text(encoding="utf-8")
    (dest_dir / "sessions.py").write_text(sessions_content, encoding="utf-8")
    print("    ✅ sessions.py gerado.")

    # 5. Gerar agent.py (a partir de templates/whatsapp/agent_template.py)
    agent_template_path = Path("templates/whatsapp/agent_template.py")
    if not agent_template_path.exists():
        print(f"❌ Template não encontrado: {agent_template_path}")
        sys.exit(1)

    print("  Gerando agent.py...")
    agent_content = agent_template_path.read_text(encoding="utf-8")
    agent_content = agent_content.replace("{{CHECKOUT_LINK}}", checkout_link)
    agent_content = agent_content.replace("{{TRIGGER_EXACT}}", trigger_exact)
    agent_content = agent_content.replace("{{PRODUCT_NAME}}", product_name)

    # Ajustar imports do template de compartilhado para local
    old_imports = """# Carregar templates compartilhados
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from agent_core_template import call_ai, is_purchase_intent, format_checkout_message, SYSTEM_PROMPT, CHECKOUT_LINK
from sessions_template import init_db, load_session, save_session, create_lead, add_message, mark_checkout_sent, save_metadata, get_metadata"""

    new_imports = """# Carregar módulos locais
sys.path.insert(0, str(Path(__file__).parent))
from agent_core import call_ai, is_purchase_intent, format_checkout_message, SYSTEM_PROMPT, CHECKOUT_LINK
from sessions import init_db, load_session, save_session, create_lead, add_message, mark_checkout_sent, save_metadata, get_metadata"""

    if old_imports in agent_content:
        agent_content = agent_content.replace(old_imports, new_imports)
    else:
        # Fallback se quebras de linha variarem levemente
        agent_content = agent_content.replace("agent_core_template", "agent_core")
        agent_content = agent_content.replace("sessions_template", "sessions")
        agent_content = agent_content.replace('.parent.parent / "shared"', '.parent')

    (dest_dir / "agent.py").write_text(agent_content, encoding="utf-8")
    print("    ✅ agent.py gerado.")

    # 6. Gerar watcher.py (a partir de templates/whatsapp/watcher_template.py)
    watcher_template_path = Path("templates/whatsapp/watcher_template.py")
    if not watcher_template_path.exists():
        print(f"❌ Template não encontrado: {watcher_template_path}")
        sys.exit(1)

    print("  Gerando watcher.py...")
    watcher_content = watcher_template_path.read_text(encoding="utf-8")
    watcher_content = watcher_content.replace("{{EVOLUTION_API_KEY}}", evolution_api_key)
    watcher_content = watcher_content.replace("{{OWNER_PHONE}}", owner_phone)
    watcher_content = watcher_content.replace("INSTANCE_NAME = \"meu-agente\"", f"INSTANCE_NAME = \"{instance_name}\"")
    watcher_content = watcher_content.replace("EVOLUTION_URL = \"http://localhost:8080\"", f"EVOLUTION_URL = \"{evolution_url}\"")

    (dest_dir / "watcher.py").write_text(watcher_content, encoding="utf-8")
    print("    ✅ watcher.py gerado.")

    # 7. Gerar .env
    print("  Gerando .env...")
    env_content = f"""# Configurações do Agente de Vendas
EVOLUTION_URL={evolution_url}
EVOLUTION_API_KEY={evolution_api_key}
INSTANCE_NAME={instance_name}

AI_PROVIDER={ai_provider}
AI_MODEL={ai_model}
AI_API_KEY={ai_api_key}

CHECKOUT_LINK={checkout_link}
TRIGGER_EXACT={trigger_exact}
PRODUCT_NAME={product_name}
"""
    (dest_dir / ".env").write_text(env_content, encoding="utf-8")
    print("    ✅ .env gerado.")

    print("\n" + "=" * 60)
    print("✅ Todos os arquivos foram gerados em ~/meu-agente/")
    print("=" * 60)

if __name__ == "__main__":
    main()
