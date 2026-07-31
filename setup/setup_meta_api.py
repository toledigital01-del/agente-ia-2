#!/usr/bin/env python3
"""
setup_meta_api.py — Configura as credenciais da Meta WhatsApp Cloud API

Guia o usuário passo a passo pelo processo de configuração na Meta Developers
e salva as credenciais no config.json do cliente.

Execução:
  python3 setup/setup_meta_api.py
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path


def print_box(title: str, lines: list):
    width = max(len(l) for l in [title] + lines) + 4
    print("\n┌" + "─" * width + "┐")
    print(f"│  {title.ljust(width - 2)}│")
    print("├" + "─" * width + "┤")
    for line in lines:
        print(f"│  {line.ljust(width - 2)}│")
    print("└" + "─" * width + "┘\n")


def ask(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val or default
    while True:
        val = input(f"  {prompt}: ").strip()
        if val:
            return val
        print("  ⚠️  Campo obrigatório. Tente novamente.")


def test_meta_token(token: str, phone_id: str) -> bool:
    """Verifica se o token e o phone_number_id estão corretos."""
    url = f"https://graph.facebook.com/v20.0/{phone_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return "id" in data
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  ❌ Token inválido ou sem permissão.")
        elif e.code == 404:
            print("  ❌ Phone Number ID não encontrado.")
        else:
            print(f"  ❌ Erro {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"  ⚠️  Não foi possível verificar (sem internet?): {e}")
        return True  # Continua sem bloquear


def register_webhook(token: str, waba_id: str, webhook_url: str, verify_token: str) -> bool:
    """Registra o webhook na Meta via Graph API."""
    url = f"https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps"
    data = json.dumps({
        "callback_url": f"{webhook_url}/webhook" if not webhook_url.endswith("/webhook") else webhook_url,
        "verify_token": verify_token,
        "subscribed_fields": ["messages"]
    }).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
            return result.get("success", False)
    except Exception as e:
        print(f"  ⚠️  Registro automático falhou: {e}")
        return False


def load_config() -> dict:
    config_path = Path.home() / ".meu-agente" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    config_path = Path.home() / ".meu-agente" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    print("\n" + "=" * 55)
    print("  Configuração da Meta WhatsApp Cloud API")
    print("=" * 55)

    print("""
Antes de começar, você precisa ter feito:
  1. Criado uma conta em https://developers.facebook.com
  2. Criado um App (tipo: Business)
  3. Adicionado o produto "WhatsApp" ao App
  4. Adicionado um número de WhatsApp Business

Se ainda não fez isso, acesse o link acima e siga o
passo a passo da Meta. Leva cerca de 10 minutos.
""")
    input("  Pressione ENTER quando estiver pronto...")

    # ── Passo 1: Token de acesso ────────────────────────────────────────────────
    print_box("PASSO 1 — Token de Acesso", [
        "No painel Meta Developers:",
        "  WhatsApp > Configuração da API > Token de acesso temporário",
        "",
        "Para um token PERMANENTE (recomendado para produção):",
        "  Configurações > Usuários do sistema > Gerar token",
        "  (marque whatsapp_business_messaging)",
    ])
    meta_token = ask("Cole seu Access Token aqui")

    # ── Passo 2: Phone Number ID ────────────────────────────────────────────────
    print_box("PASSO 2 — Phone Number ID", [
        "No painel Meta Developers:",
        "  WhatsApp > Configuração da API",
        "  Copie o 'ID do número de telefone'",
        "  (é um número longo como 123456789012345)",
    ])
    phone_number_id = ask("Cole o Phone Number ID")

    # Testar credenciais
    print("\n  🔍 Verificando credenciais...")
    if not test_meta_token(meta_token, phone_number_id):
        print("  ❌ Verifique o token e o Phone Number ID e tente novamente.")
        sys.exit(1)
    print("  ✅ Credenciais válidas!")

    # ── Passo 3: WABA ID (para registrar webhook automaticamente) ───────────────
    print_box("PASSO 3 — WhatsApp Business Account ID", [
        "No painel Meta Developers:",
        "  WhatsApp > Configuração da API",
        "  Copie o 'ID da conta do WhatsApp Business'",
        "  (diferente do Phone Number ID)",
    ])
    waba_id = ask("Cole o WABA ID (WhatsApp Business Account ID)")

    # ── Passo 4: URL do webhook ─────────────────────────────────────────────────
    cfg = load_config()
    webhook_url_default = cfg.get("webhook_url", "")

    print_box("PASSO 4 — URL do Webhook", [
        "Essa é a URL gerada pelo Cloudflare Tunnel.",
        "Se ainda não rodou o tunnel, execute primeiro:",
        "  sudo python3 setup/install_cloudflare_tunnel.py",
        "",
        "Formato esperado:",
        "  https://abc123.cfargotunnel.com",
    ])
    webhook_url = ask("URL base do Cloudflare Tunnel", webhook_url_default)
    if webhook_url.endswith("/webhook"):
        webhook_url = webhook_url[:-8]

    # ── Passo 5: Verify Token ───────────────────────────────────────────────────
    import secrets
    verify_token_default = cfg.get("meta_verify_token", secrets.token_hex(16))
    print(f"\n  ℹ️  Verify token (pode deixar o gerado automaticamente):")
    verify_token = ask("Verify Token", verify_token_default)

    # ── Registrar webhook automaticamente ──────────────────────────────────────
    print(f"\n  🔗 Registrando webhook em {webhook_url}/webhook ...")
    if register_webhook(meta_token, waba_id, webhook_url, verify_token):
        print("  ✅ Webhook registrado automaticamente na Meta!")
    else:
        print("""
  ⚠️  Não foi possível registrar automaticamente.
  Faça manualmente no painel Meta Developers:
    WhatsApp > Configuração > Webhooks
    URL: """ + webhook_url + """/webhook
    Verify Token: """ + verify_token)
        input("\n  Pressione ENTER após configurar o webhook manualmente...")

    # ── Salvar no config.json ──────────────────────────────────────────────────
    cfg.update({
        "meta_access_token":   meta_token,
        "meta_phone_number_id": phone_number_id,
        "meta_waba_id":        waba_id,
        "meta_verify_token":   verify_token,
        "webhook_url":         webhook_url,
    })
    save_config(cfg)

    print(f"""
{'=' * 55}
✅ Meta Cloud API configurada com sucesso!

Salvo em: ~/.meu-agente/config.json

Próximo passo — subir o servidor webhook:

  pip install fastapi uvicorn
  python3 ~/meu-agente/webhook_server.py

Para rodar em background com o systemd:
  sudo python3 setup/deploy_multicliente.py
{'=' * 55}
""")


if __name__ == "__main__":
    main()
