import asyncio
import json
import httpx
from app.main import app
from app.db import init_db

# 25 Realistic & Diverse Test Messages
TEST_SCENARIOS = [
    # 1. Material
    ("F101", "What material is this made of?", "100% French Organic Linen"),
    # 2. GSM
    ("F101", "What is the gsm and fabric weight?", "165 GSM"),
    # 3. Fabric feel
    ("F101", "How does the fabric feel on skin?", "breathable"),
    # 4. Stretch
    ("F101", "Is it stretchy?", "Non-stretch"),
    # 5. Fit & Clarifying question
    ("F101", "Will it fit me?", "?"),
    # 6. Care & Wash
    ("F101", "How do I wash and care for this?", "wash cold"),
    # 7. Colors
    ("F101", "What about in black?", "black"),
    # 8. Season
    ("F101", "Is it good for summer?", "Summer"),
    # 9. Tanglish season
    ("F101", "indha shirt summer-ku set aaguma?", "Summer"),
    # 10. Tanglish stretch
    ("F103", "stretch irukuma?", "stretch"),
    # 11. Chino GSM & Fit
    ("F103", "Tell me about the chinos fit and stretch", "Slim Tapered"),
    # 12. Heavyweight Tee GSM
    ("F102", "What is the gsm of the cotton tee?", "240 GSM"),
    # 13. Heavyweight Tee Feel
    ("F102", "Is the tee soft?", "peach-skin"),
    # 14. Kurti Out of stock
    ("F104", "Is the Zari Silk Kurti in stock?", "out of stock"),
    # 15. Merino Cardigan Care
    ("F105", "How do I wash the merino cardigan?", "Hand wash cold"),
    # 16. Merino Cardigan GSM
    ("F105", "What is the gsm of this cardigan?", "320 GSM"),
    # 17. Styling advice
    ("F101", "How should I style this shirt?", "chinos"),
    # 18. Pricing
    ("F101", "How much does it cost?", "₹1,899"),
    # 19. Delivery
    ("F101", "When will it reach me?", "business days"),
    # 20. Returns
    ("F101", "What is your return policy?", "7-day"),
    # 21. Transparency
    ("F101", "Is it see-through?", "opaque"),
    # 22. Human Escalation
    ("F101", "Can I speak to a real person?", "human"),
    # 23. Greeting
    ("F101", "Hello! Good morning", "Hello"),
    # 24. Acknowledgment
    ("F101", "Thank you, that was very helpful", "welcome"),
    # 25. Typo inquiry
    ("F101", "is it strechy and brethable?", "breathab"),
]

async def run_n_messages_test():
    print("==================================================================", flush=True)
    print(f"RUNNING RIGOROUS TEST ON {len(TEST_SCENARIOS)} CONVERSATIONAL MESSAGES", flush=True)
    print("==================================================================", flush=True)
    init_db()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Step A: Test /products/catalog
        r_cat = await client.get("/products/catalog")
        assert r_cat.status_code == 200, f"/products/catalog status {r_cat.status_code}"
        prods = r_cat.json()["products"]
        print(f"[OK] 1. Catalog API alive: returned {len(prods)} products", flush=True)

        passed = 0
        failed = 0

        # Step B: Test all 25 messages across Streaming & Regular endpoints
        for idx, (pid, msg, expected_keyword) in enumerate(TEST_SCENARIOS, 1):
            sess_id = f"test_session_{idx}"
            
            # 1. Test POST /chat/stream (SSE)
            tokens = []
            events = []
            done_chips = []
            async with client.stream("POST", "/chat/stream", json={
                "message": msg,
                "session_id": sess_id,
                "product_id": pid
            }) as resp:
                assert resp.status_code == 200, f"SSE failed on '{msg}' with status {resp.status_code}"
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        raw = line[5:].strip()
                        if raw:
                            data = json.loads(raw)
                            events.append(data.get("type"))
                            if data.get("type") == "token":
                                tokens.append(data.get("token"))
                            elif data.get("type") == "done":
                                done_chips = data.get("chips", [])

            full_reply = "".join(tokens)
            has_kw = expected_keyword.lower() in full_reply.lower()

            # 2. Test fallback POST /chat with same message
            r_chat = await client.post("/chat", data={
                "session_id": sess_id,
                "agent_id": "A",
                "mode": "careful",
                "message": msg
            })
            assert r_chat.status_code == 200, f"POST /chat failed on '{msg}'"
            chat_reply = r_chat.json().get("final_reply", "")

            if has_kw and len(tokens) > 3 and "meta" in events and "done" in events:
                passed += 1
                status_icon = "✓ PASS"
            else:
                failed += 1
                status_icon = "✗ FAIL"

            print(f"[{status_icon}] Msg {idx:2d} ({pid}): \"{msg[:35]}\" -> Kw: '{expected_keyword}' | Chips: {len(done_chips)}", flush=True)

        print("\n==================================================================", flush=True)
        print(f"TEST RESULTS: {passed}/{len(TEST_SCENARIOS)} PASSED | {failed} FAILED", flush=True)
        print("==================================================================", flush=True)
        assert failed == 0, f"{failed} test messages failed"

if __name__ == "__main__":
    asyncio.run(run_n_messages_test())
