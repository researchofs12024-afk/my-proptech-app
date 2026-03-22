"""
부동산 통합 플랫폼 - 카카오맵
===============================
[확정 구조]
- declare_component, tempfile 완전 제거 → 번쩍거림 해결
- 지도 + 우측 패널을 단일 components.html() 안에 구성
  → iframe 통신 문제 원천 제거
- 카카오 REST API (주소변환): JS에서 직접 호출 (CORS 허용)
- 건축물대장 API: Python만 호출 가능 (CORS 차단)
  → JS가 PNU를 window.top.location.replace()로 Python에 전달
  → Streamlit query_params 감지 → rerun → 우측 패널 갱신
- yAnchor: 1.0 → 팝업 버튼 위치 정상화
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3

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
    "map_lat": 37.5668, "map_lng": 126.9786,
    "addr": None, "pnu": None, "items": None, "err": None,
    "last_pnu": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def normalize_items(raw):
    if raw is None:           return []
    if isinstance(raw, dict): return [raw]
    return raw


def get_building_data(pnu: str, addr: str):
    """PNU로 건축물대장만 조회 (주소변환은 JS에서 이미 처리)"""
    # PNU에서 sigunguCd, bjdongCd, bun, ji 역산
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


# ── query_params 수신: JS가 PNU+주소를 URL 파라미터로 전달 ─
qp = st.query_params
if "pnu" in qp and "addr" in qp:
    pnu_received  = qp["pnu"]
    addr_received = qp["addr"]
    # lat/lng도 함께 받아 지도 중심 유지
    try:
        lat_received = float(qp.get("lat", st.session_state.map_lat))
        lng_received = float(qp.get("lng", st.session_state.map_lng))
    except Exception:
        lat_received = st.session_state.map_lat
        lng_received = st.session_state.map_lng

    if pnu_received != st.session_state.last_pnu:
        with st.spinner("🔍 건축물대장 조회 중..."):
            items, err = get_building_data(pnu_received, addr_received)
        st.session_state.update({
            "last_pnu": pnu_received,
            "map_lat":  lat_received,
            "map_lng":  lng_received,
            "addr":     addr_received,
            "pnu":      pnu_received,
            "items":    items,
            "err":      err,
        })
        st.query_params.clear()
        st.rerun()
    else:
        st.query_params.clear()


# ── 페이지 타이틀 ─────────────────────────────────────────
st.title("🗺️ 부동산 통합 플랫폼")

# ── 단일 HTML 컴포넌트 (지도 + 우측 패널) ────────────────
pnu_js    = st.session_state.pnu  or ""
addr_js   = st.session_state.addr or ""
lat_c     = st.session_state.map_lat
lng_c     = st.session_state.map_lng

# session_state의 건물 정보를 JS에 JSON으로 주입
import json
items_js  = st.session_state.items or []
err_js    = st.session_state.err   or ""
items_json = json.dumps(items_js, ensure_ascii=False)

map_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: 100%; height: 100%;
  font-family: 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  overflow: hidden;
}}
#root {{ display: flex; width: 100%; height: 700px; }}
#map  {{ flex: 1; height: 100%; min-width: 0; }}

/* 우측 패널 */
#panel {{
  width: 280px; height: 100%; overflow-y: auto;
  background: #fff; border-left: 2px solid #e0e7ff;
  display: flex; flex-direction: column; flex-shrink: 0;
}}
#ph {{
  background: linear-gradient(135deg,#3396ff,#1a6fd4);
  color: #fff; padding: 14px 16px; flex-shrink: 0;
}}
#ph h3 {{ font-size: 14px; margin-bottom: 4px; }}
#ph p  {{ font-size: 11px; opacity: .85; margin: 0; word-break: keep-all; }}
#pb {{ padding: 12px; overflow-y: auto; flex: 1; }}

.card {{
  background: #f8faff; border: 1px solid #dce8ff;
  border-radius: 8px; padding: 12px; margin-bottom: 10px;
}}
.ctitle {{ font-size: 13px; font-weight: 700; color: #1a3a6b; margin-bottom: 8px; }}
.row {{
  display: flex; justify-content: space-between;
  font-size: 12px; padding: 3px 0; border-bottom: 1px solid #edf2ff;
}}
.row:last-child {{ border-bottom: none; }}
.lbl {{ color: #888; }}
.val {{ font-weight: 600; color: #1a1a2e; text-align: right; max-width: 60%; word-break: break-all; }}

/* 팝업 버튼 */
.kbtn {{
  background: #fff; border: 2px solid #3396ff; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; font-weight: 700; color: #1a3a6b;
  box-shadow: 0 3px 10px rgba(0,0,0,.15); cursor: pointer;
  white-space: nowrap; position: relative; transition: background .1s;
}}
.kbtn:hover {{ background: #e8f0ff; }}
.kbtn::after {{
  content: ''; position: absolute;
  bottom: -9px; left: 50%; transform: translateX(-50%);
  border: 5px solid transparent; border-top-color: #3396ff;
}}
#spinner {{
  display: none; text-align: center;
  padding: 30px 0; color: #3396ff; font-size: 13px;
}}
</style>
</head>
<body>
<div id="root">
  <div id="map"></div>
  <div id="panel">
    <div id="ph">
      <h3 id="ph-title">📋 건축물 정보</h3>
      <p  id="ph-addr">지도를 클릭하세요</p>
    </div>
    <div id="pb">
      <div id="spinner">⏳ 조회 중...</div>
      <div id="content"></div>
    </div>
  </div>
</div>

<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
var ADDR_KEY   = "{ADDR_REST_KEY}";
var VWORLD_KEY = "{VWORLD_KEY}";
var map, ov;

// ── Python이 주입한 초기 데이터 표시 ──────────────────
var initItems = {items_json};
var initAddr  = "{addr_js}";
var initErr   = "{err_js}";

if (initErr) {{
  document.getElementById('ph-addr').textContent = '⚠️ ' + initErr;
}} else if (initAddr) {{
  document.getElementById('ph-addr').textContent = '📍 ' + initAddr;
  renderItems(initItems);
}}

// ── 카카오맵 초기화 ─────────────────────────────────
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
    var html = '<div class="kbtn" onclick="onQuery(' + lat + ',' + lng + ')">📋 건축물대장 조회</div>';
    ov = new kakao.maps.CustomOverlay({{
      map: map, position: e.latLng,
      content: html,
      yAnchor: 1.0   // 버튼 하단이 클릭 위치 = 정확한 위치
    }});
  }});
}});

// ── 클릭 → 카카오 REST 호출 → Python으로 PNU 전달 ───
async function onQuery(lat, lng) {{
  if (ov) ov.setMap(null);
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('content').innerHTML = '';
  document.getElementById('ph-addr').textContent = '조회 중...';

  try {{
    // 카카오 REST는 CORS 허용 → 브라우저에서 직접 호출 가능
    var [regRes, adrRes] = await Promise.all([
      fetch('https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x=' + lng + '&y=' + lat,
        {{ headers: {{ 'Authorization': 'KakaoAK ' + ADDR_KEY }} }}).then(r => r.json()),
      fetch('https://dapi.kakao.com/v2/local/geo/coord2address.json?x=' + lng + '&y=' + lat,
        {{ headers: {{ 'Authorization': 'KakaoAK ' + ADDR_KEY }} }}).then(r => r.json())
    ]);

    var bDoc = (regRes.documents || []).find(d => d.region_type === 'B');
    if (!bDoc) throw new Error('법정동 코드 없음 (도로·하천 구역)');
    if (!adrRes.documents || !adrRes.documents.length) throw new Error('주소 없음');

    var a   = adrRes.documents[0].address;
    var bun = a.main_address_no;
    var ji  = a.sub_address_no || '0';
    var pnu = bDoc.code + '1' + bun.padStart(4,'0') + ji.padStart(4,'0');
    var addr = a.address_name;

    document.getElementById('ph-addr').textContent = '⏳ 건축물대장 조회 중...';

    // 건축물대장은 CORS 차단 → Python 경유 필요
    // window.top.location.replace() 로 Streamlit query_params 변경
    // replace()는 브라우저 history에 안 쌓여서 뒤로가기 문제 없음
    var url = window.top.location.pathname
      + '?pnu=' + encodeURIComponent(pnu)
      + '&addr=' + encodeURIComponent(addr)
      + '&lat=' + lat + '&lng=' + lng;
    window.top.location.replace(url);

  }} catch(e) {{
    document.getElementById('ph-addr').textContent = '⚠️ ' + e.message;
    document.getElementById('content').innerHTML =
      '<p style="color:#e53e3e;padding:16px;font-size:13px;">' + e.message + '</p>';
    document.getElementById('spinner').style.display = 'none';
  }}
}}

// ── 건물 카드 렌더 ───────────────────────────────────
function renderItems(items) {{
  var body = document.getElementById('content');
  if (!items || items.length === 0) {{
    body.innerHTML = '<p style="color:#999;text-align:center;padding:30px 0;font-size:13px;">등록된 건물 정보 없음</p>';
    return;
  }}
  body.innerHTML = items.map(function(item) {{
    return '<div class="card">'
      + '<div class="ctitle">🏢 ' + (item.bldNm || '건물명 없음') + '</div>'
      + r('주용도',     item.mainPurpsCdNm)
      + r('지상층수',   (item.grndFlrCnt  || '-') + 'F')
      + r('지하층수',   'B' + (item.ugrndFlrCnt || '0'))
      + r('연면적',     (item.totArea     || '-') + ' ㎡')
      + r('사용승인일', item.useAprDay)
      + r('주구조',     item.mainStructCdNm)
      + r('건폐율',     (item.bcRat  || '-') + '%')
      + r('용적률',     (item.vlRat  || '-') + '%')
      + '</div>';
  }}).join('');
}}

function r(label, val) {{
  return '<div class="row"><span class="lbl">' + label + '</span>'
       + '<span class="val">' + (val || '-') + '</span></div>';
}}

// ── Vworld 지적경계 ──────────────────────────────────
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
