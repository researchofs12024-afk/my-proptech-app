"""
부동산 통합 플랫폼 - 카카오맵
================================
[최종 구조]
- 모든 API 호출을 JS에서 직접 처리 (페이지 리로드 없음)
- 지도 + 우측 패널 전부 components.html() 하나 안에 구성
- 버튼 위로 올라가는 현상 완전 해결

[카카오 JS 앱 도메인 등록 필요]
  카카오 개발자 콘솔 → MAP_JS_KEY 앱
  → 앱 설정 → 플랫폼 → Web → 사이트 도메인
  → https://your-app-name.streamlit.app 추가

[API별 호출 방식]
- 카카오맵 SDK      : JS (MAP_JS_KEY, 도메인 등록 필요)
- 카카오 REST 주소변환: JS fetch() (ADDR_REST_KEY, 같은 앱에 Web 등록 필요 OR 별도 앱)
- 공공데이터포털    : JS fetch() (CORS: Access-Control-Allow-Origin: * 지원)
- Vworld 지적경계   : JS JSONP
"""

import streamlit as st
import streamlit.components.v1 as components

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
    .block-container { padding: 0 !important; }
    header[data-testid="stHeader"] { display: none; }
    #MainMenu, footer { display: none; }
    iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)

# Python은 최초 렌더 시 지도 중심 좌표만 전달
# 이후 모든 상태는 JS 내부에서 관리

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

/* 전체 레이아웃 */
#root {{
  display: flex;
  width: 100%;
  height: 100vh;
}}
#map-wrap {{ flex: 1; position: relative; min-width: 0; }}
#map      {{ width: 100%; height: 100%; }}

/* 우측 패널 */
#panel {{
  width: 300px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 2px solid #dce8ff;
  flex-shrink: 0;
  overflow: hidden;
}}
#panel-head {{
  background: linear-gradient(135deg, #3396ff, #1a6fd4);
  color: #fff;
  padding: 16px;
  flex-shrink: 0;
}}
#panel-head h3 {{ font-size: 14px; margin-bottom: 4px; }}
#panel-head p  {{
  font-size: 11px; opacity: .85; margin: 0;
  word-break: break-all; line-height: 1.4;
}}
#panel-body {{
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}}

