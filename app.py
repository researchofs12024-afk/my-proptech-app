"""
부동산 통합 플랫폼 - 카카오맵
================================
[확정 구조 - 파일 1개]

JS→Python 통신 방법:
  - JS가 카카오 REST(CORS허용)로 PNU를 직접 계산
  - <a href="?pnu=...&addr=...&lat=...&lng=..." target="_top"> 생성 후 JS로 클릭
  - Streamlit sandbox: allow-top-navigation-by-user-activation
    → 사용자 클릭 이벤트에서만 target="_top" 허용 → 정상 작동
  - Python이 query_params 감지 → 건축물대장 API 호출 → 결과 표시

declare_component, tempfile 완전 제거
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3
import json

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
    "map_lat":    37.5668,
    "map_lng":    126.9786,
    "addr":       None,
    "pnu":        None,
    "items":      None,
    "err":        None,
    "last_pnu":   None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def normalize_items(raw):
    if raw is None:           return []
    if isinstance(raw, dict): return [raw]
    if isinstance(raw, list): return raw
    return []


def get_building_data(pnu: str):
    """PNU로 건축물대장 조회 (Python만 가능 - CORS 차단)"""
    sigungu = pnu[0:5]
    bjdong  = pnu[5:10]
    bun     = pnu[11:15]
    ji      = pnu[15:19]
    try:
        res = requests.get(
            "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
            params={"serviceKey": LEDGER_KEY,
                    "sigunguCd": sigungu, "bjdongCd": bjdong,
                    "platGbCd": "0", "bun": bun, "ji": ji,
                    "pageNo": "1", "numOfRows": "30", "_type": "json"},
            verify=False, timeout=10).json()
        raw   = res.get("response", {}).get("body", {}).get("items", {})
        items = normalize_items(raw.get("item") if isinstance(raw, dict) else None)
        return items, None
    except requests.exceptions.Timeout:
        return None, "건축물대장 API 시간 초과"
    except Exception as e:
        return None, f"건축물대장 오류: {e}"


# ── query_params 수신 ────────────────────────────────────
# JS의 <a target="_top"> 클릭 → Streamlit 페이지 URL 변경
# → st.query_params에서 파라미터 감지 → rerun
qp = st.query_params
if "pnu" in qp:
    pnu_in   = qp.get("pnu", "")
    addr_in  = qp.get("addr", "")
    try:
        lat_in = float(qp.get("lat", st.session_state.map_lat))
        lng_in = float(qp.get("lng", st.session_state.map_lng))
    except (ValueError, TypeError):
        lat_in = st.session_state.map_lat
        lng_in = st.session_state.map_lng

    if pnu_in and pnu_in != st.session_state.last_pnu:
        with st.spinner("🔍 건축물대장 조회 중..."):
            items, err = get_building_data(pnu_in)
        st.session_state.update({
            "last_pnu": pnu_in,
            "map_lat":  lat_in,
            "map_lng":  lng_in,
            "addr":     addr_in,
            "pnu":      pnu_in,
            "items":    items,
            "err":      err,
        })
    st.query_params.clear()
    st.rerun()


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

# ── 좌측 지도 ─────────────────────────────────────────────
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

/* 팝업 버튼 스타일 */
.kbtn {{
  display: inline-block;
  background: #fff;
  border: 2px solid #3396ff;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  color: #1a3a6b;
  font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  box-shadow: 0 3px 12px rgba(0,0,0,.15);
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  position: relative;
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
var ADDR_KEY   = "{ADDR_REST_KEY}";
var VWORLD_KEY = "{VWORLD_KEY}";
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

    // 클릭 위치에 로딩 표시 먼저
    var loadDiv = document.createElement('div');
    loadDiv.className = 'kbtn';
    loadDiv.style.color = '#888';
    loadDiv.textContent = '⏳ 주소 조회 중...';

    ov = new kakao.maps.CustomOverlay({{
      map: map,
      position: e.latLng,
      content: loadDiv,
      yAnchor: 1.0
    }});

    // 카카오 REST로 PNU 계산 (CORS 허용)
    getPNU(lat, lng, function(pnu, addr, err) {{
      if (ov) ov.setMap(null);
      if (err) {{
        var errDiv = document.createElement('div');
        errDiv.className = 'kbtn';
        errDiv.style.color = '#e53e3e';
        errDiv.textContent = '⚠️ ' + err;
        ov = new kakao.maps.CustomOverlay({{
          map: map, position: e.latLng,
          content: errDiv, yAnchor: 1.0
        }});
        return;
      }}

      // ★ 핵심: <a target="_top"> 클릭으로 Streamlit URL 변경
      // allow-top-navigation-by-user-activation → 사용자 클릭 시 허용
      var url = '?pnu=' + encodeURIComponent(pnu)
              + '&addr=' + encodeURIComponent(addr)
              + '&lat=' + lat + '&lng=' + lng;

      var link = document.createElement('a');
      link.href = url;
      link.target = '_top';          // 부모 페이지 URL 변경
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
}});

// 카카오 REST API로 좌표 → PNU 계산
function getPNU(lat, lng, cb) {{
  Promise.all([
    fetch('https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x=' + lng + '&y=' + lat,
      {{ headers: {{ 'Authorization': 'KakaoAK ' + ADDR_KEY }} }}).then(r => r.json()),
    fetch('https://dapi.kakao.com/v2/local/geo/coord2address.json?x=' + lng + '&y=' + lat,
      {{ headers: {{ 'Authorization': 'KakaoAK ' + ADDR_KEY }} }}).then(r => r.json())
  ]).then(function(results) {{
    var regRes = results[0];
    var adrRes = results[1];

    var bDoc = (regRes.documents || []).find(function(d) {{ return d.region_type === 'B'; }});
    if (!bDoc) {{ cb(null, null, '법정동 코드 없음'); return; }}
    if (!adrRes.documents || !adrRes.documents.length) {{ cb(null, null, '주소 없음'); return; }}

    var a   = adrRes.documents[0].address;
    var bun = a.main_address_no;
    var ji  = a.sub_address_no || '0';
    var pnu = bDoc.code + '1' + bun.padStart(4,'0') + ji.padStart(4,'0');
    cb(pnu, a.address_name, null);

  }}).catch(function(e) {{
    cb(null, null, '주소 조회 실패: ' + e.message);
  }});
}}

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
