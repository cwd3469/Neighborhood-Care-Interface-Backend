"""
권한 회귀 테스트 — security-fix(V1~V6, G-01) + 요양사 담당 범위(B안: 일정 기반, 기록 목록 B2)

seed 구성은 conftest.py 참고:
  cg_a → S1 담당 / cg_b → S1·S2 담당 / g1 → S1 / g2 → S2
"""
import pytest


def ids(resp):
    return sorted(item["id"] for item in resp.json())


# ── 인증 · 역할 고정 ─────────────────────────────────────────

def test_no_token_is_401(client, seed):
    assert client.get("/seniors").status_code == 401


def test_register_forces_caregiver_role(client, seed):
    # V1: body에 admin을 넣어도 caregiver로 저장
    resp = client.post("/register", json={"username": "hacker", "password": "x", "role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "caregiver"


def test_non_admin_cannot_create_user(client, seed):
    h = seed["headers"]
    body = {"username": "new", "password": "x", "role": "admin"}
    for who in ("cg_a", "g1"):
        assert client.post("/admin/users", json=body, headers=h[who]).status_code == 403


# ── 어르신 ───────────────────────────────────────────────────

@pytest.mark.parametrize("who,senior_key,expected", [
    ("g1", "s1", 200), ("g1", "s2", 403),      # V2: 보호자는 연결된 어르신만
    ("cg_a", "s1", 200), ("cg_a", "s2", 403),  # 요양사는 담당 어르신만
    ("admin", "s2", 200),
])
def test_read_senior_access(client, seed, who, senior_key, expected):
    resp = client.get(f"/seniors/{seed[senior_key]}", headers=seed["headers"][who])
    assert resp.status_code == expected


def test_senior_list_scoped_by_role(client, seed):
    h = seed["headers"]
    assert ids(client.get("/seniors", headers=h["g1"])) == [seed["s1"]]
    assert ids(client.get("/seniors", headers=h["cg_a"])) == [seed["s1"]]
    assert ids(client.get("/seniors", headers=h["cg_b"])) == sorted([seed["s1"], seed["s2"]])
    assert ids(client.get("/seniors", headers=h["admin"])) == sorted([seed["s1"], seed["s2"]])


# ── 일정 ─────────────────────────────────────────────────────

def test_schedule_list_scoped_by_role(client, seed):
    h = seed["headers"]
    # 보호자: 연결된 어르신(S1)의 일정만 — 요양사 무관
    assert ids(client.get("/schedules", headers=h["g1"])) == sorted([seed["sch_a1"], seed["sch_b1"]])
    # 보호자가 남의 어르신 id로 필터해도 빈 배열
    assert client.get(f"/schedules?senior_id={seed['s2']}", headers=h["g1"]).json() == []
    # 요양사: 본인 일정만
    assert ids(client.get("/schedules", headers=h["cg_a"])) == [seed["sch_a1"]]


def test_schedule_response_has_caregiver_name(client, seed):
    resp = client.get(f"/schedules/{seed['sch_a1']}", headers=seed["headers"]["admin"])
    assert resp.json()["caregiver_name"] == "cg_a"


@pytest.mark.parametrize("who,sch_key,expected", [
    ("g1", "sch_a1", 200), ("g1", "sch_b2", 403),
    ("cg_a", "sch_a1", 200), ("cg_a", "sch_b1", 403),  # 같은 어르신이어도 남의 일정은 403
    ("admin", "sch_b2", 200),
])
def test_read_schedule_access(client, seed, who, sch_key, expected):
    resp = client.get(f"/schedules/{seed[sch_key]}", headers=seed["headers"][who])
    assert resp.status_code == expected


@pytest.mark.parametrize("who,expected", [
    ("g1", 403),    # 보호자는 상태 변경 불가
    ("cg_b", 403),  # 다른 요양사 일정
    ("cg_a", 200),  # 담당 요양사
    ("admin", 200),
])
def test_change_schedule_status(client, seed, who, expected):
    resp = client.patch(
        f"/schedules/{seed['sch_a1']}/status",
        json={"status": "completed"},
        headers=seed["headers"][who],
    )
    assert resp.status_code == expected


def test_only_admin_creates_schedule(client, seed):
    body = {
        "senior_id": seed["s1"], "caregiver_id": seed["users"]["cg_a"].id,
        "scheduled_date": "2026-12-01", "start_time": "09:00:00", "end_time": "10:00:00",
    }
    assert client.post("/schedules", json=body, headers=seed["headers"]["cg_a"]).status_code == 403
    assert client.post("/schedules", json=body, headers=seed["headers"]["admin"]).status_code == 200


# ── 방문 기록 ────────────────────────────────────────────────

def test_record_list_scoped_by_role(client, seed):
    h = seed["headers"]
    # G-01: 보호자는 연결된 어르신 기록만
    assert ids(client.get("/records", headers=h["g1"])) == sorted([seed["rec_a1"], seed["rec_b1"]])
    # B2: 요양사는 담당 어르신 기록 전체 (다른 요양사가 쓴 rec_b1 포함, 담당 아닌 S2 기록 제외)
    assert ids(client.get("/records", headers=h["cg_a"])) == sorted([seed["rec_a1"], seed["rec_b1"]])
    assert client.get(f"/records?senior_id={seed['s2']}", headers=h["cg_a"]).json() == []
    assert len(client.get("/records", headers=h["admin"]).json()) == 3


@pytest.mark.parametrize("who,rec_key,expected", [
    ("g1", "rec_a1", 200), ("g1", "rec_b2", 403),      # V3
    ("cg_a", "rec_b1", 200),                           # B2: 담당 어르신이면 남이 쓴 기록도 열람
    ("cg_a", "rec_b2", 403),
])
def test_read_record_and_vitals_access(client, seed, who, rec_key, expected):
    h = seed["headers"][who]
    rid = seed[rec_key]
    assert client.get(f"/records/{rid}", headers=h).status_code == expected
    assert client.get(f"/records/{rid}/vitals", headers=h).status_code == expected  # V4


def test_missing_record_is_404(client, seed):
    assert client.get("/records/9999", headers=seed["headers"]["admin"]).status_code == 404


@pytest.mark.parametrize("who,senior_key,expected", [
    ("g1", "s1", 200), ("g1", "s2", 403),  # V5
    ("cg_a", "s2", 403),
])
def test_senior_vitals_access(client, seed, who, senior_key, expected):
    resp = client.get(f"/vitals/seniors/{seed[senior_key]}", headers=seed["headers"][who])
    assert resp.status_code == expected


def _record_body(senior_id, schedule_id=None):
    return {
        "senior_id": senior_id,
        "schedule_id": schedule_id,
        "fhir_response": {
            "resourceType": "QuestionnaireResponse",
            "authored": "2026-11-20T10:30:00",
            "item": [{"linkId": "heart-rate", "answer": [{"valueInteger": 72}]}],
        },
        "visit_notes": "식사 양호",
    }


def test_create_record_rules(client, seed):
    h = seed["headers"]
    # 보호자는 기록 생성 불가
    assert client.post("/records", json=_record_body(seed["s1"]), headers=h["g1"]).status_code == 403
    # 담당 아닌 어르신
    assert client.post("/records", json=_record_body(seed["s2"]), headers=h["cg_a"]).status_code == 403
    # 일정의 어르신과 기록의 어르신이 다름 (cg_b는 S1·S2 모두 담당)
    resp = client.post("/records", json=_record_body(seed["s1"], seed["sch_b2"]), headers=h["cg_b"])
    assert resp.status_code == 400
    # 담당 어르신이어도 남의 일정에는 기록 불가
    resp = client.post("/records", json=_record_body(seed["s1"], seed["sch_b1"]), headers=h["cg_a"])
    assert resp.status_code == 403
    # 정상 — 본인 일정 + 담당 어르신 → 활력징후도 같이 저장
    resp = client.post("/records", json=_record_body(seed["s1"], seed["sch_a1"]), headers=h["cg_a"])
    assert resp.status_code == 200
    vitals = client.get(f"/records/{resp.json()['id']}/vitals", headers=h["cg_a"]).json()
    assert [(v["loinc_code"], v["value"]) for v in vitals] == [("8867-4", 72)]


# ── AI 요약 (권한 검사만 — Claude API는 호출되지 않는 경로) ─────

@pytest.mark.parametrize("method,path", [
    ("post", "/ai/summarize/{rec_b2}"),
    ("get", "/ai/summary/{rec_b2}"),
    ("post", "/ai/senior-summary/{s2}"),
    ("get", "/ai/senior-summary/{s2}"),
])
def test_ai_endpoints_block_other_guardian(client, seed, method, path):
    # V6: 남의 어르신이면 LLM 호출 전에 403
    url = path.format(**seed)
    resp = getattr(client, method)(url, headers=seed["headers"]["g1"])
    assert resp.status_code == 403
