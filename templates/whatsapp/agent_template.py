#!/usr/bin/env python3
"""
agent_template.py — Agente WhatsApp completo (v1.0)

Responsabilidades:
1. Detectar trigger phrase em mensagens
2. Carregar/gerenciar sessão de conversa
3. Chamar IA para resposta
4. Detectar intenção de compra e enviar checkout
5. Salvar conversa em SQLite

Use como: python3 agent.py --test
          python3 agent.py --chat PHONE
          Importar em watcher.py
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Carregar templates compartilhados
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from agent_core_template import call_ai, is_purchase_intent, format_checkout_message, SYSTEM_PROMPT, CHECKOUT_LINK
from sessions_template import init_db, load_session, save_session, create_lead, add_message, mark_checkout_sent, save_metadata, get_metadata

import re

def extract_dimensions(text: str):
    """Extrai largura e altura de textos como '1.50 x 2.00', '150x200', '1.5 por 2'."""
    pattern = r"(\d+(?:[.,]\d+)?)\s*(?:x|por)\s*(\d+(?:[.,]\d+)?)"
    match = re.search(pattern, text.lower())
    if match:
        try:
            w_str, h_str = match.group(1), match.group(2)
            w = float(w_str.replace(",", "."))
            h = float(h_str.replace(",", "."))
            if w > 10:
                w = w / 100.0
            if h > 10:
                h = h / 100.0
            return round(w, 2), round(h, 2)
        except Exception:
            pass
    return None

def extract_cep(text: str) -> str:
    """Extrai CEP de 8 dígitos de um texto."""
    match = re.search(r"\b(\d{5})-?(\d{3})\b", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None

def get_shipping_quote(recipient_cep: str, width_m: float, height_m: float, quantity: int = 1) -> dict:
    """Consulta frete na API da Frenet."""
    url = "https://api.frenet.com.br/shipping/quote"
    token = "6C05BE26R0E91R4D4FR8B11R94A046DD50A1"
    
    recipient_cep = "".join(filter(str.isdigit, recipient_cep))
    if len(recipient_cep) != 8:
        return {"error": "CEP inválido"}

    length_cm = int(width_m * 100)
    height_cm = 10
    width_cm = 10
    area = width_m * height_m
    weight_kg = max(1.0, area * 2.0)

    data = {
        "SellerCEP": "36015000",
        "RecipientCEP": recipient_cep,
        "ShipmentInvoiceValue": float(max(150.00, area * 150.00)),
        "RecipientCountry": "BR",
        "ShippingItemArray": [
            {
                "Height": height_cm,
                "Length": length_cm,
                "Width": width_cm,
                "Weight": weight_kg,
                "Quantity": int(quantity)
            }
        ]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "token": token},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode())
            services = res.get("ShippingSevicesArray", [])
            quotes = []
            for s in services:
                if s.get("Error") == False or str(s.get("Error")).lower() == "false":
                    quotes.append({
                        "carrier": s.get("Carrier"),
                        "description": s.get("ServiceDescription"),
                        "price": float(s.get("ShippingPrice")),
                        "days": int(s.get("DeliveryTime"))
                    })
            return {"quotes": quotes}
    except Exception as e:
        return {"error": str(e)}

# Configurações de trigger ({{placeholders}} preenchidos durante setup)
CHECKOUT_LINK = "{{CHECKOUT_LINK}}"
TRIGGER_EXACT = "{{TRIGGER_EXACT}}"
TRIGGER_KEYWORDS = [
    "{{PRODUCT_NAME}}",
    "dúvida",
    "informação",
    "saiba mais",
    "orçamento",
    "orcamento",
    "cortina",
    "persiana",
    "toldo",
    "tela",
    "mosqueteira",
    "blackout",
    "double vision",
    "valor",
    "preço",
    "preco",
    "quanto custa",
    "comprar",
    "encomendar"
]

DB_PATH = "~/meu-agente/dados.sqlite"


def is_trigger(text: str) -> bool:
    """Verifica se mensagem contém trigger phrase."""
    text_lower = text.lower()

    # Match exato tem prioridade
    if TRIGGER_EXACT.lower() in text_lower:
        return True

    # Verificar keywords
    for keyword in TRIGGER_KEYWORDS:
        if keyword.lower() in text_lower:
            return True

    return False


def handle_message(phone: str, sender_name: str, text: str) -> str:
    """
    Processa mensagem e retorna resposta do agente com cálculos físicos e cotação de frete.

    Args:
        phone: Número do lead (ex: "5585987654321")
        sender_name: Nome do lead
        text: Conteúdo da mensagem

    Returns:
        Resposta do agente (ou None se não é trigger)
    """

    # 1. Verificar trigger
    if not is_trigger(text):
        return None

    # 2. Criar/carregar lead
    lead_id = create_lead(phone, name=sender_name)

    # Tentar extrair dimensões e CEP da mensagem atual
    dims = extract_dimensions(text)
    if dims:
        w, h = dims
        save_metadata(lead_id, "width", str(w))
        save_metadata(lead_id, "height", str(h))

    cep = extract_cep(text)
    if cep:
        save_metadata(lead_id, "cep", cep)

    # 3. Carregar sessão existente ou criar nova
    messages = load_session(lead_id) or []

    # 4. Adicionar mensagem do usuário
    user_message = {"role": "user", "content": text}
    messages.append(user_message)
    add_message(lead_id, "user", text)

    # Carregar metadados salvos acumulados para realizar os cálculos estruturados
    saved_w = get_metadata(lead_id, "width")
    saved_h = get_metadata(lead_id, "height")
    saved_cep = get_metadata(lead_id, "cep")

    prompt_injection = []
    if saved_w and saved_h:
        w_float = float(saved_w)
        h_float = float(saved_h)
        area = w_float * h_float
        charged_area = max(1.80, area) # Área mínima cobrada de 1.80m² igual à Fácil Persianas!
        
        # Preços Fácil Persianas
        p_blackout = charged_area * 147.39
        p_solar = charged_area * 186.44
        p_double = charged_area * 147.39

        calc_info = f"[SISTEMA: Para as medidas de {w_float:.2f}m x {h_float:.2f}m (Área real: {area:.2f}m², Área cobrada/mínima: {charged_area:.2f}m²):\n"
        calc_info += f"- Rolô Blackout (R$ 147.39/m²): R$ {p_blackout:.2f}\n"
        calc_info += f"- Rolô Tela Solar (R$ 186.44/m²): R$ {p_solar:.2f}\n"
        calc_info += f"- Double Vision (R$ 147.39/m²): R$ {p_double:.2f}\n"
        calc_info += "USE ESTES VALORES EXATOS NO SEU ORÇAMENTO! NUNCA INVENTE OUTROS PREÇOS!]"
        prompt_injection.append(calc_info)

    if saved_cep and saved_w and saved_h:
        w_float = float(saved_w)
        h_float = float(saved_h)
        quote_res = get_shipping_quote(saved_cep, w_float, h_float)
        if "quotes" in quote_res and quote_res["quotes"]:
            best_quote = quote_res["quotes"][0]
            carrier = best_quote["carrier"]
            desc = best_quote["description"]
            price = best_quote["price"]
            days = best_quote["days"]
            
            shipping_info = f"[SISTEMA: Cotação de Frete via Frenet para CEP {saved_cep}: {carrier} ({desc}) por R$ {price:.2f} - entrega em {days} dias úteis. Informe e cobre junto no fechamento!]"
            prompt_injection.append(shipping_info)
        elif "error" in quote_res:
            prompt_injection.append(f"[SISTEMA: Ocorreu um erro no cálculo de frete Frenet para o CEP {saved_cep}: {quote_res.get('error')}. Diga ao cliente que vai calcular com o setor de logística e já retorna.]")

    # Injetar instruções calculadas dinamicamente no final do histórico enviado à IA
    ai_messages = messages.copy()
    if prompt_injection:
        system_instruction = "\n".join(prompt_injection)
        ai_messages.append({"role": "system", "content": system_instruction})

    # 5. Chamar IA
    response = call_ai(ai_messages)

    # 6. Adicionar resposta do agente
    messages.append({"role": "assistant", "content": response})
    add_message(lead_id, "assistant", response)

    # 7. Salvar sessão
    save_session(lead_id, messages)

    # 8. Verificar intenção de compra
    if is_purchase_intent(text, messages) and len(messages) >= 4:
        response += f"\n\n{format_checkout_message()}"
        mark_checkout_sent(lead_id)

    return response


def test_trigger():
    """Teste de trigger (para setup/test_agent.py)."""
    test_messages = [
        TRIGGER_EXACT,
        "Oi, tenho uma dúvida sobre o produto",
        "Não é trigger"
    ]

    print("Testando triggers:\n")
    for msg in test_messages:
        result = "✅ Detectado" if is_trigger(msg) else "❌ Ignorado"
        print(f"  \"{msg}\" → {result}")

    return True


def main():
    """Interface CLI para teste."""
    import argparse

    parser = argparse.ArgumentParser(description="Agente WhatsApp v1.0")
    parser.add_argument("--test", action="store_true", help="Testa triggers")
    parser.add_argument("--chat", type=str, help="Chat interativo com phone")

    args = parser.parse_args()

    # Inicializar DB
    init_db()

    if args.test:
        test_trigger()
    elif args.chat:
        # Chat interativo
        print(f"\n💬 Chat com {args.chat}")
        print("(Digite 'sair' para encerrar)\n")

        while True:
            msg = input("Você: ").strip()
            if msg.lower() == "sair":
                break

            response = handle_message(
                phone=args.chat,
                sender_name="Teste",
                text=msg
            )

            if response:
                print(f"Agente: {response}\n")
            else:
                print("(Mensagem ignorada — não contém trigger)\n")
    else:
        print("Use: python3 agent.py --test")
        print("     python3 agent.py --chat PHONE")


if __name__ == "__main__":
    main()
