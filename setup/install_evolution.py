#!/usr/bin/env python3
"""
install_evolution.py — Instala Evolution API via Docker (v2)

Melhorias v2:
  - Usa imagem Docker oficial (sem git clone do repositório inteiro)
  - Salva API key via config_manager (sem depender de path frágil)
  - Detecta se Docker está rodando antes de tentar
  - Suporte Windows, macOS e Linux
"""
import subprocess
import secrets
import sys
import time
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_manager import save as cfg_save, get as cfg_get

EVOLUTION_PORT = 8080
EVOLUTION_URL = f"http://localhost:{EVOLUTION_PORT}"
COMPOSE_DIR = Path.home() / ".meu-agente" / "evolution"

DOCKER_COMPOSE = """\
services:
  evolution:
    image: atendai/evolution-api:v2.2.3
    container_name: evolution-api
    restart: unless-stopped
    ports:
      - "{port}:8080"
    environment:
      - SERVER_PORT=8080
      - LANGUAGE=pt-BR
      - LOG_LEVEL=warn
      - DB_CONNECTION=sqlite
      - DB_SAVE_DATA_INSTANCE=true
      - DB_SAVE_DATA_NEW_MESSAGE=true
      - DB_URL=file:/evolution/evolution.db
      - AUTHENTICATION_API_KEY={api_key}
      - AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
    volumes:
      - evolution_data:/evolution

volumes:
  evolution_data:
"""


def is_running() -> bool:
    try:
        with urllib.request.urlopen(EVOLUTION_URL, timeout=3) as r:
            data = json.loads(r.read())
            return "Evolution" in str(data)
    except Exception:
        return False


def docker_running() -> bool:
    r = subprocess.run(
        ["docker", "info"],
        capture_output=True, timeout=8
    )
    return r.returncode == 0


def main():
    print("=" * 60)
    print("Instalando Evolution API (v2)")
    print("=" * 60)

    # Verificar se já está rodando
    print("\nVerificando se Evolution API já está ativa...")
    if is_running():
        api_key = cfg_get("evolution_api_key")
        if api_key:
            print("Evolution API já rodando e configurada!")
        else:
            print("Evolution API rodando mas API key não encontrada.")
            api_key = input("Cole sua API key do .env da Evolution: ").strip()
            cfg_save({"evolution_api_key": api_key, "evolution_url": EVOLUTION_URL})
        print("\nPróxima etapa:")
        print("  python setup/connect_whatsapp.py\n")
        return

    # Verificar Docker
    print("Verificando Docker...")
    if not docker_running():
        print("\nDocker não está rodando.")
        print("Abra o Docker Desktop e aguarde ficar verde, depois rode novamente.\n")
        sys.exit(1)
    print("  Docker ok")

    # Criar diretório e docker-compose.yml
    COMPOSE_DIR.mkdir(parents=True, exist_ok=True)
    api_key = cfg_get("evolution_api_key") or secrets.token_urlsafe(32)
    compose_file = COMPOSE_DIR / "docker-compose.yml"
    compose_file.write_text(
        DOCKER_COMPOSE.format(port=EVOLUTION_PORT, api_key=api_key),
        encoding="utf-8"
    )
    print(f"  docker-compose.yml criado em: {COMPOSE_DIR}")

    # Salvar API key
    cfg_save({
        "evolution_api_key": api_key,
        "evolution_url": EVOLUTION_URL,
        "instance_name": "meu-agente",
    })
    print(f"  API Key salva (começa com: {api_key[:12]}...)")

    # Subir Docker
    print("\nIniciando containers (pode levar 1-2 min na primeira vez)...")
    r = subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=str(COMPOSE_DIR),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"\nErro ao iniciar Docker:\n{r.stderr}")
        print("\nTente manualmente:")
        print(f"  cd {COMPOSE_DIR}")
        print("  docker compose up -d\n")
        sys.exit(1)

    # Aguardar API
    print("Aguardando Evolution API ficar pronta...")
    for i in range(90):
        if is_running():
            print("  Evolution API pronta!")
            break
        if i % 15 == 0 and i > 0:
            print(f"  (aguardando... {i}s)")
        time.sleep(1)
    else:
        print("\nTimeout — a API ainda não respondeu.")
        print(f"Verifique: docker logs evolution-api\n")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Evolution API instalada e rodando!")
    print("=" * 60)
    print(f"\nURL: {EVOLUTION_URL}")
    print("\nPróxima etapa:")
    print("  python setup/connect_whatsapp.py\n")


if __name__ == "__main__":
    main()
