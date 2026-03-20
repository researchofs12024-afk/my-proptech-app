import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 사용자님의 모든 키 세팅 ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"    # 지도 로딩용 (App 2 JS)
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" # 주소 변환용 (App 2 REST)
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b" # 정부 Hub API
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98" # 하이라이트용

st.set_page_config(page_title="부동산 정보 플랫폼", layout="wide")
st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")

# --- 1. [파이썬 전용] 주소 변환 및 건축물 조회 로직 ---
def get_address_and_building(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    
    # A. 카카오 REST API로 주소/코드 추출 (코랩에서 성공했던 로직)
    try:
        # 법정동코드(B) 추출용
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        
        # 지번/번지 추출용
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 정보를 찾을 수 없습니다.", None, None

        doc = addr_res['documents'][0]
        addr_name = doc['address']['address_name'] if doc.get('address') else doc.get('address_name', "주소 미상")
        bun = doc['address']['main_address_no'] if doc.get('address') else "0"
        ji = doc['address']['sub_address_no'] if doc.get('address') else "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # B. 정부 Hub API로 건축물대장 조회 (성공했던 로직)
        base_url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {
            'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10],
            'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4),
            'pageNo': '1', 'numOfRows': '100', '_type': 'json'
        }
        res = requests.get(base_url, params=params, verify=False, timeout=10).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        return addr_name, pnu, ([items] if isinstance(items, dict) else items)
    except Exception as e:
        return f"오류 발생: {e}", None, None

# --- 2. [화면 구성] 좌측 지도 / 우측 데이터 ---
col1, col2 = st.columns([2, 1])
query_params = st.query_params

# 클릭된 좌표 읽기
lat_param = query_params.get("lat", 37.5668)
lng_param = query_params.get("lng", 126.9786)

with col1:
    # 지도에서 클릭 시 URL만 변경하여 새로고침하는 초간결 자바스크립트
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body, #map {{ width:100%; height:650px; margin:0; padding:0; border-radius:10px; }}
            #status {{ position: absolute; top: 10px; left: 10px; z-index: 10; padding:10px; background:white; border:2px solid #333; font-size:13px; font-weight:bold; border-radius:5px; font-family:sans-serif; }}
        </style>
    </head>
    <body>
        <div id="status">📍 지도의 대지(건물)를 클릭하세요.</div>
        <div id="map"></div>
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            kakao.maps.load(function() {{
                var map = new kakao.maps.Map(document.getElementById('map'), {{
                    center: new kakao.maps.LatLng({lat_param}, {lng_param}),
                    level: 2
                }});
                map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                kakao.maps.event.addListener(map, 'click', function(e) {{
                    var lat = e.latLng.getLat();
                    var lng = e.latLng.getLng();
                    document.getElementById('status').innerText = "⏳ 데이터 분석 중...";
                    
                    // [핵심] 주소 검색은 생략하고 좌표만 부모 창으로 전송하여 새로고침
                    var newUrl = window.location.origin + window.location.pathname + '?lat=' + lat + '&lng=' + lng;
                    window.top.location.href = newUrl;
                }});

                // 하이라이트 (Vworld) - PNU가 URL에 있을 때만 실행
                var pnu = new URLSearchParams(window.location.search).get('pnu');
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

# --- 3. 우측 정보창: 파이썬이 모든 것을 처리 ---
with col2:
    st.subheader("📋 건축물 상세 정보")
    
    if "lat" in query_params:
        lat, lng = float(query_params["lat"]), float(query_params["lng"])
        
        with st.spinner("정보 분석 중..."):
            addr, pnu, items = get_address_and_building(lat, lng)
        
        if pnu:
            # PNU를 URL에 살짝 추가 (자바스크립트 하이라이트용)
            if "pnu" not in query_params:
                st.query_params["pnu"] = pnu
            
            st.success(f"📍 {addr}")
            
            if items:
                for item in items:
                    with st.expander(f"🏢 {item.get('bldNm', '명칭 없음')}", expanded=True):
                        c1, c2 = st.columns(2)
                        c1.metric("지상층수", f"{item.get('grndFlrCnt')}F")
                        c2.metric("지하층수", f"{item.get('ugrndFlrCnt')}F")
                        st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                        st.write(f"**연면적:** {item.get('totArea')} ㎡")
                        st.write(f"**사용승인일:** {item.get('useAprvDe')}")
            else:
                st.warning("등록된 건축물 정보가 없습니다.")
        else:
            st.error(addr)
    else:
        st.info("지도를 클릭하여 정보를 확인하세요.")
