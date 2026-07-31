#!/usr/bin/env python3
"""
install_cloudflare_tunnel.py — Instala e configura Cloudflare Tunnel na VPS

O túnel cria uma URL pública HTTPS estável (ex: https://abc123.cfargotunnel.com)
apontando para o servidor webhook local na porta 8000.
Essa URL é usada como endpoint de webhook na Meta Developers.

Execução (na VPS, como root ou com sudo):
  python3 setup/install_cloudflare_tunnel.py
"""

import os
import sys
import json
import subprocess
import urllib.request
from pathlib import Path


def print_step(n: int, total: int, msg: str):
    bar = "█" * n + "░" * (total - n)
    print(f"\n[{bar}] Passo {n}/{total} — {msg}")


def run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check,
                          capture_output=capture, text=True)


def check_root():
    if os.geteuid() != 0:
        print("⚠️  Execute com sudo: sudo python3 setup/install_cloudflare_tunnel.py")
        sys.exit(1)


def install_cloudflared():
    print_step(1, 5, "Instalando cloudflared")

    # Verificar se já está instalado
    result = run(["which", "cloudflared"], check=False, capture=True)
    if result.returncode == 0:
        print("   ✅ cloudflared já instalado:", result.stdout.strip())
        return

    arch = run(["uname", "-m"], capture=True).stdout.strip()
    if arch == "x86_64":
        filename = "cloudflared-linux-amd64"
    elif arch == "aarch64":
        filename = "cloudflared-linux-arm64"
    else:
        print(f"❌ Arquitetura não suportada: {arch}")
        sys.exit(1)

    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{filename}"
    print(f"   Baixando {url}...")
    urllib.request.urlretrieve(url, f"/tmp/{filename}")
    os.chmod(f"/tmp/{filename}", 0o755)
    run(["mv", f"/tmp/{filename}", "/usr/local/bin/cloudflared"])
    print("   ✅ cloudflared instalado em /usr/local/bin/cloudflared")


def login_cloudflare():
    print_step(2, 5, "Login na Cloudflare")
    print("""
   O comando abaixo vai abrir um link no terminal.
   Copie o link, cole no seu navegador e faça login
   na Cloudflare (crie conta grátis em cloudflare.com).
   Após autorizar, volte aqui — o terminal continua sozinho.
    """)
    input("   Pressione ENTER para gerar o link de login...")
    result = run(["cloudflared", "tunnel", "login"], check=False)
    if result.returncode != 0:
        print("❌ Falha no login. Tente novamente.")
        sys.exit(1)
    print("   ✅ Login realizado com sucesso!")


def create_tunnel(name: str = "meu-agente") -> str:
    print_step(3, 5, f"Criando túnel '{name}'")

    # Verificar se já existe
    result = run(["cloudflared", "tunnel", "list", "--output", "json"],
                 check=False, capture=True)
    if result.returncode == 0:
        try:
            tunnels = json.loads(result.stdout)
            for t in tunnels:
                if t.get("name") == name:
                    tunnel_id = t["id"]
                    print(f"   ✅ Túnel já existe: {tunnel_id}")
                    return tunnel_id
        except Exception:
            pass

    result = run(["cloudflared", "tunnel", "create", name], capture=True)
    tunnel_id = None
    for line in result.stdout.splitlines():
        if "with id" in line:
            tunnel_id = line.split("with id")[-1].strip().split()[0]
            break

    if not tunnel_id:
        print("❌ Não foi possível extrair o ID do túnel.")
        print(result.stdout)
        sys.exit(1)

    print(f"   ✅ Túnel criado: {tunnel_id}")
    return tunnel_id


def write_config(tunnel_id: str, local_port: int = 8000) -> str:
    print_step(4, 5, "Configurando túnel")

    config_dir = Path.home() / ".cloudflared"
    config_dir.mkdir(exist_ok=True)

    config_content = f"""tunnel: {tunnel_id}
credentials-file: {config_dir}/{tunnel_id}.json

ingress:
  - service: http://localhost:{local_port}
  - service: http_status:404
"""
    (config_dir / "config.yml").write_text(config_content)
    tunnel_url = f"https://{tunnel_id}.cfargotunnel.com"
    print(f"   ✅ Configuração salva em {config_dir}/config.yml")
    print(f"   🔗 Sua URL pública será: {tunnel_url}")
    return tunnel_url


def install_service():
    print_step(5, 5, "Instalando como serviço (auto-start)")
    run(["cloudflared", "service", "install"], check=False)
    run(["systemctl", "enable", "cloudflared"], check=False)
    run(["systemctl", "restart", "cloudflared"], check=False)

    result = run(["systemctl", "is-active", "cloudflared"], check=False, capture=True)
    if result.stdout.strip() == "active":
        print("   ✅ Serviço cloudflared ativo e rodando.")
    else:
        print("   ⚠️  Serviço pode não ter subido. Verifique: systemctl status cloudflared")


def save_url_to_config(tunnel_url: str):
    config_path = Path.home() / ".meu-agente" / "config.json"
    if not config_path.exists():
        return
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg["webhook_url"] = tunnel_url
        config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print(f"\n   ✅ URL salva em {config_path}")
    except Exception as e:
        print(f"   ⚠️  Não salvou no config.json: {e}")


def main():
    print("=" * 50)
    print("  Configuração do Cloudflare Tunnel")
    print("=" * 50)

    check_root()
    install_cloudflared()
    login_cloudflare()
    tunnel_id  = create_tunnel("meu-agente")
    tunnel_url = write_config(tunnel_id)
    install_service()
    save_url_to_config(tunnel_url)

    webhook_url = f"{tunnel_url}/webhook"

    print(f"""
{'=' * 50}
✅ Cloudflare Tunnel configurado com sucesso!

🔗 URL pública do webhook:
   {webhook_url}

Próximo passo:
  python3 setup/setup_meta_api.py

Cole a URL acima quando o script pedir.
{'=' * 50}
""")


if __name__ == "__main__":
    main()
