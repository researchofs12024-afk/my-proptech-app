import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 키 세팅 ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 ---
def get_all_info(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 카카오 지역 코드 API (법정동 추출)
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        
        # 카카오 주소 변환 API (지번/번지 추출)
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 정보를 찾을 수 없습니다.", None, None

        doc = addr_res['documents'][0]
        addr_name = doc['address']['address_name'] if doc.get('address') else doc.get('address_name', "주소 미상")
        bun = doc['address']['main_address_no'] if doc.get('address') else "0"
        ji = doc['address']['sub_address_no'] if doc.get('address') else "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # 정부 Hub API (건축물대장)
        base_url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {
            'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10],
            'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4),
            'pageNo': '1', 'numOfRows': '100', '_type': 'json'
        }
        g_res = requests.get(base_url, params=params, verify=False, timeout=10).json()
        items = g_res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        return addr_name, pnu, ([items] if isinstance(items, dict) else items)
    except Exception as e:
        return f"통신 오류: {e}", None, None

# --- 2. 초기 설정 및 파라미터 읽기 ---
params = st.query_params
lat = float(params.get("lat", 37.5668))
lng = float(params.get("lng", 126.9786))
current_pnu = None

st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")

col1, col2 = st.columns([2, 1])

# --- 3. 우측 정보창 (데이터 먼저 처리) ---
with col2:
    st.subheader("📋 건축물 상세 정보")
    if "lat" in params:
        with st.spinner("🚀 데이터를 불러오는 중..."):
            addr, pnu, items = get_all_info(lat, lng)
            if pnu:
                current_pnu = pnu
                st.success(f"📍 {addr}")
                if items:
                    for item in items:
                        with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                            st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                            st.write(f"**층수:** 지상 {item.get('grndFlrCnt')}F / 지하 {item.get('ugrndFlrCnt')}F")
                            st.write(f"**연면적:** {item.get('totArea')} ㎡")
                            st.write(f"**사용승인일:** {item.get('useAprvDe')}")
                else:
                    st.warning("등록된 건물이 없습니다.")
            else:
                st.error(addr)
    else:
        st.info("지도의 대지를 클릭하세요.")

# --- 4. 좌측 지도창 ---
with col1:
    pnu_val = f"'{current_pnu}'" if current_pnu else "null"
    
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body, #map {{ width:100%; height:650px; margin:0; padding:0; border-radius:10px; overflow:hidden; }}
            #status {{ position: absolute; top: 10px; left: 10px; z-index: 10; padding:10px; background:white; border:2px solid #333; font-size:13px; font-weight:bold; border-radius:5px; font-family:sans-serif; }}
            #retry-btn {{ display:none; margin-top:10px; padding:5px 10px; background:#007bff; color:white; text-decoration:none; border-radius:3px; }}
        </style>
    </head>
    <body>
        <div id="status">
            <span id="msg">📍 지도를 클릭하세요.</span>
            <a id="retry-btn" href="#" target="_top">조회하기 (클릭)</a>
        </div>
        <div id="map"></div>
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map_obj;
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                var options = {{ center: new kakao.maps.LatLng({lat}, {lng}), level: 2 }};
                map_obj = new kakao.maps.Map(container, options);
                map_obj.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                kakao.maps.event.addListener(map_obj, 'click', function(e) {{
                    var latlng = e.latLng;
                    var nextUrl = window.parent.location.origin + window.parent.location.pathname + '?lat=' + latlng.getLat() + '&lng=' + latlng.getLng();
                    
                    document.getElementById('msg').innerText = "⏳ 전송 중... 안 되면 아래 버튼 클릭:";
                    document.getElementById('retry-btn').style.display = "inline-block";
                    document.getElementById('retry-btn').href = nextUrl;

                    // [핵심] 부모 창 주소 변경 시도 (가장 안정적인 방식 조합)
                    try {{
                        window.parent.location.href = nextUrl;
                    }} catch(err) {{
                        window.top.location.assign(nextUrl);
                    }}
                }});

                // 하이라이트 (Vworld)
                var pnu = {pnu_val};
                if(pnu) {{
                    var vUrl = "https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.parent.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback";
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
                    new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map_obj }});
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)
