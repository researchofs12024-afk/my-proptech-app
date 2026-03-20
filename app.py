import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 모든 키 입력 ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
KAKAO_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076"
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 정보 플랫폼", layout="wide")

st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")
st.markdown("지도의 필지를 클릭하면 해당 대지의 건축물대장 정보를 조회합니다.")

# --- [파이썬 로직] 데이터 조회 함수 ---
def get_ledger_data(b_code, bun, ji):
    base_url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
    params = {
        'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10],
        'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4),
        'pageNo': '1', 'numOfRows': '30', '_type': 'json'
    }
    try:
        res = requests.get(base_url, params=params, verify=False, timeout=5)
        if res.status_code == 200:
            items = res.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            return [items] if isinstance(items, dict) else items
    except: return []
    return []

# --- [화면 구성] 좌측 지도 / 우측 데이터 ---
col1, col2 = st.columns([2, 1])

# 현재 주소창의 파라미터를 읽어옴
query_params = st.query_params

# 지도의 중심점 설정 (클릭한 곳이 있으면 그곳으로, 없으면 서울시청)
map_lat = 37.5668
map_lng = 126.9786
if "lat" in query_params:
    map_lat = float(query_params["lat"])
    map_lng = float(query_params["lng"])

with col1:
    # 지도 HTML/JS
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body {{ margin:0; padding:0; height:100%; width:100%; }}
            #map {{ width:100%; height:650px; border-radius:10px; border:1px solid #ccc; cursor: pointer; }}
            #v-status {{ position: absolute; top: 10px; left: 10px; z-index: 10; padding:8px; background:white; border:1px solid #ccc; font-size:12px; border-radius:5px; }}
        </style>
    </head>
    <body>
        <div id="v-status">지도를 클릭하면 정보가 나타납니다. (필지 안쪽 클릭)</div>
        <div id="map"></div>

        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map, currentPoly;
            
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                var options = {{ 
                    center: new kakao.maps.LatLng({map_lat}, {map_lng}), 
                    level: 2 
                }};
                map = new kakao.maps.Map(container, options);
                map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                var geocoder = new kakao.maps.services.Geocoder();

                // 클릭 이벤트
                kakao.maps.event.addListener(map, 'click', function(e) {{
                    var lat = e.latLng.getLat();
                    var lng = e.latLng.getLng();
                    
                    document.getElementById('v-status').innerText = "⏳ 주소 분석 중...";

                    geocoder.coord2Address(lng, lat, function(res, stat) {{
                        if (stat === kakao.maps.services.Status.OK && res[0].address) {{
                            var a = res[0].address;
                            var pnu = a.b_code + '1' + a.main_address_no.padStart(4, '0') + a.sub_address_no.padStart(4, '0');
                            
                            // 부모 주소창의 URL을 강제로 변경 (window.top 사용)
                            var newUrl = window.location.origin + window.location.pathname + 
                                         '?b_code=' + a.b_code + 
                                         '&bun=' + a.main_address_no + 
                                         '&ji=' + (a.sub_address_no || '0') + 
                                         '&addr=' + encodeURIComponent(a.address_name) + 
                                         '&pnu=' + pnu +
                                         '&lat=' + lat +
                                         '&lng=' + lng;
                            
                            // Streamlit Cloud의 Iframe 보안을 뚫기 위한 최상단 이동 명령어
                            window.top.location.href = newUrl;
                        }} else {{
                            document.getElementById('v-status').innerText = "❌ 지번 주소가 없습니다.";
                        }}
                    }});
                }});

                // 하이라이트 그리기
                var params = new URLSearchParams(window.location.search);
                var pnu = params.get('pnu');
                if(pnu) {{
                    var vUrl = "https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback";
                    var script = document.createElement('script');
                    script.src = vUrl;
                    document.body.appendChild(script);
                }}
            }});

            window.vCallback = function(data) {{
                if(data.response && data.response.status === 'OK') {{
                    var geom = data.response.result.featureCollection.features[0].geometry.coordinates;
                    while(Array.isArray(geom[0][0])) {{ geom = geom[0]; }}
                    var path = geom.map(c => new kakao.maps.LatLng(c[1], c[0]));
                    currentPoly = new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map }});
                    document.getElementById('v-status').innerText = "✅ 필지 확인 완료";
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)

with col2:
    st.subheader("📋 건축물 상세 정보")
    # Streamlit 최신 버전 쿼리 파라미터 읽기 방식
    if "b_code" in query_params:
        addr = query_params["addr"]
        b_code = query_params["b_code"]
        bun = query_params["bun"]
        ji = query_params["ji"]
        
        st.success(f"📍 {addr}")
        
        with st.spinner("데이터를 가져오는 중..."):
            items = get_ledger_data(b_code, bun, ji)
            
        if items:
            for item in items:
                with st.expander(f"🏢 {item.get('bldNm', '명칭 없음')} ({item.get('dongNm', '본동')})", expanded=True):
                    c1, c2 = st.columns(2)
                    c1.metric("지상층수", f"{item.get('grndFlrCnt')}F")
                    c2.metric("지하층수", f"{item.get('ugrndFlrCnt')}F")
                    st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                    st.write(f"**연면적:** {item.get('totArea')} ㎡")
                    st.write(f"**사용승인일:** {item.get('useAprvDe')}")
        else:
            st.warning("건축물대장 정보가 없습니다.")
    else:
        st.info("지도에서 대지(건물)를 클릭해 주세요.")
