"""
부동산 통합 플랫폼 - 카카오맵
================================
[핵심 해결책]
카카오맵 SDK 내장 Geocoder 사용
  kakao.maps.services.Geocoder()
  → MAP_JS_KEY 하나로 지도 + 주소변환 모두 처리
  → ADDR_REST_KEY 브라우저 호출 불필요 (403 해결)
  → 페이지 리로드 없음 (버튼 위로 올라가는 현상 해결)

[전체 흐름]
  지도클릭 → Geocoder로 PNU 계산 → 건축물대장 API fetch
  → 우측 패널에 바로 표시 (모두 JS 내부에서 완결)

[필요한 카카오 앱 설정]
  MAP_JS_KEY 앱만 Web 플랫폼에 streamlit.app 도메인 등록
  (이미 등록되어 있음)
"""

import streamlit as st
import streamlit.components.v1 as components

MAP_JS_KEY  = "ede7b455451821c17720156a3e8b5011"
LEDGER_KEY  = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY  = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

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
#root {{ display: flex; width: 100%; height: 100vh; }}
#map-wrap {{ flex: 1; min-width: 0; }}
#map {{ width: 100%; height: 100%; }}

/* 우측 패널 */
#panel {{
  width: 300px; height: 100%;
  display: flex; flex-direction: column;
  background: #fff;
  border-left: 2px solid #dce8ff;
  flex-shrink: 0;
}}
#panel-head {{
  background: linear-gradient(135deg, #3396ff, #1a6fd4);
  color: #fff; padding: 16px; flex-shrink: 0;
}}
#panel-head h3 {{ font-size: 14px; margin-bottom: 4px; }}
#panel-head p  {{
  font-size: 11px; opacity: .85; margin: 0;
  word-break: break-all; line-height: 1.5;
}}
#panel-body {{ flex: 1; overflow-y: auto; padding: 12px; }}

