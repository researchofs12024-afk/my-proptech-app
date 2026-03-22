"""
부동산 통합 플랫폼 - 카카오맵 기반
======================================
[검증된 수정 사항]
1. ❌→✅ iframe 통신: window.parent.location 차단 문제
         → streamlit-js-eval 사용 (Streamlit 공식 권장 방식)
2. ❌→✅ items=None 일 때 for문 TypeError
         → normalize_items()에서 None → [] 처리
3. ❌→✅ pnu 변수 스코프 오류
         → session_state로 안전하게 관리
4. ❌→✅ 지도 클릭마다 중심좌표 초기화
         → map_center를 session_state에 저장
5. ❌→✅ 중복 rerun 위험
         → last_coord_key로 이미 처리한 좌표 스킵

[설치 필요]
pip install streamlit streamlit-js-eval requests urllib3
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────────────────
# API 키
# ─────────────────────────────────────────────────────────
MAP_JS_KEY    = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076"
LEDGER_KEY    = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY    = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

# ─────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="부동산 통합 플랫폼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container { padding: 1rem 1rem 0 1rem !important; }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu, footer { display: none; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────────────────
defaults = {
    "map_center_lat": 37.5668,
    "map_center_lng": 126.9786,
    "addr":           None,
    "pnu":            None,
    "items":          None,
    "error_msg":      None,
    "last_coord_key": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────
# 건축물대장 조회 함수
# ─────────────────────────────────────────────────────────
def normalize_items(raw):
    """API item 필드: dict(단일건물) / list(복수) / None 모두 처리"""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    return raw


def get_building_data(lat: float, lng: float):
    """
    Returns: (addr_name, pnu, items, error_msg)
    성공: error_msg=None
    실패: addr_name=None, pnu=None, items=None, error_msg=str
    """
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 1. 법정동 코드 조회
        reg_res = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}",
            headers=headers, timeout=5
        ).json()
        b_code = next(
            (doc["code"] for doc in reg_res.get("documents", [])
             if doc.get("region_type") == "B"),
            None
        )

        # 2. 지번 주소 조회
        addr_res = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}",
            headers=headers, timeout=5
        ).json()

        if not b_code:
            return None, None, None, "법정동 코드를 찾을 수 없습니다 (도로·하천 등 비건물 구역)"
        if not addr_res.get("documents"):
            return None, None, None, "주소 정보를 찾을 수 없습니다"

        addr_obj  = addr_res["documents"][0]["address"]
        addr_name = addr_obj["address_name"]
        bun       = addr_obj["main_address_no"]
        ji        = addr_obj["sub_address_no"] or "0"

        # 3. PNU 생성 (19자리)
        pnu = b_code + "1" + bun.zfill(4) + ji.zfill(4)

        # 4. 건축물대장 표제부 조회
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {
            "serviceKey": LEDGER_KEY,
            "sigunguCd":  b_code[:5],
            "bjdongCd":   b_code[5:10],
            "platGbCd":   "0",
            "bun":        bun.zfill(4),
            "ji":         ji.zfill(4),
            "pageNo":     "1",
            "numOfRows":  "30",
            "_type":      "json",
        }
        res  = requests.get(url, params=params, verify=False, timeout=10).json()
        body = res.get("response", {}).get("body", {})
        raw  = body.get("items", {})
        items = normalize_items(raw.get("item") if isinstance(raw, dict) else None)

        return addr_name, pnu, items, None

    except requests.exceptions.Timeout:
        return None, None, None, "API 응답 시간 초과"
    except requests.exceptions.ConnectionError:
        return None, None, None, "네트워크 연결 오류"
    except Exception as e:
        return None, None, None, f"오류: {str(e)}"


# ─────────────────────────────────────────────────────────
# streamlit-js-eval 임포트 확인
# ─────────────────────────────────────────────────────────
try:
    from streamlit_js_eval import streamlit_js_eval
    HAS_JS_EVAL = True
except ImportError:
    HAS_JS_EVAL = False

if not HAS_JS_EVAL:
    st.error(
        "**`streamlit-js-eval` 패키지가 설치되지 않았습니다.**\n\n"
        "지도 클릭 → Python 좌표 전달에 필요합니다.\n\n"
        "```bash\npip install streamlit-js-eval\n```"
    )

# ─────────────────────────────────────────────────────────
# 레이아웃
# ─────────────────────────────────────────────────────────
st.title("🗺️ 부동산 통합 플랫폼")
col_map, col_info = st.columns([3, 1])

# ── 우측: 정보 패널 ────────────────────────────────────
with col_info:
    st.subheader("📋 건축물 정보")

    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
    elif st.session_state.addr is None:
        st.info("지도를 클릭하면\n건축물대장을 조회합니다.")
    else:
        st.success(f"📍 {st.session_state.addr}")
        st.caption(f"PNU: `{st.session_state.pnu}`")

        items = st.session_state.items
        if not items:
            st.warning("등록된 건물 정보가 없습니다.")
        else:
            for item in items:
                bld_nm = item.get("bldNm") or "건물명 없음"
                with st.expander(f"🏢 {bld_nm}", expanded=True):
                    rows = [
                        ("주용도",      "mainPurpsCdNm"),
                        ("지상층수",    "grndFlrCnt"),
                        ("지하층수",    "ugrndFlrCnt"),
                        ("연면적(㎡)",  "totArea"),
                        ("사용승인일",  "useAprDay"),
                        ("주구조",      "mainStructCdNm"),
                        ("건폐율(%)",   "bcRat"),
                        ("용적률(%)",   "vlRat"),
                    ]
                    for label, key in rows:
                        val = item.get(key) or "-"
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"font-size:13px;padding:4px 0;"
                            f"border-bottom:1px solid #f0f2f6'>"
                            f"<span style='color:#888'>{label}</span>"
                            f"<span style='font-weight:600;color:#1a1a2e'>{val}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

# ── 좌측: 카카오맵 ─────────────────────────────────────
with col_map:
    current_pnu = st.session_state.pnu or ""
    lat_c       = st.session_state.map_center_lat
    lng_c       = st.session_state.map_center_lng

    map_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{ margin:0; padding:0; background:#e8e8e8; }}
#map {{ width:100%; height:680px; }}
.kmap-btn {{
    background:#fff;
    border:2px solid #3396ff;
    border-radius:8px;
    padding:9px 16px;
    font-size:13px;
    font-weight:700;
    color:#1a3a6b;
    font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
    box-shadow:0 4px 14px rgba(0,0,0,.16);
    cursor:pointer;
    white-space:nowrap;
    position:relative;
    transition:background .15s;
}}
.kmap-btn:hover {{ background:#e8f0ff; }}
.kmap-btn::after {{
    content:'';
    position:absolute;
    bottom:-10px; left:50%;
    transform:translateX(-50%);
    border:5px solid transparent;
    border-top-color:#3396ff;
}}
</style>
</head>
<body>
<div id="map"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
var map, clickOverlay;

kakao.maps.load(function() {{
    map = new kakao.maps.Map(document.getElementById('map'), {{
        center: new kakao.maps.LatLng({lat_c}, {lng_c}),
        level: 3
    }});

    // 기존 필지 하이라이트 복원 (Python이 pnu를 직접 주입)
    var pnu = "{current_pnu}";
    if (pnu) drawParcel(pnu);

    kakao.maps.event.addListener(map, 'click', function(e) {{
        var lat = e.latLng.getLat();
        var lng = e.latLng.getLng();

        if (clickOverlay) clickOverlay.setMap(null);

        var content =
            '<div class="kmap-btn" onclick="sendCoord(' + lat + ',' + lng + ')">' +
            '📋 건축물대장 조회' +
            '</div>';

        clickOverlay = new kakao.maps.CustomOverlay({{
            map:      map,
            position: e.latLng,
            content:  content,
            yAnchor:  2.0
        }});
    }});
}});

// ── JS → Python: window._streamlit_coord에 값을 세팅하면
//    streamlit_js_eval이 폴링해서 Python에서 읽어감 ──────
function sendCoord(lat, lng) {{
    window._streamlit_coord = lat + "," + lng;
}}

// ── Vworld 지적경계 폴리곤 ───────────────────────────
function drawParcel(pnu) {{
    var s = document.createElement('script');
    s.src =
        'https://api.vworld.kr/req/data' +
        '?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM' +
        '&key={VWORLD_KEY}' +
        '&attrFilter=pnu:=' + pnu +
        '&crs=EPSG:4326&callback=vCallback';
    document.body.appendChild(s);
}}

window.vCallback = function(data) {{
    if (!data.response || data.response.status !== 'OK') return;
    var features = data.response.result.featureCollection.features;
    if (!features || !features.length) return;
    var geom = features[0].geometry.coordinates;
    while (Array.isArray(geom[0][0])) geom = geom[0];
    var path = geom.map(function(c) {{ return new kakao.maps.LatLng(c[1], c[0]); }});
    new kakao.maps.Polygon({{
        map:            map,
        path:           path,
        strokeWeight:   3,
        strokeColor:    '#3396ff',
        strokeOpacity:  1.0,
        fillColor:      '#3396ff',
        fillOpacity:    0.15
    }});
}};
</script>
</body>
</html>"""

    components.html(map_html, height=690, scrolling=False)

# ─────────────────────────────────────────────────────────
# streamlit-js-eval 폴링: 지도 클릭 좌표 수신
# ─────────────────────────────────────────────────────────
if HAS_JS_EVAL:
    coord_str = streamlit_js_eval(
        js_expressions="window._streamlit_coord",
        key="map_click_coord"
    )

    if coord_str and isinstance(coord_str, str):
        if coord_str != st.session_state.last_coord_key:
            try:
                lat, lng = [float(x) for x in coord_str.split(",")]

                with st.spinner("🔍 건축물대장 조회 중..."):
                    addr, pnu, items, err = get_building_data(lat, lng)

                st.session_state.last_coord_key = coord_str
                st.session_state.map_center_lat = lat
                st.session_state.map_center_lng = lng

                if err:
                    st.session_state.error_msg = err
                    st.session_state.addr  = None
                    st.session_state.pnu   = None
                    st.session_state.items = None
                else:
                    st.session_state.error_msg = None
                    st.session_state.addr  = addr
                    st.session_state.pnu   = pnu
                    st.session_state.items = items

                st.rerun()

            except (ValueError, AttributeError):
                pass