/* 건물 카드 */
.card {{
  background: #f8faff;
  border: 1px solid #dce8ff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}}
.card-title {{
  font-size: 13px; font-weight: 700;
  color: #1a3a6b; margin-bottom: 8px;
}}
.row {{
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px solid #edf2ff;
}}
.row:last-child {{ border-bottom: none; }}
.lbl {{ color: #888; white-space: nowrap; margin-right: 8px; }}
.val {{ font-weight: 600; color: #1a1a2e; text-align: right; }}

/* 지도 위 팝업 버튼 */
.kbtn {{
  display: inline-block;
  background: #fff;
  border: 2px solid #3396ff;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px; font-weight: 700; color: #1a3a6b;
  font-family: 'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  box-shadow: 0 3px 12px rgba(0,0,0,.15);
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  transition: background .1s;
  border-bottom: 2px solid #2277cc;
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

/* 메시지 */
.msg-empty {{
  text-align: center; color: #aaa;
  font-size: 13px; padding: 40px 0; line-height: 1.8;
}}
.msg-err {{
  color: #e53e3e; font-size: 13px;
  padding: 16px; line-height: 1.6;
}}
</style>
</head>
<body>
<div id="root">
  <div id="map-wrap">
    <div id="map"></div>
  </div>
  <div id="panel">
    <div id="panel-head">
      <h3 id="ph-title">📋 건축물 정보</h3>
      <p  id="ph-addr">지도를 클릭하세요</p>
    </div>
    <div id="panel-body">
      <div class="msg-empty">지도에서 건물 위치를 클릭하면<br>건축물대장이 표시됩니다.</div>
    </div>
  </div>
</div>

<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
// ── 상수 ────────────────────────────────────────────────
var ADDR_KEY    = "{ADDR_REST_KEY}";
var LEDGER_KEY  = "{LEDGER_KEY}";
var VWORLD_KEY  = "{VWORLD_KEY}";

var map, ov;

// ── 카카오맵 초기화 ──────────────────────────────────────
kakao.maps.load(function() {{
  map = new kakao.maps.Map(document.getElementById('map'), {{
    center: new kakao.maps.LatLng(37.5668, 126.9786),
    level: 3
  }});

  kakao.maps.event.addListener(map, 'click', function(e) {{
    var lat = e.latLng.getLat();
    var lng = e.latLng.getLng();

    if (ov) ov.setMap(null);

    // 클릭 즉시 버튼 표시 (onclick으로 API 호출)
    var btn = document.createElement('div');
    btn.className = 'kbtn';
    btn.textContent = '📋 건축물대장 조회';
    btn.onclick = function() {{
      btn.textContent = '⏳ 조회 중...';
      btn.style.color = '#888';
      queryAll(lat, lng);
    }};

    ov = new kakao.maps.CustomOverlay({{
      map: map,
      position: e.latLng,
      content: btn,
      yAnchor: 1.0
    }});
  }});
}});

// ── 모든 API 조회 ───────────────────────────────────────
async function queryAll(lat, lng) {{
  var ph  = document.getElementById('ph-addr');
  var pb  = document.getElementById('panel-body');

  try {{
    // 1. 카카오 REST: 법정동코드 + 주소 (병렬)
    var [regRes, adrRes] = await Promise.all([
      fetch('https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x=' + lng + '&y=' + lat,
        {{headers: {{'Authorization': 'KakaoAK ' + ADDR_KEY}}}}).then(r => r.json()),
      fetch('https://dapi.kakao.com/v2/local/geo/coord2address.json?x=' + lng + '&y=' + lat,
        {{headers: {{'Authorization': 'KakaoAK ' + ADDR_KEY}}}}).then(r => r.json())
    ]);

    var bDoc = (regRes.documents||[]).find(d => d.region_type === 'B');
    if (!bDoc) throw new Error('법정동 코드 없음 (도로·하천 구역)');
    if (!adrRes.documents||!adrRes.documents.length) throw new Error('주소 없음');

    var a    = adrRes.documents[0].address;
    var bun  = a.main_address_no;
    var ji   = (a.sub_address_no || '0');
    var pnu  = bDoc.code + '1' + bun.padStart(4,'0') + ji.padStart(4,'0');
    var addr = a.address_name;

    ph.textContent = '📍 ' + addr;
    pb.innerHTML   = '<div class="msg-empty">건축물대장 조회 중...</div>';

    // 지적경계 표시
    drawParcel(pnu);

    // 2. 건축물대장 API (공공데이터포털, CORS: *)
    var bCode = bDoc.code;
    var url = 'https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo'
      + '?serviceKey=' + encodeURIComponent(LEDGER_KEY)
      + '&sigunguCd=' + bCode.slice(0,5)
      + '&bjdongCd='  + bCode.slice(5,10)
      + '&platGbCd=0'
      + '&bun='  + bun.padStart(4,'0')
      + '&ji='   + ji.padStart(4,'0')
      + '&pageNo=1&numOfRows=30&_type=json';

    var bldRes = await fetch(url).then(r => r.json());
    var raw    = (bldRes.response||{{}}).body||{{}};
    var itemsRaw = (raw.items||{{}}).item;
    var items  = !itemsRaw ? [] : (Array.isArray(itemsRaw) ? itemsRaw : [itemsRaw]);

    renderPanel(items);

    // 팝업 버튼 제거 (조회 완료)
    if (ov) ov.setMap(null);

  }} catch(e) {{
    document.getElementById('ph-addr').textContent = '⚠️ 오류';
    document.getElementById('panel-body').innerHTML =
      '<div class="msg-err">⚠️ ' + e.message + '</div>';
    if (ov) ov.setMap(null);
  }}
}}

// ── 패널 렌더링 ─────────────────────────────────────────
function renderPanel(items) {{
  var pb = document.getElementById('panel-body');
  if (!items.length) {{
    pb.innerHTML = '<div class="msg-empty">등록된 건물 정보 없음</div>';
    return;
  }}
  pb.innerHTML = items.map(function(item) {{
    return '<div class="card">'
      + '<div class="card-title">🏢 ' + (item.bldNm || '건물명 없음') + '</div>'
      + row('주용도',    item.mainPurpsCdNm)
      + row('지상층수',  (item.grndFlrCnt||'-') + 'F')
      + row('지하층수',  'B' + (item.ugrndFlrCnt||'0'))
      + row('연면적',    (item.totArea||'-') + ' ㎡')
      + row('사용승인일',item.useAprDay)
      + row('주구조',    item.mainStructCdNm)
      + row('건폐율',    (item.bcRat||'-') + '%')
      + row('용적률',    (item.vlRat||'-') + '%')
      + '</div>';
  }}).join('');
}}

function row(lbl, val) {{
  return '<div class="row">'
    + '<span class="lbl">' + lbl + '</span>'
    + '<span class="val">' + (val||'-') + '</span>'
    + '</div>';
}}

// ── Vworld 지적경계 ──────────────────────────────────────
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
  if (!f||!f.length) return;
  var g = f[0].geometry.coordinates;
  while (Array.isArray(g[0][0])) g = g[0];
  var path = g.map(function(c) {{ return new kakao.maps.LatLng(c[1],c[0]); }});
  new kakao.maps.Polygon({{
    map: map, path: path,
    strokeWeight: 3, strokeColor: '#3396ff', strokeOpacity: 1,
    fillColor: '#3396ff', fillOpacity: 0.15
  }});
}};
</script>
</body>
</html>"""

components.html(map_html, height=800, scrolling=False)
