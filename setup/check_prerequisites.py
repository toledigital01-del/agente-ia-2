#!/usr/bin/env python3
"""
check_prerequisites.py — Verifica pré-requisitos do sistema (v2)

Melhorias v2:
  - Funciona em Windows, macOS e Linux (detecta python ou python3)
  - Verifica se Docker daemon está RODANDO (não apenas instalado)
  - Remove verificação de Node.js (não é necessário)
  - Mensagens de instalação específicas por OS
"""
import subprocess
import sys
import platform

OS = platform.system()  # "Windows", "Darwin", "Linux"


def run(cmd: list, timeout: int = 5) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or r.stderr or "ok").strip().split("\n")[0]
        return r.returncode == 0, out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def check_python() -> bool:
    # Tenta 'python' primeiro (Windows), depois 'python3' (macOS/Linux)
    for cmd in (["python", "--version"], ["python3", "--version"]):
        ok, ver = run(cmd)
        if ok and ver:
            print(f"  ✅ Python: {ver}")
            return True
    print("  ❌ Python NÃO encontrado")
    return False


def check_git() -> bool:
    ok, ver = run(["git", "--version"])
    if ok:
        print(f"  ✅ Git: {ver}")
        return True
    print("  ❌ Git NÃO encontrado")
    return False


def check_docker_installed() -> bool:
    ok, ver = run(["docker", "--version"])
    if ok:
        print(f"  ✅ Docker instalado: {ver}")
        return True
    print("  ❌ Docker NÃO instalado")
    return False


def check_docker_running() -> bool:
    ok, _ = run(["docker", "info"], timeout=8)
    if ok:
        print("  ✅ Docker daemon rodando")
        return True
    print("  ❌ Docker NÃO está rodando (Docker Desktop precisa estar aberto)")
    return False


def print_install_guide(missing: list):
    guides = {
        "python": {
            "Windows": "winget install Python.Python.3.12",
            "Darwin":  "brew install python3",
            "Linux":   "sudo apt install python3",
        },
        "git": {
            "Windows": "winget install Git.Git",
            "Darwin":  "brew install git",
            "Linux":   "sudo apt install git",
        },
        "docker": {
            "Windows": "Baixe em: https://www.docker.com/products/docker-desktop",
            "Darwin":  "Baixe em: https://www.docker.com/products/docker-desktop",
            "Linux":   "sudo apt install docker.io && sudo systemctl start docker",
        },
        "docker_running": {
            "Windows": "Abra o Docker Desktop no menu Iniciar e aguarde o ícone na bandeja ficar verde",
            "Darwin":  "Abra o Docker Desktop (Applications) e aguarde o ícone na barra ficar verde",
            "Linux":   "sudo systemctl start docker",
        },
    }

    print("\n" + "=" * 60)
    print("Instale o que falta e rode novamente:")
    print("=" * 60)
    for item in missing:
        cmd = guides.get(item, {}).get(OS, "Veja: https://docs.docker.com")
        print(f"\n  {item.upper()}:\n    {cmd}")
    print()


def main():
    print("=" * 60)
    print("Verificando pré-requisitos")
    print("=" * 60 + "\n")

    missing = []

    print("Python:")
    if not check_python():
        missing.append("python")

    print("\nGit:")
    if not check_git():
        missing.append("git")

    print("\nDocker:")
    docker_installed = check_docker_installed()
    if not docker_installed:
        missing.append("docker")
    else:
        if not check_docker_running():
            missing.append("docker_running")

    if missing:
        print_install_guide(missing)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Todos os pré-requisitos instalados!")
    print("=" * 60)
    print("\nPróxima etapa:")

    if OS == "Windows":
        print("  python setup/install_evolution.py\n")
    else:
        print("  python3 setup/install_evolution.py\n")


if __name__ == "__main__":
    main()
