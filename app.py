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

st.set_page_config(page_title="카카오 부동산 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 (기존 성공 로직) ---
def get_building_info(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 카카오 법정동코드 조회
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        # 카카오 지번 주소 조회
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 정보를 찾을 수 없습니다.", None, None

        addr_obj = addr_res['documents'][0]['address']
        addr_name = addr_obj['address_name']
        bun = addr_obj['main_address_no']
        ji = addr_obj['sub_address_no'] or "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # 건축물대장 Hub API 조회
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10], 'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4), 'pageNo': '1', 'numOfRows': '30', '_type': 'json'}
        res = requests.get(url, params=params, verify=False, timeout=10).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        return addr_name, pnu, ([items] if isinstance(items, dict) else items)
    except:
        return "데이터 조회 중 오류가 발생했습니다.", None, None

# --- 2. 페이지 상태 관리 ---
if "clicked_pos" not in st.session_state:
    st.session_state.clicked_pos = None

st.title("🗺️ 카카오맵 기반 부동산 통합 플랫폼")

col1, col2 = st.columns([2, 1])

# --- 3. 좌측 지도창 (디자인 중심) ---
with col1:
    # 현재 클릭된 좌표가 있으면 지도의 중심으로 설정
    c_lat = st.session_state.clicked_pos["lat"] if st.session_state.clicked_pos else 37.5668
    c_lng = st.session_state.clicked_pos["lng"] if st.session_state.clicked_pos else 126.9786

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body, #map {{ width:100%; height:650px; margin:0; padding:0; border-radius:15px; }}
            #ui-info {{ position: absolute; top: 15px; left: 15px; z-index: 10; padding:12px; background:white; border:2px solid #ffcd00; border-radius:10px; font-family: 'Malgun Gothic', sans-serif; font-size:13px; font-weight:bold; box-shadow: 0 2px 6px rgba(0,0,0,0.2); }}
        </style>
    </head>
    <body>
        <div id="ui-info">📍 카카오 지도를 클릭해 주세요.</div>
        <div id="map"></div>

        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                var options = {{ center: new kakao.maps.LatLng({c_lat}, {c_lng}), level: 2 }};
                var map = new kakao.maps.Map(container, options);
                
                // 카카오맵 특유의 컨트롤들 추가
                map.addControl(new kakao.maps.MapTypeControl(), kakao.maps.ControlPosition.TOPRIGHT);
                map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);

                // 클릭 이벤트
                kakao.maps.event.addListener(map, 'click', function(e) {{
                    var latlng = e.latLng;
                    // [핵심] 쿼리 파라미터를 통해 부모 창을 새로고침 (가장 확실한 통신법)
                    var url = window.parent.location.origin + window.parent.location.pathname + "?lat=" + latlng.getLat() + "&lng=" + latlng.getLng();
                    window.parent.location.href = url;
                }});
            }});
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)

# --- 4. 우측 정보창 ---
with col2:
    st.subheader("📋 건축물 상세 정보")
    
    # URL에서 좌표를 가져옴
    params = st.query_params
    if "lat" in params and "lng" in params:
        lat = float(params["lat"])
        lng = float(params["lng"])
        st.session_state.clicked_pos = {"lat": lat, "lng": lng}
        
        with st.spinner("카카오 데이터를 분석 중..."):
            addr, pnu, items = get_building_data(lat, lng)
            
        if pnu:
            st.success(f"📍 {addr}")
            if items:
                for item in items:
                    with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                        st.write(f"**용도:** {item.get('mainPurpsCdNm')}")
                        st.write(f"**층수:** {item.get('grndFlrCnt')}F / B{item.get('ugrndFlrCnt')}")
                        st.write(f"**연면적:** {item.get('totArea')} ㎡")
            else:
                st.warning("등록된 건축물이 없습니다.")
        else:
            st.error(addr)
    else:
        st.info("지도를 클릭하면 정보가 나타납니다.")
