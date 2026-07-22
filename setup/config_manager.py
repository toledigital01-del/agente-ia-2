#!/usr/bin/env python3
"""
config_manager.py — Gerencia configuração central em ~/.meu-agente/config.json

Centraliza API key da Evolution, provider de IA e outras configs.
Evita que cada script procure o .env em paths diferentes.
"""
import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".meu-agente" / "config.json"


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load()
    current.update(data)
    CONFIG_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value):
    save({key: value})


def show():
    cfg = load()
    if not cfg:
        print("  (sem configuração salva)")
        return
    for k, v in cfg.items():
        if "key" in k.lower() or "secret" in k.lower():
            masked = str(v)[:8] + "..." if v else "(vazio)"
            print(f"  {k}: {masked}")
        else:
            print(f"  {k}: {v}")
