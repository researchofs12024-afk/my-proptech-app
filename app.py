"""
부동산 통합 플랫폼 - 카카오맵
===============================
[구조]
  app.py
  kakao_component/
    index.html   ← 카카오맵 (고정 경로 → 번쩍거림 없음)

[JS→Python 통신]
  Streamlit.setComponentValue({lat, lng})
  → declare_component 공식 채널
  → window.top / location 우회 없음

[흐름]
  1. 지도 클릭 → JS: setComponentValue({lat, lng})
  2. Python: coord 수신 → 카카오REST + 건축물대장 API 호출
  3. session_state 갱신 → st.rerun()
  4. 우측 패널에 결과 표시
  5. Python이 컴포넌트에 pnu, lat, lng 재전달 → 지도 유지
"""

import os
import json
import requests
import urllib3
import streamlit as st
import streamlit.components.v1 as components

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAP_JS_KEY    = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "668fc8777ccf99d71bfe4be308a90047"
LEDGER_KEY    = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY    = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(
    page_title="부동산 통합 플랫폼",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
    .block-container { padding: 0.5rem 1rem !important; }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu, footer { display: none; }
</style>
""", unsafe_allow_html=True)

# ── 세션 초기화 ──────────────────────────────────────────
for k, v in {
    "map_lat":   37.5668,
    "map_lng":   126.9786,
    "addr":      None,
    "pnu":       None,
    "items":     None,
    "err":       None,
    "last_coord": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── 컴포넌트 고정 경로 선언 ──────────────────────────────
# app.py 기준 상대 경로 → 매 rerun에도 동일 경로 → 번쩍거림 없음
_COMP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kakao_component")
_kakao_map = components.declare_component("kakao_map", path=_COMP_PATH)


# ── API 함수 ─────────────────────────────────────────────
def normalize_items(raw):
    if raw is None:           return []
    if isinstance(raw, dict): return [raw]
    if isinstance(raw, list): return raw
    return []


def get_building_data(lat: float, lng: float):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        reg = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}",
            headers=headers, timeout=5).json()
        b_code = next(
            (d["code"] for d in reg.get("documents", []) if d.get("region_type") == "B"), None)

        adr = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}",
            headers=headers, timeout=5).json()

        if not b_code:
            return None, None, None, "법정동 코드 없음 (도로·하천 구역)"
        if not adr.get("documents"):
            return None, None, None, "주소 정보 없음"

        a   = adr["documents"][0]["address"]
        bun = a["main_address_no"]
        ji  = a["sub_address_no"] or "0"
        pnu = b_code + "1" + bun.zfill(4) + ji.zfill(4)

        res = requests.get(
            "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
            params={"serviceKey": LEDGER_KEY, "sigunguCd": b_code[:5],
                    "bjdongCd": b_code[5:10], "platGbCd": "0",
                    "bun": bun.zfill(4), "ji": ji.zfill(4),
                    "pageNo": "1", "numOfRows": "30", "_type": "json"},
            verify=False, timeout=10).json()

        raw   = res.get("response", {}).get("body", {}).get("items", {})
        items = normalize_items(raw.get("item") if isinstance(raw, dict) else None)
        return a["address_name"], pnu, items, None

    except requests.exceptions.Timeout:
        return None, None, None, "API 시간 초과"
    except Exception as e:
        return None, None, None, f"오류: {e}"


# ── 레이아웃 ─────────────────────────────────────────────
st.title("🗺️ 부동산 통합 플랫폼")
col_map, col_info = st.columns([3, 1])

# ── 우측 정보 패널 ────────────────────────────────────────
with col_info:
    st.subheader("📋 건축물 정보")
    if st.session_state.err:
        st.error(st.session_state.err)
    elif not st.session_state.addr:
        st.info("지도를 클릭하면\n건축물대장을 조회합니다.")
    else:
        st.success(f"📍 {st.session_state.addr}")
        st.caption(f"PNU: `{st.session_state.pnu}`")
        items = st.session_state.items
        if not items:
            st.warning("등록된 건물 없음")
        else:
            for item in items:
                with st.expander(f"🏢 {item.get('bldNm') or '건물명 없음'}", expanded=True):
                    for label, key in [
                        ("주용도",     "mainPurpsCdNm"),
                        ("지상층수",   "grndFlrCnt"),
                        ("지하층수",   "ugrndFlrCnt"),
                        ("연면적(㎡)", "totArea"),
                        ("사용승인일", "useAprDay"),
                        ("주구조",     "mainStructCdNm"),
                        ("건폐율(%)",  "bcRat"),
                        ("용적률(%)",  "vlRat"),
                    ]:
                        val = item.get(key) or "-"
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"font-size:13px;padding:4px 0;border-bottom:1px solid #f0f2f6'>"
                            f"<span style='color:#888'>{label}</span>"
                            f"<span style='font-weight:600'>{val}</span></div>",
                            unsafe_allow_html=True)

# ── 좌측 지도 컴포넌트 ───────────────────────────────────
with col_map:
    # Python → JS: 초기 데이터 전달 (render 이벤트)
    coord = _kakao_map(
        map_key    = MAP_JS_KEY,
        vworld_key = VWORLD_KEY,
        lat        = st.session_state.map_lat,
        lng        = st.session_state.map_lng,
        pnu        = st.session_state.pnu or "",
        key        = "kakao_map",
        default    = None,
        height     = 700,
    )

    # JS → Python: 클릭 좌표 수신
    if coord and isinstance(coord, dict):
        lat = coord.get("lat")
        lng = coord.get("lng")
        if lat and lng:
            coord_key = f"{lat},{lng}"
            if coord_key != st.session_state.last_coord:
                with st.spinner("🔍 건축물대장 조회 중..."):
                    addr, pnu, items, err = get_building_data(float(lat), float(lng))
                st.session_state.update({
                    "last_coord": coord_key,
                    "map_lat":    float(lat),
                    "map_lng":    float(lng),
                    "addr":       addr,
                    "pnu":        pnu,
                    "items":      items,
                    "err":        err,
                })
                st.rerun()
