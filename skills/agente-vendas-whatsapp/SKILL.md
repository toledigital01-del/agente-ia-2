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
- **PRICING IS INTENTIONALLY "FÁCIL PERSIANAS" PRICING — DO NOT "FIX" IT:** `agent.py`'s hardcoded per-m² prices (R$ 147.39 for Rolô Blackout/Double Vision, R$ 186.44 for Rolô Tela Solar, comment literally says `# Preços Fácil Persianas`) look at first glance like a copy-paste bug from a competitor's project, especially since the real prices listed on `agilcortinasepersianas.com.br/loja` are 2-4x higher (e.g. Rolô Blackout Texturizado is R$336.71/m² on the live site, not R$147.39). **This is confirmed intentional** — the client explicitly said (2026-07-25) "nossos preços são os mesmos deles" (our prices are the same as theirs) and that this stays the source of truth **until they send an explicit price table**. A model-detection rewrite (mapping each of the new 🧵 tecido variants to real site prices) was built, tested, and then explicitly reverted at the client's request — do not reintroduce it without a fresh, explicit go-ahead. If the client ever does send a price table, update the two hardcoded multipliers (and mirror in `templates/whatsapp/agent_template.py`) rather than scraping the live site again.

### 3. Database & SQL Integrity
- The `leads` table uses exactly **11 bindings** in the `create_lead` SQL insert query inside `sessions.py`. Ensure `now` is supplied for both `created_at` and `updated_at`.
- Use the `session_metadata` table to persist: `width`, `height`, `cep`, `checkout_id`, `asaas_checkout_url`, `checkout_sent_at`, and `followup_status` ("0", "1", "2", "PAID").

