#!/usr/bin/env python3
"""
connect_whatsapp.py — Conecta WhatsApp via QR Code (v2)

Melhorias v2:
  - Lê API key do config_manager (não de path frágil)
  - Exibe QR Code no próprio terminal (sem precisar de visualizador externo)
  - Fallback: salva PNG e abre com o app padrão do sistema (Windows/macOS/Linux)
  - Detecta reconexão: se já conectado, avisa e sai
"""
import json
import sys
import time
import base64
import platform
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get as cfg_get, save as cfg_save

OS = platform.system()


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
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}", "detail": body}
    except Exception as e:
        return {"error": str(e)}


def get_connection_state(instance: str) -> str:
    result = call_api(f"/instance/connectionState/{instance}")
    return (
        result.get("instance", {}).get("state")
        or result.get("state")
        or "unknown"
    )


def show_qr_terminal(qr_code_raw: str):
    """Tenta exibir QR Code no terminal via biblioteca qrcode (a partir do texto bruto do pairing)."""
    if not qr_code_raw:
        return False
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_code_raw)
        qr.make(fit=True)
        print("\n" + "=" * 60)
        print("QR CODE — escaneie com o WhatsApp:")
        print("=" * 60)
        qr.print_ascii(invert=True)
        return True
    except ImportError:
        return False


def show_qr_image(qr_data_url: str):
    """Salva QR Code como PNG e abre com o visualizador padrão do sistema."""
    raw = qr_data_url.split(",")[-1]
    try:
        img_bytes = base64.b64decode(raw)
    except Exception:
        return False

    img_path = Path(tempfile.gettempdir()) / "agente-qrcode.png"
    img_path.write_bytes(img_bytes)

    try:
        if OS == "Windows":
            import os
            os.startfile(str(img_path))
        elif OS == "Darwin":
            subprocess.Popen(["open", str(img_path)])
        else:
            subprocess.Popen(["xdg-open", str(img_path)])
        print(f"\nQR Code aberto no visualizador de imagens.")
        print(f"(arquivo: {img_path})")
        return True
    except Exception:
        print(f"\nQR Code salvo em: {img_path}")
        print("Abra esse arquivo manualmente para escanear.")
        return True


def display_qr(qr_code_raw: str, qr_base64: str):
    """Exibe QR: tenta terminal primeiro (a partir do texto bruto), depois imagem."""
    if not show_qr_terminal(qr_code_raw):
        if not qr_code_raw:
            print("\n  (não veio o texto bruto do QR na resposta da API)")
        else:
            print("\n  (instale 'qrcode' para ver no terminal: pip install qrcode)")
        show_qr_image(qr_base64)
    print("\nComo escanear:")
    print("  WhatsApp → Configurações → Aparelhos Conectados → Conectar Aparelho")


def main(instance_name: str = None):
    instance_name = instance_name or cfg_get("instance_name", "meu-agente")

    print("=" * 60)
    print("Conectando WhatsApp (v2)")
    print("=" * 60)

    # Verificar se já conectado
    print(f"\nVerificando instância: {instance_name}...")
    state = get_connection_state(instance_name)
    if state == "open":
        print("WhatsApp já conectado! Nada a fazer.")
        print("\nSe precisar reconectar: python setup/reconnect_whatsapp.py\n")
        return

    # Garantir que instância existe
    instances_resp = call_api("/instance/fetchInstances")
    instances = instances_resp if isinstance(instances_resp, list) else []
    existing_names = [
        i.get("name") or i.get("instance", {}).get("instanceName", "")
        for i in instances
    ]

    if instance_name not in existing_names:
        print(f"Criando instância '{instance_name}'...")
        r = call_api("/instance/create", "POST", {
            "instanceName": instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        })
        if "error" in r and "already" not in str(r.get("detail", "")):
            print(f"Erro ao criar instância: {r}")
            sys.exit(1)
        print("  Instância criada.")

    # Gerar QR Code
    print("\nGerando QR Code...")
    qr_result = call_api(f"/instance/connect/{instance_name}")

    qrcode_obj = qr_result.get("qrcode") if isinstance(qr_result.get("qrcode"), dict) else {}
    qr_code_raw = qr_result.get("code") or qrcode_obj.get("code")
    qr_base64 = (
        qr_result.get("base64")
        or qrcode_obj.get("base64")
        or (qr_result.get("qrcode") if isinstance(qr_result.get("qrcode"), str) else None)
    )

    if not qr_code_raw and not qr_base64:
        print(f"\nNão foi possível obter QR Code.")
        print(f"Resposta da API: {qr_result}")
        print("\nDicas:")
        print("  - Verifique se a Evolution API está rodando: docker ps")
        print("  - Verifique a API key em: python setup/install_evolution.py")
        sys.exit(1)

    display_qr(qr_code_raw, qr_base64)

    # Aguardar conexão
    print("\nAguardando scan (até 90 segundos)...")
    for i in range(90):
        state = get_connection_state(instance_name)
        if state == "open":
            print("  WhatsApp conectado!")
            cfg_save({"whatsapp_connected": True, "instance_name": instance_name})
            break
        if i % 20 == 0 and i > 0:
            print(f"  (aguardando... {i}s)")
        time.sleep(1)
    else:
        print("\nTimeout — o QR Code pode ter expirado.")
        print("Rode novamente para gerar um novo QR Code.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("WhatsApp conectado!")
    print("=" * 60)
    print(f"\nInstância: {instance_name}")
    print("\nPróxima etapa:")

    if OS == "Windows":
        print("  python setup/test_api.py --provider openai --key SUA_KEY\n")
    else:
        print("  python3 setup/test_api.py --provider openai --key SUA_KEY\n")


if __name__ == "__main__":
    main()
