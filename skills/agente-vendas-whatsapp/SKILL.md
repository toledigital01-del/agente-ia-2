---
name: agente-vendas-whatsapp
description: Manage, configure, update, test, and debug the WhatsApp Sales Agent for Ágil Cortinas e Persianas. Use this skill whenever the user mentions adjusting the WhatsApp bot, changing pricing, modifying the System Prompt, fixing Evolution API, updating Frenet shipping or Asaas checkouts, restarting the watcher, or managing conversational sales logic.
---

# WhatsApp Sales Agent - Management Skill

This skill provides comprehensive instructions on how to manage, configure, update, test, and debug the WhatsApp Sales Agent for **Ágil Cortinas e Persianas**.

## 🗺️ Repository and System Architecture

### Local Production Folder
All operational, running files are stored in `C:\Users\fmtol\meu-agente\`:
- `agent.py`: Handles message processing, dimension extraction, Fácil Persianas pricing calculations, CEP extraction, Frenet shipping queries, and triggers Asaas API checkout links.
- `agent_core.py`: Stores the core `SYSTEM_PROMPT` containing the uncurated BANT sales flow and product manual.
- `sessions.py`: Manages SQL schema, lead tracking, and `session_metadata` (width, height, cep, checkout_id, followup_status).
- `watcher.py`: Continuous poller of the Evolution API. Translates incoming voice messages via Whisper and generates voice replies via gTTS. Runs background payment reminders.
- `.env`: System credentials.

### Template and Repository Folder
The repository is located at `C:\users\fmtol\agente-ia-vendas\agente-ia-vendas\`.
Templates are compiled using placeholder replacements (`{{AI_API_KEY}}`, etc.) and copied to the local production folder:
- `templates/shared/agent_core_template.py` -> `meu-agente/agent_core.py`
- `templates/shared/sessions_template.py` -> `meu-agente/sessions.py`
- `templates/whatsapp/agent_template.py` -> `meu-agente/agent.py`
- `templates/whatsapp/watcher_template.py` -> `meu-agente/watcher.py`

---

## 🛠️ Operational Workflows

### 1. Updating the System Prompt or Pricing
When the user wants to adjust rules, pricing, or instructions:
1. Load `~/.meu-agente/config.json`.
2. Edit the `"system_prompt"` string with the new rules.
3. Overwrite `~/.meu-agente/config.json`.
4. Compile/regenerate `C:\Users\fmtol\meu-agente\agent_core.py` by reading `templates/shared/agent_core_template.py` and replacing placeholders with active values from `config.json`.
5. Restart the watcher (see section 6).

### 2. BANT Prompt Constraints & Rules
When modifying the prompt, ALWAYS enforce:
- **NO COMPETITOR MENTION:** NEVER mention "Fácil Persianas". Use "nossa fábrica" or "Ágil Persianas".
- **NO REGIONAL MENTION:** NEVER say the factory is in Juiz de Fora (MG). Delivery is nationwide.
- **ONE QUESTION AT A TIME:** The agent must ask exactly one question per message and wait for the response (cadenced flow).
- **5% PIX DISCOUNT:** Always offer 5% discount on PIX payments and show the calculated discounted price.
- **MEASUREMENT MANUALS:** Understand and explain standard wall installation (+10-15cm on all sides), sanca/plaster installation (-1cm width, +10-15cm height), and side-by-side split (width / 2 with a 3cm gap warning).

### 3. Database & SQL Integrity
- The `leads` table uses exactly **11 bindings** in the `create_lead` SQL insert query inside `sessions.py`. Ensure `now` is supplied for both `created_at` and `updated_at`.
- Use the `session_metadata` table to persist: `width`, `height`, `cep`, `checkout_id`, `asaas_checkout_url`, `checkout_sent_at`, and `followup_status` ("0", "1", "2", "PAID").

### 4. Audio Transcription and TTS Replies
- **Whisper Transcription:** Audio messages are fetched in Base64 via `POST /chat/getBase64FromMediaMessage/{instance}` and transcribed with Whisper. You MUST include `"User-Agent": "Mozilla/5.0 ..."` in headers of urllib requests to Groq (`api.groq.com`) to bypass Cloudflare Error 403.
- **Voice Response Synthesis:** Text replies are converted to MP3 using `gTTS` and sent as native voice notes via `POST /message/sendMedia/{instance}` with `"mediatype": "audio"` at the JSON root level.

### 5. Automatic Payment Reminders (Cobrança Ativa)
- The background task `process_payment_followups()` runs periodically in `watcher.py` (every 200 iterations / 10 minutes).
- It checks Asaas payment status using `GET /v3/payments?paymentLink={checkout_id}`.
- If unpaid, it sends a 2-hour friendly distraction reminder and a 24-hour scarcity/urgency reminder. If paid, it updates `followup_status` to `"PAID"` and sends a beautiful confirmation.

### 6. Restarting the Watcher Service
Whenever production code (`agent.py`, `watcher.py`, etc.) is updated, you MUST restart the background poller:
1. Search active background processes using `list_background_processes`.
2. Stop the running process: `Stop-Process -Id <PID> -Force` via shell command.
3. Launch a new background process: `python C:\Users\fmtol\meu-agente\watcher.py` with `is_background=True`.
