"""
부동산 통합 플랫폼 - 카카오맵
================================
[확정 구조]

JS 역할: 지도 렌더링 + 클릭 좌표 전달만
Python 역할: 모든 API 호출 (카카오 REST, 건축물대장)

JS → Python 좌표 전달:
  <a href="?lat=...&lng=..." target="_top"> 클릭
  → allow-top-navigation-by-user-activation (사용자 클릭 시 허용)
  → Streamlit query_params 감지 → rerun

카카오 REST API (주소변환): Python에서만 호출
  → ADDR_REST_KEY 브라우저 노출 없음
  → 도메인/플랫폼 등록 불필요
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAP_JS_KEY    = "ede7b455451821c17720156a3e8b5011"  # JS키 (카카오맵 표시용, 지도앱)
ADDR_REST_KEY = "668fc8777ccf99d71bfe4be308a90047"  # REST키 (주소변환용, Python서버에서만 호출)
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
    "map_lat":  37.5668,
    "map_lng":  126.9786,
    "addr":     None,
    "pnu":      None,
    "items":    None,
    "err":      None,
    "last_coord": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def normalize_items(raw):
    if raw is None:           return []
    if isinstance(raw, dict): return [raw]
    if isinstance(raw, list): return raw
    return []


def get_all_data(lat: float, lng: float):
    """
    Python 서버에서 모든 API 호출
    1. 카카오 REST: 좌표 → 주소 + 법정동코드 + PNU
    2. 공공데이터포털: PNU → 건축물대장
    """
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 1. 법정동 코드
        reg = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}",
            headers=headers, timeout=5).json()
        b_code = next(
            (d["code"] for d in reg.get("documents", []) if d.get("region_type") == "B"),
            None)

        # 2. 지번 주소
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
        addr_name = a["address_name"]

        # 3. 건축물대장
        res = requests.get(
            "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
            params={"serviceKey": LEDGER_KEY, "sigunguCd": b_code[:5],
                    "bjdongCd": b_code[5:10], "platGbCd": "0",
                    "bun": bun.zfill(4), "ji": ji.zfill(4),
                    "pageNo": "1", "numOfRows": "30", "_type": "json"},
            verify=False, timeout=10).json()

        raw   = res.get("response", {}).get("body", {}).get("items", {})
        items = normalize_items(raw.get("item") if isinstance(raw, dict) else None)
        return addr_name, pnu, items, None

    except requests.exceptions.Timeout:
        return None, None, None, "API 시간 초과"
    except Exception as e:
        return None, None, None, f"오류: {e}"


# ── query_params 수신 ─────────────────────────────────────
# JS의 <a target="_top" href="?lat=...&lng=..."> 클릭
# → Streamlit 페이지 URL에 파라미터 추가 → query_params 감지
qp = st.query_params
if "lat" in qp and "lng" in qp:
    try:
        lat_in = float(qp["lat"])
        lng_in = float(qp["lng"])
        coord_key = f"{lat_in},{lng_in}"

        if coord_key != st.session_state.last_coord:
            with st.spinner("🔍 건축물대장 조회 중..."):
                addr, pnu, items, err = get_all_data(lat_in, lng_in)
            st.session_state.update({
                "last_coord": coord_key,
                "map_lat":    lat_in,
                "map_lng":    lng_in,
                "addr":       addr,
                "pnu":        pnu,
                "items":      items,
                "err":        err,
            })
    except (ValueError, TypeError):
        pass
    finally:
        st.query_params.clear()
        st.rerun()


# ── 레이아웃 ─────────────────────────────────────────────
st.title("🗺️ 부동산 통합 플랫폼")
col_map, col_info = st.columns([3, 1])

# ── 우측 정보 패널 (Python 렌더링) ───────────────────────
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

# ── 좌측 지도 (JS는 좌표 전달만) ─────────────────────────
with col_map:
    lat_c  = st.session_state.map_lat
    lng_c  = st.session_state.map_lng
    pnu_js = st.session_state.pnu or ""

    map_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 100%; height: 100%; overflow: hidden; }}
#map {{ width: 100%; height: 700px; }}

.kbtn {{
  display: inline-block;
  background: #fff;
  border: 2px solid #3396ff;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  color: #1a3a6b;
  font-family: 'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  box-shadow: 0 3px 12px rgba(0,0,0,.15);
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  position: relative;
  transition: background .1s;
}}
.kbtn:hover {{ background: #e8f0ff; }}
.kbtn::after {{
  content: '';
  position: absolute;
  bottom: -9px; left: 50%;
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
var map, ov;
var VWORLD_KEY = "{VWORLD_KEY}";

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

    // JS는 좌표만 전달, 모든 API 처리는 Python이 담당
    // <a target="_top"> : 사용자 클릭 → allow-top-navigation-by-user-activation → 허용
    var link = document.createElement('a');
    link.href = '?lat=' + lat + '&lng=' + lng;
    link.target = '_top';
    link.className = 'kbtn';
    link.textContent = '📋 건축물대장 조회';

    ov = new kakao.maps.CustomOverlay({{
      map: map,
      position: e.latLng,
      content: link,
      yAnchor: 1.0
    }});
  }});
}});

// Vworld 지적경계
function drawParcel(pnu) {{
  var s = document.createElement('script');
  s.src = 'https://api.vworld.kr/req/data?service=data&request=GetFeature'
    + '&data=LP_PA_CBND_BU_GEOM&key=' + VWORLD_KEY
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
</html>"""

    components.html(map_html, height=710, scrolling=False)
