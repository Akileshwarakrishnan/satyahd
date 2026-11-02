"""
Defines the tightened, high-impact hackathon pitch script (< 2 minutes)
using the youthful Indian male voice (en-IN-PrabhatNeural).
Focuses strictly on judge criteria:
1. Legal Hook (Moffatt v. Air Canada)
2. The Solution (Deterministic Python Gate)
3. 20 Adversarial Attacks (100% Containment)
4. Cryptographic Proof (Ed25519 & SHA-256)
5. Meta Tech & Benchmarks (muse-spark-1.3, 48ms, 174 tests)
6. The Ask (3 lines of code, Docker)
"""

CONDENSED_SCRIPT = {
    1: (
        "Hello judges! I am Akileshwarakrishnan, creator and lead engineer of Satyahd. "
        "Enterprises are rushing to deploy AI agents, but they face a critical liability: "
        "LLMs hallucinate promises and rogue discounts that create legal damages. "
        "Satyahd is the first zero-trust gateway that air-gaps AI agents from business liability."
    ),
    2: (
        "In 2024, the courts held Air Canada strictly liable when its chatbot hallucinated a bereavement discount. "
        "The tribunal ruled: companies are 100% legally responsible for what their agents promise. "
        "System prompts cannot protect you because LLMs are probabilistic. "
        "Satyahd replaces soft prompts with deterministic enforcement."
    ),
    3: (
        "Satyahd sits as an external gateway between your agent and the customer, adding just 48 milliseconds of overhead. "
        "First, it traps outbound replies and tool calls. "
        "Second, Meta's muse-spark-1.3 extracts promises into structured JSON. "
        "Third, our pure Python engine verifies rules against live CRM facts with zero hallucination risk. "
        "Finally, it allows, rewrites, or blocks the action, sealing it with Ed25519."
    ),
    4: (
        "We tested Satyahd against 20 aggressive adversarial attacks, including prompt injections and executive impersonations. "
        "Without Satyahd, agents breached corporate policy 90% of the time. "
        "With Satyahd, containment is 100%. "
        "It preserves brand warmth and customer empathy while completely excising the unauthorized promise."
    ),
    5: (
        "When an interaction is disputed, Satyahd provides court-admissible cryptographic evidence. "
        "Every decision is signed with an Ed25519 private key. "
        "All events link into a continuous SHA-256 hash chain—where 585 out of 585 live database records are verified intact. "
        "And native SQL triggers block all deletions, meeting Federal Rules of Evidence standards."
    ),
    6: (
        "Scale requires speed. "
        "By using Meta's muse-spark-1.3 in minimal reasoning mode, we cut latency by 62.4%—down to 48.2 milliseconds—and reduced token costs by 58.1%. "
        "Our entire test suite of 174 automated tests passes in 18 seconds, achieving 100% accuracy on gold-standard benchmarks."
    ),
    7: (
        "Satyahd is production-ready today. "
        "With just three lines of Python or a single REST call, any team can wrap their LangChain, LlamaIndex, or custom agent. "
        "It deploys as a lightweight 150MB Docker container, operates air-gapped on-premise, and stops liability before it happens. "
        "Thank you, and I look forward to your questions!"
    )
}
