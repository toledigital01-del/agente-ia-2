#!/usr/bin/env python3
"""
reconnect_whatsapp.py — Reconecta WhatsApp quando sessão expira (v2, NOVO)

Use quando o WhatsApp foi desconectado (troca de celular, sessão expirada, etc.)
Desconecta a instância atual, deleta sessão e gera novo QR Code.
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get as cfg_get, save as cfg_save


def call_api(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    api_key = cfg_get("evolution_api_key", "")
    evo_url = cfg_get("evolution_url", "http://localhost:8080")

    url = f"{evo_url}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}


def get_state(instance: str) -> str:
    r = call_api(f"/instance/connectionState/{instance}")
    return r.get("instance", {}).get("state") or r.get("state") or "unknown"


def main():
    instance = cfg_get("instance_name", "meu-agente")

    print("=" * 60)
    print(f"Reconectando WhatsApp — instância: {instance}")
    print("=" * 60)

    # Estado atual
    state = get_state(instance)
    print(f"\nEstado atual: {state}")

    if state == "open":
        confirm = input("WhatsApp está conectado. Deseja reconectar mesmo assim? (s/N): ").strip().lower()
        if confirm != "s":
            print("Operação cancelada.\n")
            return

    # Logout da instância
    print("\nDesconectando sessão atual...")
    r = call_api(f"/instance/logout/{instance}", "DELETE")
    if "error" in r and "404" not in str(r.get("error")):
        print(f"  Aviso ao desconectar: {r.get('error')}")
    else:
        print("  Sessão encerrada.")

    # Gerar novo QR
    print("\nGerando novo QR Code...")
    cfg_save({"whatsapp_connected": False})

    # Importar e chamar connect_whatsapp
    sys.path.insert(0, str(Path(__file__).parent))
    import connect_whatsapp
    connect_whatsapp.main(instance_name=instance)


if __name__ == "__main__":
    main()
