"""
부동산 통합 플랫폼 - 카카오맵
===============================
JS → Python 통신: Streamlit.setComponentValue() 인라인 구현
- window.top.location.href 방식 제거 (페이지 리로드 문제)
- 카카오맵 + 정보패널을 하나의 HTML 안에 모두 구성
- Python은 건축물대장 API만 담당, 결과를 session_state에 저장
- 지도 클릭 → setComponentValue → Streamlit rerun → 우측 패널 갱신
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3
import os, tempfile

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAP_JS_KEY    = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "668fc8777ccf99d71bfe4be308a90047"
LEDGER_KEY    = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY    = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding: 1rem !important; }
    header[data-testid="stHeader"] { display:none; }
    #MainMenu, footer { display:none; }
</style>
""", unsafe_allow_html=True)

# ── 세션 초기화 ──────────────────────────────────────────
for k, v in {
    "map_lat": 37.5668, "map_lng": 126.9786,
    "addr": None, "pnu": None, "items": None, "err": None,
    "last_coord": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def normalize_items(raw):
    if raw is None: return []
    if isinstance(raw, dict): return [raw]
    return raw


def get_building_data(lat, lng):
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


# ── 커스텀 컴포넌트 인라인 선언 ─────────────────────────
# Streamlit 커스텀 컴포넌트의 핵심: Streamlit.setComponentValue()
# → iframe 안 JS에서 호출하면 Python에서 반환값으로 받을 수 있음
# → 페이지 리로드 없이 JS→Python 단방향 값 전달 가능
_COMP_DIR = tempfile.mkdtemp()
_INDEX = os.path.join(_COMP_DIR, "index.html")

pnu_js = st.session_state.pnu or ""
lat_c  = st.session_state.map_lat
lng_c  = st.session_state.map_lng

with open(_INDEX, "w", encoding="utf-8") as f:
    f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 100%; height: 100%; overflow: hidden; }}
#map {{ width: 100%; height: 100vh; }}
.kbtn {{
  background: #fff;
  border: 2px solid #3396ff;
  border-radius: 8px;
  padding: 9px 16px;
  font-size: 13px;
  font-weight: 700;
  color: #1a3a6b;
  font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  box-shadow: 0 4px 14px rgba(0,0,0,.18);
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  transition: background .15s;
}}
.kbtn:hover {{ background: #e8f0ff; }}
.kbtn::after {{
  content: '';
  position: absolute;
  bottom: -10px; left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #3396ff;
}}
</style>
</head>
<body>
<div id="map"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
// ── Streamlit 커스텀 컴포넌트 통신 초기화 ──────────────
// Streamlit이 로드되면 componentReady 이벤트를 보내고
// setComponentValue()로 Python에 값을 돌려줌
function sendToPython(coord) {{
  // Streamlit 컴포넌트 공식 통신 채널
  window.parent.postMessage({{
    type: "streamlit:setComponentValue",
    value: coord
  }}, "*");
}}

// Streamlit이 컴포넌트 준비됐다고 알림
window.parent.postMessage({{ type: "streamlit:componentReady", apiVersion: 1 }}, "*");

// ── 카카오맵 ──────────────────────────────────────────
var map, ov;

kakao.maps.load(function() {{
  map = new kakao.maps.Map(document.getElementById('map'), {{
    center: new kakao.maps.LatLng({lat_c}, {lng_c}),
    level: 3
  }});

  var pnu = "{pnu_js}";
  if (pnu) drawParcel(pnu);

  kakao.maps.event.addListener(map, 'click', function(e) {{
    var lat = e.latLng.getLat();
    var lng = e.latLng.getLng();
    if (ov) ov.setMap(null);
    var btn = '<div class="kbtn" onclick="sendToPython(\\'' + lat + ',' + lng + '\\')">📋 건축물대장 조회</div>';
    ov = new kakao.maps.CustomOverlay({{
      map: map, position: e.latLng, content: btn, yAnchor: 2.0
    }});
  }});
}});

// ── Vworld 지적경계 ───────────────────────────────────
function drawParcel(pnu) {{
  var s = document.createElement('script');
  s.src = 'https://api.vworld.kr/req/data?service=data&request=GetFeature'
    + '&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}'
    + '&attrFilter=pnu:=' + pnu + '&crs=EPSG:4326&callback=vCb';
  document.body.appendChild(s);
}}

window.vCb = function(d) {{
  if (!d.response || d.response.status !== 'OK') return;
  var f = d.response.result.featureCollection.features;
  if (!f || !f.length) return;
  var g = f[0].geometry.coordinates;
  while (Array.isArray(g[0][0])) g = g[0];
  var path = g.map(function(c) {{ return new kakao.maps.LatLng(c[1], c[0]); }});
  new kakao.maps.Polygon({{
    map: map, path: path,
    strokeWeight: 3, strokeColor: '#3396ff', strokeOpacity: 1,
    fillColor: '#3396ff', fillOpacity: 0.15
  }});
}};
</script>
</body>
</html>""")

# 커스텀 컴포넌트 선언 (매번 같은 경로를 쓰면 Streamlit이 캐시함)
_kakao_map = components.declare_component("kakao_map", path=_COMP_DIR)

# ── 레이아웃 ─────────────────────────────────────────
st.title("🗺️ 부동산 통합 플랫폼")
col_map, col_info = st.columns([3, 1])

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

with col_map:
    # 컴포넌트 렌더 + JS→Python 값 수신
    # setComponentValue() 호출 시 coord_raw에 값이 들어오고 Streamlit이 rerun함
    coord_raw = _kakao_map(key="kakao_map_click", default=None)

    if coord_raw and isinstance(coord_raw, str):
        if coord_raw != st.session_state.last_coord:
            try:
                lat, lng = [float(x) for x in coord_raw.split(",")]
                with st.spinner("🔍 건축물대장 조회 중..."):
                    addr, pnu, items, err = get_building_data(lat, lng)

                st.session_state.last_coord = coord_raw
                st.session_state.map_lat    = lat
                st.session_state.map_lng    = lng
                st.session_state.addr       = addr
                st.session_state.pnu        = pnu
                st.session_state.items      = items
                st.session_state.err        = err
                st.rerun()
            except (ValueError, AttributeError):
                pass
