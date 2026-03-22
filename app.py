import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 모든 키 입력 ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 (성공 로직) ---
def get_building_data(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 1-1. 주소 및 코드 추출 (카카오 REST)
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 정보를 찾을 수 없습니다.", None, None

        addr_obj = addr_res['documents'][0]['address']
        addr_name = addr_obj['address_name']
        bun = addr_obj['main_address_no']
        ji = addr_obj['sub_address_no'] or "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # 1-2. 건축물대장 조회 (정부 API)
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10], 'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4), 'pageNo': '1', 'numOfRows': '30', '_type': 'json'}
        res = requests.get(url, params=params, verify=False, timeout=10).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        return addr_name, pnu, ([items] if isinstance(items, dict) else items)
    except Exception as e:
        return f"통신 오류: {e}", None, None

# --- 2. 초기 상태 설정 ---
st.title("🗺️ 카카오맵 부동산 정보 플랫폼")
params = st.query_params

# 지도의 중심점 유지
lat_center = float(params.get("lat", 37.5668))
lng_center = float(params.get("lng", 126.9786))

col1, col2 = st.columns([2, 1])

# --- 3. 우측 정보창 ---
with col2:
    st.subheader("📋 건축물 정보")
    if "lat" in params:
        with st.spinner("🚀 데이터를 분석 중..."):
            addr, pnu, items = get_building_data(float(params["lat"]), float(params["lng"]))
        
        if pnu:
            st.success(f"📍 {addr}")
            if items:
                for item in items:
                    with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                        st.write(f"**용도:** {item.get('mainPurpsCdNm')}")
                        st.write(f"**층수:** {item.get('grndFlrCnt')}F / B{item.get('ugrndFlrCnt')}")
                        st.write(f"**연면적:** {item.get('totArea')} ㎡")
            else: st.warning("등록된 건물이 없습니다.")
        else: st.error(addr)
    else:
        st.info("지도를 클릭한 뒤 나타나는 버튼을 눌러주세요.")

# --- 4. 좌측 지도창 (카카오맵 디자인) ---
with col1:
    current_pnu = pnu if "lat" in params and 'pnu' in locals() else ""
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body, #map {{ width:100%; height:650px; margin:0; padding:0; border-radius:15px; overflow:hidden; }}
            .customoverlay {{ position:relative; bottom:85px; border-radius:6px; border: 1px solid #ccc; border-bottom:2px solid #ddd; float:left; }}
            .customoverlay:nth-child(unique) {{ display:block; }}
            .customoverlay .title {{ display:block; text-align:center; background:#fff; margin-right:35px; padding:10px 15px; font-size:14px; font-weight:bold; border-radius:6px; }}
            .customoverlay .button {{ display:block; background:#3396ff; color:#fff; padding:10px 15px; font-size:14px; font-weight:bold; border-radius:0 6px 6px 0; position:absolute; right:0; top:0; cursor:pointer; border:none; }}
        </style>
    </head>
    <body>
        <div id="map"></div>

        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map, overlay;
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                map = new kakao.maps.Map(container, {{ center: new kakao.maps.LatLng({lat_center}, {lng_center}), level: 2 }});
                
                // 지적편집도는 선택사항 (원하시면 아래 줄 주석을 해제하세요)
                // map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                kakao.maps.event.addListener(map, 'click', function(e) {{
                    var lat = e.latLng.getLat();
                    var lng = e.latLng.getLng();
                    
                    if(overlay) overlay.setMap(null);

                    // [보안 우회 핵심] 카카오맵 감성의 버튼 생성
                    var content = '<div class="customoverlay">' +
                                  '  <span class="title">이 위치 조회하기</span>' +
                                  '  <form action="" method="get" target="_top" style="margin:0;">' +
                                  '    <input type="hidden" name="lat" value="' + lat + '">' +
                                  '    <input type="hidden" name="lng" value="' + lng + '">' +
                                  '    <button type="submit" class="button">GO</button>' +
                                  '  </form>' +
                                  '</div>';

                    overlay = new kakao.maps.CustomOverlay({{
                        map: map, position: e.latLng, content: content, yAnchor: 1 
                    }});
                }});

                // 하이라이트 (Vworld)
                var pnu = "{current_pnu}";
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
                    new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map }});
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)
