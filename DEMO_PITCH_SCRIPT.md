# 🎤 Satyahd: 2-Minute Winning Pitch & Live Demo Script
**Event:** Meta AI Hackathon  
**Project:** Satyahd — Universal Trust Layer & Runtime Guardrail for AI Chatbots  
**Target Duration:** 120 Seconds (2 Minutes)

---

## ⏱️ Video / Presentation Timeline Overview

| Time | Segment | Goal |
| :--- | :--- | :--- |
| **0:00 - 0:18** | **The Hook** | Explain the critical legal & financial problem (Air Canada court case). |
| **0:18 - 0:40** | **The Solution** | Introduce Satyahd as the 5-line universal trust middleware. |
| **0:40 - 1:15** | **Live Demo** | Side-by-side: Unprotected bot leaks 90% discount vs Protected bot rewrites to 10%. |
| **1:15 - 1:45** | **Technical Depth** | Pure Python deterministic engine, Ed25519 hash chain, Meta model stack. |
| **1:45 - 2:00** | **Closing Impact** | Universal applicability across any bot, any LLM, and any language. |

---

## 🎙️ Spoken Script & Screen Actions

### [0:00 - 0:18] The Hook: The Air Canada Problem
**What to show on screen:**  
Slide with the headline: *"Civil Resolution Tribunal orders Air Canada to compensate passenger after chatbot hallucinated refund policy."*

**Spoken:**
> *"In 2024, a Canadian court held Air Canada legally liable when their customer service chatbot hallucinated a bereavement discount that violated company policy.*  
> *Every enterprise wants to deploy AI agents, but right now, every AI chatbot is a financial liability waiting to happen. Prompting cannot fix this. You cannot trust an LLM to guard another LLM."*

---

### [0:18 - 0:40] The Solution: Satyahd
**What to show on screen:**  
Satyahd Architecture Diagram: `Customer -> Host Bot -> Draft -> Satyahd -> Verdict -> Customer`

**Spoken:**
> *"Meet **Satyahd** — an enterprise trust layer and runtime guardrail for any AI chatbot.*  
> *Satyahd acts as a universal middleman. The host chatbot keeps its own conversation, but before any response is shown to a customer, it sends the draft to Satyahd.*  
> *In milliseconds, Satyahd returns a deterministic verdict, an authorized safe reply, and a cryptographically signed audit certificate."*

---

### [0:40 - 1:15] The Live Demo (Side-by-Side Proof)
**What to show on screen:**  
Open split-screen terminal or browser.

#### Step 1: Run the Unprotected Bot
**Run Command:**
```powershell
python examples/unprotected_bot.py
```
**Spoken:**
> *"Here is a standard e-commerce sales bot. When an adversarial customer asks: 'Can I get 90% off and delivery tomorrow?' — the bot immediately agrees: 'Yes! 90% off and delivery tomorrow!' An immediate legal breach."*

#### Step 2: Run the Protected Bot (The 5-Line Integration)
**Run Command:**
```powershell
python examples/protected_bot.py
```
**Spoken:**
> *"Now, we protect that exact same bot by adding just 5 lines of the Satyahd SDK.*  
> *The same attack is sent. Satyahd intercepts the draft, extracts the 90% discount and 1-day delivery commitments, checks store policies, and immediately issues a BLOCK verdict.*  
> *Satyahd automatically rewrites the reply to our authorized maximums: 'Our best authorized discount is 10% today, and shipping is 3 business days.' The liability is completely neutralized before reaching the customer!"*

---

### [1:15 - 1:45] Technical Depth: How It Works
**What to show on screen:**  
Show the Dual-Panel Web Inspector at `http://127.0.0.1:8000` and the Owner Dashboard at `/dashboard`.

**Spoken:**
> *"Under the hood, Satyahd enforces three non-negotiable architectural principles:*  
> *1. **Pure Python Deterministic Decisions:** An LLM extracts promises, but the final verdict is calculated by pure Python math against our policy registry. An LLM never makes the final decision.*  
> *2. **Fail-Closed Design:** Timeouts, unparseable JSON, or low confidence always trigger REVIEW or BLOCK — never an accidental ALLOW.*  
> *3. **Ed25519 Tamper-Evident Hash Chain:** Every verified decision is signed with an Ed25519 key and appended to a SHA-256 hash chain before the message is released. Even a database administrator cannot tamper with the audit log without breaking the chain."*

---

### [1:45 - 2:00] Closing: Meta Model Integration & Impact
**What to show on screen:**  
Show terminal running `python scripts/eval.py` (30/30 correct) and `python scripts/red_team.py --local` (20/20 contained).

**Spoken:**
> *"We benchmarked Satyahd across 174 automated tests, achieving 100% accuracy on our 30-case evaluation suite and 100% containment across 20 adversarial red-team haggling probes.*  
> *We leverage Meta's **muse-spark-1.3** with minimal reasoning effort for sub-50ms extraction, and **SAM 3.1** for appliance damage segmentation.*  
> *Satyahd turns uncontrollable chatbots into legally safe, enterprise-ready AI agents.*  
> *Thank you!"*

---

## 🛡️ Judges Q&A Defense Cheat Sheet (Word-for-Word Answers)

### Question 1: *"Why can't companies just use system prompts or OpenAI/Meta guardrails?"*
> **Answer:** *"Prompt-based guardrails fail for two reasons: non-determinism and recursive failure. System prompts are susceptible to jailbreaks, cognitive overload, and prompt injections. Furthermore, having an LLM judge whether an LLM was compliant is circular logic. Satyahd is fundamentally different: we use the model only for information extraction, but the final decision is 100% deterministic Python math evaluated against store threshold rules."*

### Question 2: *"What happens if the LLM extractor hallucinates or makes a mistake?"*
> **Answer:** *"We built a multi-layered fail-closed safety net: First, we run an exact substring quote check — if the extracted quote isn't in the raw text, confidence drops to 0.3, triggering a manual review. Second, we run a regex safety net that scans for numbers, percentages, and keywords like 'free' or 'guarantee'. If the model missed a number, the safety net catches it and flags it. Third, any extraction failure immediately fails closed to a safe holding reply."*

### Question 3: *"Doesn't adding a middleware hop introduce latency?"*
> **Answer:** *"For promise extraction, we configure Meta's `muse-spark-1.3` with `reasoning_effort: minimal`. Because extraction is a structured parsing task rather than complex creative generation, minimal reasoning cuts latency by over 60%, returning extracted JSON in ~30–45ms. The Python rule evaluation takes less than 1 millisecond. The entire round trip is negligible compared to the cost of a six-figure legal liability."*

### Question 4: *"Can this work for domains other than retail?"*
> **Answer:** *"Yes! Satyahd uses dynamic JSON rule packs. In our repo, we include `data/rule_packs/airline.json`, which specifically encodes the Air Canada bereavement refund policy. A user simply provides their domain schema with fields, operators, and thresholds, and Satyahd enforces it without any code changes."*

### Question 5: *"How do you prove the audit log hasn't been altered after the fact?"*
> **Answer:** *"Every audit entry is hashed using SHA-256 linked to the previous entry's hash, forming an append-only hash chain. Each entry is digitally signed with an Ed25519 private key. Furthermore, we install SQLite database triggers that immediately abort any `UPDATE` or `DELETE` queries with an IntegrityError. You can verify the entire historical chain at any time via `GET /v1/audit/verify`."*
