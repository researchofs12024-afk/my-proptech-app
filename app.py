import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [중요 설정] 본인의 Streamlit 앱 주소를 꼭 입력하세요 ---
# 예: "https://my-proptech-app.streamlit.app" (끝에 / 는 빼주세요)
YOUR_APP_URL = "https://my-proptech-app.streamlit.app"

# --- [API 키 설정] ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 정보 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 ---
def get_building_data(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 카카오 법정동코드 조회
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        
        # 카카오 지번 주소 조회
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 정보를 찾을 수 없습니다.", None, None

        doc = addr_res['documents'][0]
        addr_name = doc['address']['address_name'] if doc.get('address') else doc.get('address_name', "주소 미상")
        bun = doc['address']['main_address_no']
        ji = doc['address']['sub_address_no'] or "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # 건축물대장 Hub API 조회
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {
            'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10],
            'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4),
            'pageNo': '1', 'numOfRows': '100', '_type': 'json'
        }
        res = requests.get(url, params=params, verify=False, timeout=10).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        return addr_name, pnu, ([items] if isinstance(items, dict) else items)
    except Exception as e:
        return f"통신 오류: {e}", None, None

# --- 2. 초기 상태 설정 ---
params = st.query_params
lat = float(params.get("lat", 37.5668))
lng = float(params.get("lng", 126.9786))

st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")

col1, col2 = st.columns([2, 1])

# --- 3. 우측 정보창 ---
with col2:
    st.subheader("📋 건축물 상세 정보")
    if "lat" in params:
        with st.spinner("🚀 데이터를 분석 중입니다..."):
            addr_name, pnu, items = get_building_data(lat, lng)
            
            if pnu:
                st.success(f"📍 {addr_name}")
                if items:
                    for item in items:
                        with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                            st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                            st.write(f"**층수:** 지상 {item.get('grndFlrCnt')}F / 지하 {item.get('ugrndFlrCnt')}F")
                            st.write(f"**연면적:** {item.get('totArea')} ㎡")
                            st.write(f"**사용승인일:** {item.get('useAprvDe')}")
                else:
                    st.warning("등록된 건축물 정보가 없습니다.")
            else:
                st.error(addr_name)
    else:
        st.info("지도의 대지를 클릭한 후 [조회하기] 버튼을 눌러주세요.")

# --- 4. 좌측 지도창 ---
with col1:
    current_pnu = pnu if "lat" in params and 'pnu' in locals() else ""
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body, #map {{ width:100%; height:650px; margin:0; padding:0; border-radius:10px; overflow:hidden; }}
            #ui-panel {{ position: absolute; top: 15px; left: 15px; z-index: 100; padding:15px; background:rgba(255,255,255,0.95); border:2px solid #007bff; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.2); font-family:sans-serif; }}
            #search-btn {{ width:100%; padding:10px; background:#007bff; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer; font-size:14px; margin-top:10px; display:none; }}
            #search-btn:hover {{ background:#0056b3; }}
        </style>
    </head>
    <body>
        <div id="ui-panel">
            <div id="msg">📍 지도를 클릭하세요.</div>
            <!-- [보안 우회 핵심] target="_top"을 사용하는 FORM 태그 -->
            <form id="search-form" action="{YOUR_APP_URL}" method="get" target="_top">
                <input type="hidden" name="lat" id="form-lat">
                <input type="hidden" name="lng" id="form-lng">
                <button type="submit" id="search-btn">🔍 이 위치 조회하기</button>
            </form>
        </div>
        <div id="map"></div>

        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map_obj;
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                var options = {{ center: new kakao.maps.LatLng({lat}, {lng}), level: 2 }};
                map_obj = new kakao.maps.Map(container, options);

                kakao.maps.event.addListener(map_obj, 'click', function(e) {{
                    var latlng = e.latLng;
                    document.getElementById('msg').innerHTML = "<b>좌표 선택됨!</b><br><small>" + latlng.getLat().toFixed(4) + ", " + latlng.getLng().toFixed(4) + "</small>";
                    
                    // Form 데이터 세팅
                    document.getElementById('form-lat').value = latlng.getLat();
                    document.getElementById('form-lng').value = latlng.getLng();
                    
                    // 버튼 보여주기
                    document.getElementById('search-btn').style.display = "block";
                }});

                // 하이라이트 (Vworld)
                var pnu = "{current_pnu}";
                if(pnu) {{
                    var script = document.createElement('script');
                    script.src = "https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback";
                    document.body.appendChild(script);
                }}
            }});

            window.vCallback = function(data) {{
                if(data.response && data.response.status === 'OK') {{
                    var geom = data.response.result.featureCollection.features[0].geometry.coordinates;
                    while(Array.isArray(geom[0][0])) {{ geom = geom[0]; }}
                    var path = geom.map(c => new kakao.maps.LatLng(c[1], c[0]));
                    new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map_obj }});
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)
