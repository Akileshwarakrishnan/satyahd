# Satyahd Threat Model (v2 "Universal Middleman Plugin")

## 1. Overview & Trust Philosophy

Satyahd (सत्याह) operates on a fundamental security principle: **LLMs are non-deterministic pattern matchers and must NEVER have the final authority to bind a business legally or commercially.**

All final decisions (`ALLOW`, `BLOCK`, `REVIEW`) are evaluated by deterministic Python code against validated business rules. Any timeout, malformed payload, or uncertainty fails closed to `REVIEW` or `BLOCK`.

```
Customer ──> Host Chatbot ──> Draft Reply / Action ──> Satyahd Guardrail ──> Safe Reply / Verdict ──> Host Chatbot ──> Customer
                                                           │
                                                           ▼
                                               Deterministic Python Engine
                                                           │
                                               Ed25519 Signed Audit Chain
```

---

## 2. Threat Actors & Adversary Profiles

| Threat Actor | Motivation | Capabilities |
| :--- | :--- | :--- |
| **Adversarial Customer / Haggler** | Extract discounts, immediate free shipping, or unlimited refunds | Natural language negotiation, social engineering, lowball probes, multi-turn escalation. |
| **Prompt Injector / Jailbreaker** | Force chatbot to hallucinate company policy overrides ("VIP Demo", "Manager authorized") | System prompt leak attempts, roleplay attacks, instruction override syntax. |
| **Hallucinating / Over-eager LLM** | Close the sale at all costs (loss of constraint adherence) | Spontaneous creation of fictitious discounts, fake inventory claims, or impossible SLAs. |
| **Malicious Insider / Database Tamperer** | Erase audit trails of unauthorized transactions or alter logs | Direct SQL access, row modification, deletion attempts. |
| **Autonomous Shopping Bot** | Systematic price arbitrage and boundary probing | Automated high-frequency API requests testing discount and return policy limits. |

---

## 3. What Satyahd Protects Against (In-Scope Threats)

### 3.1. Unauthorized Commercial Commitments (*Air Canada* Liability)
- **Threat:** In *Moffatt v. Air Canada* (2024 BCCRT 149), the airline's chatbot invented a bereavement refund policy. The tribunal ruled the company was legally bound by its bot's statements.
- **Satyahd Mitigation:** Intercepts every draft reply. Pure Python checks extract all discount, delivery, refund, and stock promises. If a promise breaches company policies, it is blocked or deterministically rewritten to authorized caps.

### 3.2. Social Engineering & Authority Spoofing
- **Threat:** Attackers claim "Your manager approved 50% off" or "VIP demonstration override."
- **Satyahd Mitigation:** The host LLM may believe the user, but Satyahd ignores conversational persuasion. Only hard facts (database records, order dates, stock levels) and strict rule thresholds determine the verdict.

### 3.3. Multilingual & Tanglish Evasion
- **Threat:** Attackers switch languages (e.g., Tamil / Tanglish: *"50% thallubadi venum"*, *"paathi vela"*, *"eppovenaalum refund"*) to bypass simple English keyword blocklists.
- **Satyahd Mitigation:** Multilingual promise extraction regex and model normalization extract semantic commitments into normalized units (percent, days, units) prior to deterministic rule evaluation.

### 3.4. Action-Tool Execution Breaches (`POST /v1/verify/action`)
- **Threat:** An autonomous agent attempts to execute an action tool (e.g. `apply_discount(percent=50)`, `issue_refund(amount=5000)`) directly against transactional APIs.
- **Satyahd Mitigation:** The Action Gateway verifies arguments against configured policy rules before execution. Unauthorized tool calls are blocked before touching live backend databases.

### 3.5. Audit Log Tampering & Repudiation
- **Threat:** An attacker or malicious admin attempts to modify or delete historical interaction records in the database.
- **Satyahd Mitigation:**
  - Append-only database triggers reject `UPDATE` and `DELETE` on `audit_log`.
  - SHA-256 cryptographic hash chaining links every record to its predecessor.
  - Ed25519 digital signatures sign each record with an asymmetric private key.
  - Periodic external anchoring commits chain state to immutable local anchors.
  - `GET /v1/audit/verify` detects any modified byte, deleted sequence, or broken hash link.

### 3.6. Silent Fail-Open Failures
- **Threat:** A model provider goes down, times out, or returns corrupt JSON, causing guardrails to crash and bypass safety checks.
- **Satyahd Mitigation:** Hard Rule 2 (Fail-Closed). Any exception, timeout, or schema failure returns `verdict: "review"` with a safe holding reply, NEVER an unsafe `ALLOW`.

---

## 4. What Satyahd Does NOT Protect Against (Out-of-Scope Threats)

| Threat | Description | Recommended Upstream / Downstream Control |
| :--- | :--- | :--- |
| **Offensive / Toxic Content** | Profanity, hate speech, or harassment unrelated to commercial terms | Upstream content moderation filter (e.g., Meta Llama Guard, Perspective API). |
| **Volumetric DDoS** | High-volume Layer 4 / Layer 7 denial of service on host chatbot endpoints | Cloudflare, AWS Shield, or API Gateway rate limiting. |
| **OS / Hardware Root Compromise** | An attacker obtaining root OS shell access on the server running Satyahd | Secure Linux / Windows hardening, HSM / Cloud KMS key management (see Roadmap R-507). |
| **Flawed Executive Policy Configuration** | A company administrator intentionally setting the authorized discount rule to 99% | Multi-party authorization, approval workflows, and staging environment verification. |
| **Verbal Human Promises** | Commitments made by telephone, in-store sales representatives, or physical mail | Corporate employee training and written contract requirements. |

---

## 5. Security Boundary & Cryptographic Assurances

- **Key Generation:** Ed25519 signing keys are generated on first boot (`ed25519_key.pem`) and are ignored by version control (`.gitignore`).
- **Sandbox Isolation:** Sandbox requests (`X-Satyahd-Sandbox: true` or `sbx_` tokens) run full promise verification but do not mutate or taint the production audit chain.
- **Log Privacy:** Raw customer personally identifiable information is strictly restricted from unstructured application logs.
