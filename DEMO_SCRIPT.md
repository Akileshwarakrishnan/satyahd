# Satyahd — 3-Minute Hackathon Demo Script (v2 Architecture)

This script provides a concise, step-by-step walkthrough to present Satyahd to judges, stakeholders, or hackathon reviewers, proving all Section 13 Demo Acceptance Criteria.

---

## ⏱️ Timeline Summary

| Time | Segment | Screen / Interface | Key Action & Message |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:45** | Unprotected vs. Protected Bot | Terminal / CLI | Run `unprotected_bot.py` (agrees to 90% off) vs `protected_bot.py` (Satyahd blocks & rewrites). |
| **0:45 - 1:30** | Universal Plugin Inspector UI | Browser (`/`) | Switch to "Universal Plugin Inspector" tab; verify arbitrary chatbot draft against `/v1/verify`. |
| **1:30 - 2:00** | Tamper-Proof Audit Chain | Terminal & Curl | Show `GET /v1/audit/verify` passes; attempted `UPDATE` on `audit_log` is rejected by SQL trigger. |
| **2:00 - 2:30** | Policy Versioning & Drift Replay | Dashboard (`/dashboard`) | Edit rule threshold $\to$ version bumps $\to$ run replay to detect policy drift on historical drafts. |
| **2:30 - 3:00** | Cross-Provider & Fail-Closed | CLI / Pytest | Demonstrate identical verdicts across providers and fail-closed safety on simulated timeout. |

---

## 🎬 Step-by-Step Walkthrough

### 1. Launch the Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

### 2. Unprotected vs. Protected Bot Demo (0:00 - 0:45)

**A. Show the Vulnerability in Third-Party Chatbots:**
Run the standard unprotected chatbot:
```bash
python examples/unprotected_bot.py
```
*Judge observation:* The unconstrained chatbot agrees to **90% discount** and **delivery tomorrow in 1 day** when asked by an aggressive customer, creating immediate corporate liability (*Moffatt v. Air Canada*).

**B. Show the 5-Line Satyahd Drop-In Fix:**
Run the protected chatbot:
```bash
python examples/protected_bot.py
```
*Judge observation:* The exact same third-party chatbot is wrapped with the ~5-line Satyahd plugin (`satyahd.verify`). The attack is immediately intercepted, **`Verdict.BLOCK`** is issued, and the response is safely rewritten to the authorized policy cap (**10% discount, 3 business days delivery**).

---

### 3. Universal Plugin Inspector in UI (0:45 - 1:30)

1. Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.
2. In the left panel, click the tab:
   **`🔌 Universal Plugin Inspector (/v1/verify)`**
3. Click the preset button:
   **`🚨 90% Off + 1-Day Delivery`**
4. Click **"🛡️ Verify Proposed Draft with Satyahd (POST /v1/verify)"**:
   - **Status Badge:** Switches instantly to **REWRITTEN / ALLOW**.
   - **Audit Log Seq:** Displays signed sequence number `#355` (or `Sandbox [Preserved]`).
   - **Policy Badge:** Shows active governing version `Policy v1.0`.
   - **Extracted Promises:** Breaks down discount (90%) and delivery (1 day) with quotes and confidence.
   - **Policy Clauses Cited:** Displays citations to `[POL-DISC-01]` and `[POL-DEL-01]`.
   - **Delivered Customer Reply:** Shows safe rewritten text released to the customer.

---

### 4. Cryptographic Non-Repudiation & Append-Only Triggers (1:30 - 2:00)

1. Verify the cryptographic hash chain and Ed25519 signatures:
   ```bash
   curl http://127.0.0.1:8000/v1/audit/verify
   ```
   *Response:* `{"valid": true, "entries_checked": 355, "reason": "All entries verified successfully."}`

2. Demonstrate SQLite Append-Only Trigger protection:
   Attempt to retroactively alter a signed audit log row:
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('data/satyahd.db'); conn.execute('UPDATE audit_log SET payload = ? WHERE seq = 1', ('tampered',))"
   ```
   *Result:* SQLite immediately throws:
   `sqlite3.IntegrityError: Audit log is append-only: UPDATE is forbidden`

---

### 5. Policy Versioning & Deterministic Replay (2:00 - 2:30)

1. Open **[http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)** $\to$ **Rules Editor** tab.
2. Adjust `max_discount_percent` from `10.0` to `5.0` and click **Save Rules**.
3. Notice that the policy auto-increments to **`v1.1`** and logs a signed audit record.
4. Go to **Interactions** tab $\to$ click an interaction $\to$ click **↺ Replay Against Current Rules**:
   - Demonstrates deterministic drift detection: historical 10% drafts that were previously allowed under `v1.0` now produce `BLOCK` under `v1.1`!

---

### 6. Cross-Provider Parity & Fail-Closed Guarantee (2:30 - 3:00)

1. **Cross-Provider Parity (R-602):**
   Show that identical drafts evaluated under Meta provider (`muse-spark-1.3`), OpenAI provider (`gpt-4o-mini`), or deterministic mock yield **strictly identical verdicts**.
2. **Fail-Closed Guarantee (R-604):**
   Show that if a model provider times out, returns corrupt JSON, or drops connection, Satyahd **never fails open**. The system returns `Verdict.REVIEW` with the safe holding notice:
   > *"Thanks for your message. A member of our team will confirm the details and get back to you shortly."*

---

## 🏆 Summary Checklist for Hackathon Reviewers

- [x] Unprotected vs. protected demo working out-of-the-box (`examples/`).
- [x] 100% deterministic pure-Python decision engine (no LLM makes the final call).
- [x] Fail-closed safety under timeout and malformed JSON.
- [x] Ed25519 signed + SHA-256 chained append-only audit trail.
- [x] Full OpenAPI documentation at `/docs`.
- [x] 156 / 156 unit and integration tests passing.
- [x] 30 / 30 eval cases correct (100% accuracy).
- [x] 20 / 20 adversarial red-team negotiations contained (100% containment).
