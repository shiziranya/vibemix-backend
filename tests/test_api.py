"""
VibeMix API 全量测试脚本
运行: python tests/test_api.py
"""
import json
import sys
import time

import requests

BASE = "http://localhost:5000"

# ── 颜色输出 ──────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = 0
failed = 0
skipped = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")
    if detail:
        print(f"    {RED}→ {detail}{RESET}")


def skip(msg):
    global skipped
    skipped += 1
    print(f"  {YELLOW}⊘{RESET} {msg}")


def section(title):
    print(f"\n{BOLD}{CYAN}{'─'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*50}{RESET}")


def check(name, resp, expected_code=200, check_data=True):
    try:
        body = resp.json()
    except Exception:
        fail(name, f"HTTP {resp.status_code}, non-JSON body: {resp.text[:100]}")
        return None

    if resp.status_code != expected_code:
        fail(name, f"HTTP {resp.status_code} (expected {expected_code}), code={body.get('code')}, msg={body.get('message')}")
        return None

    if check_data and body.get("code") != 0:
        fail(name, f"code={body['code']}, message={body.get('message')}")
        return None

    ok(name)
    return body.get("data")


# ── State shared across tests ─────────────────────────────
state = {}


# ═══════════════════════════════════════════════════════════
# 1. Health check
# ═══════════════════════════════════════════════════════════
section("1. Health Check")
r = requests.get(f"{BASE}/health")
if r.status_code == 200 and r.json().get("status") == "ok":
    ok("GET /health → 200 ok")
else:
    fail("GET /health", str(r.text))


# ═══════════════════════════════════════════════════════════
# 2. Auth — Register
# ═══════════════════════════════════════════════════════════
section("2. Auth — Register / Login")

phone = f"138{int(time.time()) % 100000000:08d}"
password = "test1234"

r = requests.post(f"{BASE}/api/auth/register", json={
    "phone": phone,
    "password": password,
    "nickname": "测试用户",
})
data = check("POST /api/auth/register", r, 201)
if data:
    state["access_token"] = data["access_token"]
    state["refresh_token"] = data["refresh_token"]
    state["user_id"] = data["user"]["id"]
    state["headers"] = {"Authorization": f"Bearer {data['access_token']}"}

# Duplicate register
r2 = requests.post(f"{BASE}/api/auth/register", json={"phone": phone, "password": password})
body2 = r2.json()
if r2.status_code == 409 or (r2.status_code == 400 and body2.get("code") != 0):
    ok("POST /api/auth/register (duplicate) → rejected")
elif body2.get("code") != 0:
    ok("POST /api/auth/register (duplicate) → rejected with error code")
else:
    fail("POST /api/auth/register (duplicate) should fail")

# Invalid phone
r3 = requests.post(f"{BASE}/api/auth/register", json={"phone": "123", "password": "abc123"})
if r3.json().get("code") != 0:
    ok("POST /api/auth/register (bad phone) → rejected")
else:
    fail("POST /api/auth/register (bad phone) should fail")

# Login
r = requests.post(f"{BASE}/api/auth/login", json={"phone": phone, "password": password})
data = check("POST /api/auth/login", r)
if data:
    state["access_token"] = data["access_token"]
    state["refresh_token"] = data["refresh_token"]
    state["headers"] = {"Authorization": f"Bearer {data['access_token']}"}

# Wrong password
r = requests.post(f"{BASE}/api/auth/login", json={"phone": phone, "password": "wrongpass"})
if r.json().get("code") != 0:
    ok("POST /api/auth/login (wrong password) → rejected")
else:
    fail("POST /api/auth/login (wrong password) should fail")

# GET /me
r = requests.get(f"{BASE}/api/auth/me", headers=state.get("headers", {}))
data = check("GET /api/auth/me", r)
if data:
    assert data.get("phone") == phone, "phone mismatch"
    ok("  → user phone matches")

# PUT /me
r = requests.put(f"{BASE}/api/auth/me", headers=state.get("headers", {}),
                 json={"nickname": "调酒达人"})
data = check("PUT /api/auth/me", r)
if data:
    assert data.get("nickname") == "调酒达人"
    ok("  → nickname updated")

# Refresh token
r = requests.post(f"{BASE}/api/auth/refresh",
                  headers={"Authorization": f"Bearer {state.get('refresh_token', '')}"})