.card {{
  background: #f8faff; border: 1px solid #dce8ff;
  border-radius: 8px; padding: 12px; margin-bottom: 10px;
}}
.card-title {{
  font-size: 13px; font-weight: 700;
  color: #1a3a6b; margin-bottom: 8px;
}}
.row {{
  display: flex; justify-content: space-between;
  font-size: 12px; padding: 3px 0;
  border-bottom: 1px solid #edf2ff;
}}
.row:last-child {{ border-bottom: none; }}
.lbl {{ color: #888; white-space: nowrap; margin-right: 8px; }}
.val {{ font-weight: 600; color: #1a1a2e; text-align: right; }}

.kbtn {{
  display: inline-block;
  background: #fff; border: 2px solid #3396ff;
  border-radius: 8px; padding: 8px 16px;
  font-size: 13px; font-weight: 700; color: #1a3a6b;
  font-family: 'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  box-shadow: 0 3px 12px rgba(0,0,0,.15);
  cursor: pointer; white-space: nowrap;
  position: relative; transition: background .1s;
}}
.kbtn:hover {{ background: #e8f0ff; }}
.kbtn.loading {{ color: #888; border-color: #ccc; cursor: default; }}
.kbtn::after {{
  content: '';
  position: absolute;
  bottom: -10px; left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: #3396ff;
}}
.kbtn.loading::after {{ border-top-color: #ccc; }}

.msg {{ text-align: center; color: #aaa; font-size: 13px; padding: 40px 0; line-height: 1.8; }}
.err {{ color: #e53e3e; font-size: 13px; padding: 16px; line-height: 1.6; }}
</style>
</head>
<body>
<div id="root">
  <div id="map-wrap"><div id="map"></div></div>
  <div id="panel">
    <div id="panel-head">
      <h3 id="ph-title">📋 건축물 정보</h3>
      <p  id="ph-addr">지도를 클릭하세요</p>
    </div>
    <div id="panel-body">
      <div class="msg">지도에서 건물 위치를 클릭하면<br>건축물대장이 표시됩니다.</div>
    </div>
  </div>
</div>

<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
var LEDGER_KEY = "{LEDGER_KEY}";
var VWORLD_KEY = "{VWORLD_KEY}";
var map, ov, geocoder;

kakao.maps.load(function() {{
  map = new kakao.maps.Map(document.getElementById('map'), {{
    center: new kakao.maps.LatLng(37.5668, 126.9786),
    level: 3
  }});

  // ★ 카카오맵 SDK 내장 Geocoder (MAP_JS_KEY로 동작, ADDR_REST_KEY 불필요)
  geocoder = new kakao.maps.services.Geocoder();

  kakao.maps.event.addListener(map, 'click', function(e) {{
    var lat = e.latLng.getLat();
    var lng = e.latLng.getLng();

    if (ov) ov.setMap(null);

    var btn = document.createElement('div');
    btn.className = 'kbtn';
    btn.textContent = '📋 건축물대장 조회';
    btn.onclick = function() {{
      if (btn.classList.contains('loading')) return;
      btn.classList.add('loading');
      btn.textContent = '⏳ 조회 중...';
      queryAll(lat, lng);
    }};

    ov = new kakao.maps.CustomOverlay({{
      map: map, position: e.latLng,
      content: btn, yAnchor: 1.0
    }});
  }});
}});

function queryAll(lat, lng) {{
  var ph = document.getElementById('ph-addr');
  var pb = document.getElementById('panel-body');

  // Geocoder: coord2RegionCode (법정동코드)
  geocoder.coord2RegionCode(lng, lat, function(regResult, regStatus) {{
    if (regStatus !== kakao.maps.services.Status.OK) {{
      showErr('법정동 코드 조회 실패');
      return;
    }}

    var bDoc = regResult.find(function(d) {{ return d.region_type === 'B'; }});
    if (!bDoc) {{
      showErr('법정동 코드 없음 (도로·하천 구역)');
      return;
    }}

    // Geocoder: coord2Address (지번주소)
    geocoder.coord2Address(lng, lat, function(adrResult, adrStatus) {{
      if (adrStatus !== kakao.maps.services.Status.OK || !adrResult.length) {{
        showErr('주소 조회 실패');
        return;
      }}

      var a    = adrResult[0].address;
      var bun  = a.main_address_no;
      var ji   = a.sub_address_no || '0';
      var pnu  = bDoc.code + '1' + bun.padStart(4,'0') + ji.padStart(4,'0');
      var addr = a.address_name;

      ph.textContent = '📍 ' + addr;
      pb.innerHTML   = '<div class="msg">건축물대장 조회 중...</div>';
      if (ov) ov.setMap(null);

      drawParcel(pnu);
      fetchLedger(bDoc.code, bun, ji);
    }});
  }});
}}

// 건축물대장 API (공공데이터포털, CORS: Access-Control-Allow-Origin: *)
function fetchLedger(bCode, bun, ji) {{
  var url = 'https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo'
    + '?serviceKey=' + encodeURIComponent(LEDGER_KEY)
    + '&sigunguCd=' + bCode.slice(0,5)
    + '&bjdongCd='  + bCode.slice(5,10)
    + '&platGbCd=0'
    + '&bun='  + bun.padStart(4,'0')
    + '&ji='   + ji.padStart(4,'0')
    + '&pageNo=1&numOfRows=30&_type=json';

  fetch(url)
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      var raw      = ((data.response||{{}}).body||{{}}).items||{{}};
      var itemsRaw = raw.item;
      var items    = !itemsRaw ? []
                   : Array.isArray(itemsRaw) ? itemsRaw : [itemsRaw];
      renderPanel(items);
    }})
    .catch(function(e) {{
      showErr('건축물대장 조회 실패: ' + e.message);
    }});
}}

function renderPanel(items) {{
  var pb = document.getElementById('panel-body');
  if (!items.length) {{
    pb.innerHTML = '<div class="msg">등록된 건물 정보 없음</div>';
    return;
  }}
  pb.innerHTML = items.map(function(item) {{
    return '<div class="card">'
      + '<div class="card-title">🏢 ' + (item.bldNm||'건물명 없음') + '</div>'
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

function showErr(msg) {{
  document.getElementById('ph-addr').textContent = '⚠️ 오류';
  document.getElementById('panel-body').innerHTML = '<div class="err">⚠️ ' + msg + '</div>';
  if (ov) ov.setMap(null);
}}

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