### 4. Audio Transcription and TTS Replies
- **Whisper Transcription:** Audio messages are fetched in Base64 via `POST /chat/getBase64FromMediaMessage/{instance}` and transcribed with Whisper (Groq's `whisper-large-v3` preferred, `OPENAI_API_KEY`/`whisper-1` as second choice — both read from `~/.config/watch/.env`). You MUST include `"User-Agent": "Mozilla/5.0 ..."` in headers of urllib requests to Groq (`api.groq.com`) to bypass Cloudflare Error 403.
  - **Fixed bug (2026-07-25):** the last-resort fallback used to reuse `config.json`'s `ai_api_key` as if it were always an OpenAI key whenever it was >30 chars — but that key is whatever `AI_PROVIDER` is currently set to (Anthropic/Gemini/OpenAI). Since the client runs Anthropic, this silently sent an `sk-ant-...` key as a Bearer token to `api.openai.com`, which 401s every time (audio replies would then just fail with "não consegui compreender seu áudio"). Now gated on `config_data.get("ai_provider") == "openai"` before reusing that key — in `watcher.py` and `templates/whatsapp/watcher_template.py`.
- **Voice Response Synthesis:** Despite this file's older text and the `send_whatsapp_audio` docstring history mentioning `gTTS`, the **live code as of 2026-07-25 uses ElevenLabs exclusively** (`send_whatsapp_audio()` → `send_whatsapp_audio_elevenlabs()`, no gTTS fallback path exists anymore). Reads `elevenlabs_api_key`/`elevenlabs_voice_id` from `config.json` (default voice `21m00Tcm4TlvDq8ikWAM` "Rachel"), preprocesses text via `preprocess_text_for_tts()` (spells out `R$`/decimal values by extenso in Portuguese, adds `...` pauses after punctuation) before calling `POST /v1/text-to-speech/{voice_id}`, then sends the MP3 as base64 via `POST /message/sendMedia/{instance}` with `"mediatype": "audio"`. If `elevenlabs_api_key` is missing, it returns `False` and the caller falls back to a plain text WhatsApp reply — there's no automatic TTS provider fallback anymore.

### 5. Automatic Payment Reminders (Cobrança Ativa)
- The background task `process_payment_followups()` runs periodically in `watcher.py` (every 200 iterations / 10 minutes, including once immediately on startup since `iteration_counter` starts at 0).
- It checks Asaas payment status using `GET /v3/payments?paymentLink={checkout_id}`.
- If unpaid, it sends a 2-hour friendly distraction reminder and a 24-hour scarcity/urgency reminder. If paid, it updates `followup_status` to `"PAID"` and sends a beautiful confirmation.
- **Known quirk (not yet fixed, low severity):** the 2h/24h checks are `if elapsed >= 7200 and status == "0"` then `elif elapsed >= 86400 and status == "1"`. If the watcher is down/restarted across the entire 2h–24h window (so the 2h reminder never fired), the next run sees `elapsed >= 86400` but `status` still `"0"`, takes the **first** branch, and sends the "2 hour, need help?" wording ~24h+ late instead of the urgency one — it self-corrects and sends the correct 24h message ~10 minutes later on the following run. Cosmetic (wrong tone once), not a functional loss — mention if a client asks why a lead got two reminder messages close together.

### 6. Restarting the Watcher Service
Whenever production code (`agent.py`, `watcher.py`, etc.) is updated, you MUST restart the background poller:
1. Search active background processes: `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*watcher.py*" }` (PowerShell — more reliable on Windows than `list_background_processes`/`tasklist`, which can silently miss or duplicate entries).
2. Stop **every** matching PID with `Stop-Process -Id <PID> -Force`. Always check for duplicates before starting a new one — two watchers polling the same instance double-reply to every customer.
3. Launch a new process: `Start-Process -FilePath "python" -ArgumentList "watcher.py" -WorkingDirectory "$env:USERPROFILE\meu-agente" -WindowStyle Minimized` (keeps it alive independent of the calling shell).
4. **⚠️ Restarting can silently swallow an unanswered lead message.** `watch()` loads `watcher_state.json` once at start, then on its very first poll iteration marks every message currently in the last-20-messages window as "seen" **without replying** (anti-flood-on-boot logic) before switching to normal mode. If a customer's message arrives in the window between "last processed" and "watcher back up", it gets marked seen and never answered — and you won't see an error, just silence. Editing `seen_ids` in `watcher_state.json` on disk does **not** fix an already-running process (state is loaded once into memory, and any `save_state()` call overwrites your edit with the in-memory copy). If you suspect a message got swallowed, check `POST /chat/findMessages/{instance}` on the Evolution API directly for the timestamp, and just ask the user to resend — don't restart again to "retry", it repeats the same swallow.

### 7. Windows-Specific Gotchas (encoding, config drift, provider bugs)
- **UTF-8 console/log encoding:** Every `setup/*.py` script and `watcher.py` must reconfigure stdout/stderr to UTF-8 on Windows (`if sys.platform == "win32": sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")`, placed right after the imports) and `logging.FileHandler(...)` must be given `encoding="utf-8"` explicitly. Without this, any print/log containing emoji (✅, 🔍, etc.) crashes with `UnicodeEncodeError` on the default `cp1252` codepage. This fix now lives in all `setup/*.py` files and in both `watcher.py` and `templates/whatsapp/watcher_template.py` — keep it when regenerating.
- **`connect_whatsapp.py` QR display:** Evolution API's `/instance/connect/{instance}` response has two QR fields: `code` (raw pairing string — feed this to the `qrcode` library for ASCII terminal rendering) and `base64` (a ready-made PNG data URL — only useful for `show_qr_image`/opening as a file). The old code tried to `base64.b64decode(...).decode("utf-8")` the PNG bytes as if they were the raw pairing text, which always throws `UnicodeDecodeError` (PNG magic byte `0x89` isn't valid UTF-8). Fixed: `show_qr_terminal` now takes the raw `code` string directly; `display_qr(qr_code_raw, qr_base64)` picks whichever is available. If a user says the ASCII QR "doesn't scan" in their terminal, fall back to `show_qr_image(qr_base64)` directly (opens as a Windows image file, much easier to scan than tiny terminal glyphs).
- **Config drift between `config.json` and the generated agent:** `AI_PROVIDER` / `AI_MODEL` / `AI_API_KEY` are baked as hardcoded constants at the top of `meu-agente/agent_core.py` (and mirrored in `meu-agente/.env`, though `.env` is NOT read at runtime by `agent_core.py`). Updating `~/.meu-agente/config.json` alone (e.g. via `config_manager.save()`) does **nothing** to the live agent — you must edit `agent_core.py`'s `AI_PROVIDER`/`AI_MODEL`/`AI_API_KEY` constants directly (or regenerate from `agent_core_template.py`), update `.env` for consistency, and then restart the watcher (section 6). Always verify by grepping `agent_core.py` for these constants before assuming a provider/key swap took effect — this exact drift once left an agent running on a stale Gemini key for a day after the user had switched to Anthropic in the setup conversation.
- **Anthropic 400 Bad Request from `[SISTEMA: ...]` price/shipping injections:** `agent.py`'s `handle_message()` injects dynamic pricing/shipping instructions as `{"role": "system", "content": ...}` **inside** the `messages` list (see step 4 in section 1, `prompt_injection`). OpenAI and Gemini's OpenAI-compatible endpoint both accept a `system`-role message anywhere in the array, but **Anthropic's `/v1/messages` only accepts `user`/`assistant` roles in `messages`** — a `system` entry there causes an HTTP 400. Because `call_anthropic()` used to swallow `HTTPError` into `f"Erro Anthropic: {e.reason}"` and return it as the chat reply, this bug shipped the literal string **"Erro Anthropic: Bad Request" straight to the customer on WhatsApp** whenever a lead had already given measurements (which is exactly when the price injection fires). Fixed in `agent_core.py`/`agent_core_template.py`: `call_anthropic()` now strips any `role: "system"` entries out of `messages` and folds their content into the top-level `system` parameter instead, and on any remaining API error it logs `e.code`/`e.reason`/the response body via `print()` and returns a graceful Portuguese fallback ("Desculpe, tive um probleminha técnico...") instead of leaking the raw error to the lead. When debugging "the agent sent a weird/technical message to a customer," always suspect this pattern first — reproduce with `handle_message(phone, name, text)` directly against the customer's real phone number (their saved session/metadata is often what triggers provider-specific edge cases that a fresh test number won't hit).
- **Verified working model string:** `claude-opus-4-6` (tested live against the real Anthropic API on 2026-07-25) — use this unless the user asks for a different Claude model.