data = check("POST /api/auth/refresh", r)
if data and data.get("access_token"):
    state["access_token"] = data["access_token"]
    state["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
    ok("  → new access_token issued")


# ═══════════════════════════════════════════════════════════
# 3. Ingredients search
# ═══════════════════════════════════════════════════════════
section("3. Ingredients Search")

r = requests.get(f"{BASE}/api/cabinet/ingredients", headers=state.get("headers", {}))
data = check("GET /api/cabinet/ingredients (all)", r)
if data:
    assert data["total"] > 0, "should have ingredients"
    ok(f"  → {data['total']} total ingredients")

r = requests.get(f"{BASE}/api/cabinet/ingredients?q=gin", headers=state.get("headers", {}))
data = check("GET /api/cabinet/ingredients?q=gin", r)
if data:
    assert data["total"] > 0
    state["gin_id"] = data["items"][0]["id"]
    ok(f"  → found {data['total']} gin-related ingredients, first id={state['gin_id']}")

r = requests.get(f"{BASE}/api/cabinet/ingredients?category=base_spirit&per_page=5",
                 headers=state.get("headers", {}))
data = check("GET /api/cabinet/ingredients?category=base_spirit", r)
if data:
    assert all(i["is_base_spirit"] for i in data["items"])
    ok(f"  → all {len(data['items'])} items are base spirits")
    # Grab a few spirit IDs for cabinet tests
    state["spirit_ids"] = [i["id"] for i in data["items"][:3]]


# ═══════════════════════════════════════════════════════════
# 4. Cabinet
# ═══════════════════════════════════════════════════════════
section("4. Cabinet Management")

# Empty cabinet
r = requests.get(f"{BASE}/api/cabinet", headers=state.get("headers", {}))
data = check("GET /api/cabinet (empty)", r)
if data:
    assert data["total"] == 0
    ok("  → empty cabinet confirmed")

# Stats (empty)
r = requests.get(f"{BASE}/api/cabinet/stats", headers=state.get("headers", {}))
data = check("GET /api/cabinet/stats (empty)", r)
if data:
    assert data["total_spirits"] == 0
    ok(f"  → stats: {data}")

# Add spirits
for sid in state.get("spirit_ids", [])[:3]:
    r = requests.post(f"{BASE}/api/cabinet/items", headers=state.get("headers", {}),
                      json={"ingredient_id": sid})
    data = check(f"POST /api/cabinet/items (id={sid})", r, 201)

# Add duplicate → should fail
if state.get("spirit_ids"):
    r = requests.post(f"{BASE}/api/cabinet/items", headers=state.get("headers", {}),
                      json={"ingredient_id": state["spirit_ids"][0]})
    if r.json().get("code") != 0:
        ok("POST /api/cabinet/items (duplicate) → rejected")
    else:
        fail("POST /api/cabinet/items (duplicate) should fail")

# Stats after adding
r = requests.get(f"{BASE}/api/cabinet/stats", headers=state.get("headers", {}))
data = check("GET /api/cabinet/stats (after add)", r)
if data:
    assert data["total_spirits"] >= 1
    ok(f"  → stats: spirits={data['total_spirits']}, unlocked={data['unlocked_recipes']}")
    state["unlocked_count"] = data["unlocked_recipes"]

# List cabinet
r = requests.get(f"{BASE}/api/cabinet", headers=state.get("headers", {}))
data = check("GET /api/cabinet (with items)", r)
if data:
    assert data["total"] >= 1
    ok(f"  → {data['total']} items in cabinet")

# Preview unlock
if state.get("gin_id"):
    r = requests.get(f"{BASE}/api/cabinet/preview?ingredient_id={state['gin_id']}",
                     headers=state.get("headers", {}))
    data = check("GET /api/cabinet/preview", r)
    if data is not None:
        ok(f"  → adding gin would unlock {data['new_unlock_count']} more recipes")

# Remove one spirit
if state.get("spirit_ids"):
    remove_id = state["spirit_ids"][-1]
    r = requests.delete(f"{BASE}/api/cabinet/items/{remove_id}",
                        headers=state.get("headers", {}))
    data = check(f"DELETE /api/cabinet/items/{remove_id}", r)
    if data:
        ok(f"  → after remove: spirits={data['total_spirits']}")
    # Re-add it
    requests.post(f"{BASE}/api/cabinet/items", headers=state.get("headers", {}),
                  json={"ingredient_id": remove_id})


# ═══════════════════════════════════════════════════════════
# 5. Cocktails
# ═══════════════════════════════════════════════════════════
section("5. Cocktails")

r = requests.get(f"{BASE}/api/cocktails?limit=5", headers=state.get("headers", {}))
data = check("GET /api/cocktails?limit=5", r)
if data:
    assert len(data["items"]) == 5
    state["cocktail_id"] = data["items"][0]["id"]
    ok(f"  → first cocktail: id={state['cocktail_id']}, name={data['items'][0]['name']}")

r = requests.get(f"{BASE}/api/cocktails?q=negroni", headers=state.get("headers", {}))
data = check("GET /api/cocktails?q=negroni", r)
if data:
    ok(f"  → search 'negroni': {data['count']} results")

# Cocktail detail
if state.get("cocktail_id"):
    r = requests.get(f"{BASE}/api/cocktails/{state['cocktail_id']}",
                     headers=state.get("headers", {}))
    data = check(f"GET /api/cocktails/{state['cocktail_id']}", r)
    if data:
        assert "ingredients" in data
        assert "steps" in data
        ok(f"  → {len(data['ingredients'])} ingredients, {len(data['steps'])} steps")
        # Check ingredient status annotation
        statuses = {i["status"] for i in data["ingredients"]}
        ok(f"  → ingredient statuses: {statuses}")

    # Steps endpoint
    r = requests.get(f"{BASE}/api/cocktails/{state['cocktail_id']}/steps",
                     headers=state.get("headers", {}))
    data = check(f"GET /api/cocktails/{state['cocktail_id']}/steps", r)
    if data:
        ok(f"  → {len(data['steps'])} steps returned")

# 404 cocktail
r = requests.get(f"{BASE}/api/cocktails/999999", headers=state.get("headers", {}))
if r.json().get("code") != 0:
    ok("GET /api/cocktails/999999 → 404 error code")
else:
    fail("GET /api/cocktails/999999 should return error")


# ═══════════════════════════════════════════════════════════
# 6. Recommend
# ═══════════════════════════════════════════════════════════
section("6. AI Recommend")

recommend_payload = {
    "mood_tags": ["relaxing"],
    "abv_pref": "any",
    "flavor_tags": [],
    "recipe_type": "classic",
    "free_text": "今天很累，想要简单的",
}

r = requests.post(f"{BASE}/api/recommend", headers=state.get("headers", {}),
                  json=recommend_payload)
data = check("POST /api/recommend", r)
if data:
    assert "session_id" in data
    assert "cocktail" in data
    assert "ai" in data
    assert "ingredients" in data
    state["session_id"] = data["session_id"]
    state["recommended_cocktail_id"] = data["cocktail"]["id"]
    ok(f"  → session={data['session_id']}")
    ok(f"  → cocktail: {data['cocktail']['name_zh'] or data['cocktail']['name']}")
    ok(f"  → ai.reason: {data['ai']['reason'][:50]}...")
    ok(f"  → ai.poetic_copy: {data['ai']['poetic_copy']}")
    ok(f"  → {len(data['ingredients'])} ingredients annotated")

# Refresh (换一个)
if state.get("session_id"):
    r = requests.post(f"{BASE}/api/recommend/refresh", headers=state.get("headers", {}),
                      json={"session_id": state["session_id"]})
    data = check("POST /api/recommend/refresh (换一个)", r)
    if data:
        assert data["session_id"] == state["session_id"]
        ok(f"  → new cocktail: {data['cocktail']['name_zh'] or data['cocktail']['name']}")

# Invalid session
r = requests.post(f"{BASE}/api/recommend/refresh", headers=state.get("headers", {}),
                  json={"session_id": "sess_nonexistent"})
if r.json().get("code") != 0:
    ok("POST /api/recommend/refresh (bad session) → error")
else:
    fail("POST /api/recommend/refresh (bad session) should fail")

# Invalid mood tag
r = requests.post(f"{BASE}/api/recommend", headers=state.get("headers", {}),
                  json={"mood_tags": ["invalid_tag"]})
if r.json().get("code") != 0:
    ok("POST /api/recommend (invalid mood_tag) → validation error")
else:
    fail("POST /api/recommend (invalid mood_tag) should fail")

# History
r = requests.get(f"{BASE}/api/recommend/history", headers=state.get("headers", {}))
data = check("GET /api/recommend/history", r)
if data:
    assert data["total"] >= 1
    ok(f"  → {data['total']} history records")


# ═══════════════════════════════════════════════════════════
# 7. Card
# ═══════════════════════════════════════════════════════════
section("7. Card Generation")

if state.get("recommended_cocktail_id") and state.get("session_id"):
    card_payload = {
        "session_id": state["session_id"],
        "cocktail_id": state["recommended_cocktail_id"],
        "layout": "portrait",
        "mood_caption": "今晚的心情是微醺放松，所以调了这杯鸡尾酒",
        "ai_copy": "苦中带甜，像某个值得的夜晚。",
        "ingredients": [{"name_zh": "金酒", "measure_raw": "1 oz", "status": "owned"}],
    }
    r = requests.post(f"{BASE}/api/card/generate", headers=state.get("headers", {}),
                      json=card_payload)
    data = check("POST /api/card/generate", r, 202)
    if data:
        assert data["status"] == "pending"
        state["card_id"] = data["card_id"]
        ok(f"  → card_id={data['card_id']}, status=pending")

    # Poll card status
    if state.get("card_id"):
        time.sleep(1)
        r = requests.get(f"{BASE}/api/card/{state['card_id']}",
                         headers=state.get("headers", {}))
        data = check(f"GET /api/card/{state['card_id']}", r)
        if data:
            ok(f"  → status={data['status']}")

    # My cards
    r = requests.get(f"{BASE}/api/card/my", headers=state.get("headers", {}))
    data = check("GET /api/card/my", r)
    if data:
        ok(f"  → {data['total']} cards total")

    # Invalid card id
    r = requests.get(f"{BASE}/api/card/not-a-uuid", headers=state.get("headers", {}))
    if r.json().get("code") != 0:
        ok("GET /api/card/not-a-uuid → validation error")
    else:
        fail("GET /api/card/not-a-uuid should fail")

    # Invalid layout
    r = requests.post(f"{BASE}/api/card/generate", headers=state.get("headers", {}),
                      json={**card_payload, "layout": "invalid"})
    if r.json().get("code") != 0:
        ok("POST /api/card/generate (bad layout) → validation error")
    else:
        fail("POST /api/card/generate (bad layout) should fail")
else:
    skip("Card tests skipped (no session_id or cocktail_id)")


# ═══════════════════════════════════════════════════════════
# 8. Auth — JWT protection
# ═══════════════════════════════════════════════════════════
section("8. JWT Protection")

protected_endpoints = [
    ("GET", f"{BASE}/api/auth/me"),
    ("GET", f"{BASE}/api/cabinet"),
    ("GET", f"{BASE}/api/cabinet/stats"),
    ("POST", f"{BASE}/api/recommend"),
    ("GET", f"{BASE}/api/cocktails"),
]
for method, url in protected_endpoints:
    r = requests.request(method, url)
    if r.status_code == 401:
        ok(f"{method} {url.replace(BASE,'')} → 401 without token")
    else:
        fail(f"{method} {url.replace(BASE,'')} should be 401 without token, got {r.status_code}")


# ═══════════════════════════════════════════════════════════
# 9. Logout
# ═══════════════════════════════════════════════════════════
section("9. Logout")
r = requests.post(f"{BASE}/api/auth/logout", headers=state.get("headers", {}))
data = check("POST /api/auth/logout", r)
if data is not None or r.json().get("code") == 0:
    ok("  → logout successful")


# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
total = passed + failed + skipped
print(f"\n{BOLD}{'═'*50}{RESET}")
print(f"{BOLD}  Test Summary{RESET}")
print(f"{'═'*50}")
print(f"  {GREEN}Passed : {passed}{RESET}")
print(f"  {RED}Failed : {failed}{RESET}")
print(f"  {YELLOW}Skipped: {skipped}{RESET}")
print(f"  Total  : {total}")
print(f"{'═'*50}\n")

if failed > 0:
    sys.exit(1)
