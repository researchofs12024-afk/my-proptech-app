"""
부동산 통합 플랫폼 - 카카오맵
===============================
streamlit-js-eval 완전 제거 버전
JS → Python 통신: st.query_params (Streamlit 내장)
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAP_JS_KEY    = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076"
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

# ── 세션 초기화 ─────────────────────────────────────
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
        b_code = next((d["code"] for d in reg.get("documents", []) if d.get("region_type") == "B"), None)

        adr = requests.get(
            f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}",
            headers=headers, timeout=5).json()

        if not b_code:       return None, None, None, "법정동 코드 없음 (도로·하천 구역)"
        if not adr.get("documents"): return None, None, None, "주소 정보 없음"

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


# ── query_params로 좌표 수신 ────────────────────────
# 카카오맵 iframe 안에서 window.parent.location을 바꾸는 게
# Streamlit Cloud sandbox에서 막히는 경우가 있음.
# 대신 iframe 자체 URL을 바꾸는 게 아니라,
# Streamlit이 렌더하는 페이지 URL에 ?lat=&lng= 를 붙이는 방식.
# → 카카오맵 HTML 안에서 window.top.location.href 로 시도하되
#   실패하면 window.location.href 로 fallback (현재 iframe만 이동, 의미없음)
# → 가장 확실한 방법: 지도 클릭 시 Streamlit 페이지 자체를 새 URL로 이동
#   (window.top.location.href = "?lat=...&lng=...")
#   Streamlit Cloud는 같은 origin이므로 top.location 변경 허용됨

qp = st.query_params
if "lat" in qp and "lng" in qp:
    try:
        lat = float(qp["lat"])
        lng = float(qp["lng"])
        coord_key = f"{lat},{lng}"
        if coord_key != st.session_state.last_coord:
            with st.spinner("🔍 건축물대장 조회 중..."):
                addr, pnu, items, err = get_building_data(lat, lng)
            st.session_state.last_coord = coord_key
            st.session_state.map_lat    = lat
            st.session_state.map_lng    = lng
            st.session_state.addr       = addr
            st.session_state.pnu        = pnu
            st.session_state.items      = items
            st.session_state.err        = err
            # URL 파라미터 제거 후 rerun (무한루프 방지)
            st.query_params.clear()
            st.rerun()
    except (ValueError, KeyError):
        st.query_params.clear()

# ── 레이아웃 ───────────────────────────────────────
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
                        ("주용도",    "mainPurpsCdNm"),
                        ("지상층수",  "grndFlrCnt"),
                        ("지하층수",  "ugrndFlrCnt"),
                        ("연면적(㎡)","totArea"),
                        ("사용승인일","useAprDay"),
                        ("주구조",    "mainStructCdNm"),
                        ("건폐율(%)", "bcRat"),
                        ("용적률(%)", "vlRat"),
                    ]:
                        val = item.get(key) or "-"
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"font-size:13px;padding:4px 0;border-bottom:1px solid #f0f2f6'>"
                            f"<span style='color:#888'>{label}</span>"
                            f"<span style='font-weight:600'>{val}</span></div>",
                            unsafe_allow_html=True)

with col_map:
    pnu_js  = st.session_state.pnu or ""
    lat_c   = st.session_state.map_lat
    lng_c   = st.session_state.map_lng

    # window.top.location.href 방식:
    # Streamlit Cloud에서 iframe과 부모 페이지는 같은 origin
    # → window.top 접근 가능 → URL 파라미터로 좌표 전달
    map_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html,body{{margin:0;padding:0;}}
#map{{width:100%;height:680px;}}
.kbtn{{
  background:#fff;border:2px solid #3396ff;border-radius:8px;
  padding:9px 16px;font-size:13px;font-weight:700;color:#1a3a6b;
  font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
  box-shadow:0 4px 14px rgba(0,0,0,.16);cursor:pointer;
  white-space:nowrap;position:relative;
}}
.kbtn::after{{
  content:'';position:absolute;bottom:-10px;left:50%;
  transform:translateX(-50%);border:5px solid transparent;
  border-top-color:#3396ff;
}}
</style>
</head>
<body>
<div id="map"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
<script>
var map, ov;

kakao.maps.load(function(){{
  map = new kakao.maps.Map(document.getElementById('map'),{{
    center: new kakao.maps.LatLng({lat_c},{lng_c}),
    level: 3
  }});

  var pnu = "{pnu_js}";
  if(pnu) drawParcel(pnu);

  kakao.maps.event.addListener(map,'click',function(e){{
    var lat = e.latLng.getLat(), lng = e.latLng.getLng();
    if(ov) ov.setMap(null);
    var btn = '<div class="kbtn" onclick="go('+lat+','+lng+')">📋 건축물대장 조회</div>';
    ov = new kakao.maps.CustomOverlay({{map:map,position:e.latLng,content:btn,yAnchor:2.0}});
  }});
}});

function go(lat,lng){{
  // Streamlit 페이지(top)의 URL을 ?lat=&lng=로 변경
  // → Streamlit이 query_params 변화를 감지해 rerun
  var base = window.top.location.pathname;
  window.top.location.href = base + '?lat=' + lat + '&lng=' + lng;
}}

function drawParcel(pnu){{
  var s=document.createElement('script');
  s.src='https://api.vworld.kr/req/data?service=data&request=GetFeature'
    +'&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}'
    +'&attrFilter=pnu:='+pnu+'&crs=EPSG:4326&callback=vCb';
  document.body.appendChild(s);
}}

window.vCb=function(d){{
  if(!d.response||d.response.status!=='OK') return;
  var f=d.response.result.featureCollection.features;
  if(!f||!f.length) return;
  var g=f[0].geometry.coordinates;
  while(Array.isArray(g[0][0])) g=g[0];
  var path=g.map(function(c){{return new kakao.maps.LatLng(c[1],c[0]);}});
  new kakao.maps.Polygon({{map:map,path:path,
    strokeWeight:3,strokeColor:'#3396ff',strokeOpacity:1,
    fillColor:'#3396ff',fillOpacity:0.15}});
}};
</script>
</body>
</html>"""

    components.html(map_html, height=690, scrolling=False)
