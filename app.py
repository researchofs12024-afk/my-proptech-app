import streamlit as st
import pandas as pd
import requests
import urllib3
import streamlit.components.v1 as components

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [API 키 설정] ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 정보 통합 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 (기존 성공 로직) ---
def get_building_data(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 카카오 법정동코드 및 주소 조회
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
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

# --- 2. 초기 상태 및 화면 레이아웃 ---
params = st.query_params
st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")

# 만약 URL에 좌표가 있다면 (지도를 클릭하고 새 창이 열렸다면)
if "lat" in params:
    lat = float(params.get("lat"))
    lng = float(params.get("lng"))
    
    st.divider()
    with st.spinner("🚀 클릭하신 대지의 정보를 분석 중입니다..."):
        addr_name, pnu, items = get_building_data(lat, lng)
        
    if pnu:
        st.success(f"📍 검색 결과: {addr_name}")
        if items:
            # 정보를 표나 카드 형태로 출력
            for item in items:
                with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')} 정보 보기", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("지상/지하", f"{item.get('grndFlrCnt')}F / B{item.get('ugrndFlrCnt')}")
                    c2.metric("연면적", f"{item.get('totArea')} ㎡")
                    c3.metric("승인일", item.get('useAprvDe', '-'))
                    st.write(f"**주용도:** {item.get('mainPurpsCdNm')} | **구조:** {item.get('strctCdNm')}")
        else:
            st.warning("등록된 건축물 정보가 없습니다.")
    else:
        st.error(addr_name)
    st.divider()

# --- 3. 지도 표시부 ---
st.subheader("🗺️ 지도를 움직여 대지를 클릭하세요")

# 현재 앱의 URL을 자동으로 알아내기
# (YOUR_APP_URL 수동 입력 없이 자동으로 처리하는 로직)
map_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
    <style>
        html, body, #map {{ width:100%; height:550px; margin:0; padding:0; border-radius:10px; overflow:hidden; }}
        #ui-panel {{ position: absolute; top: 15px; left: 15px; z-index: 100; padding:15px; background:rgba(255,255,255,0.95); border:2px solid #007bff; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.2); font-family:sans-serif; }}
        #search-link {{ display:none; margin-top:10px; padding:12px; background:#007bff; color:white; text-decoration:none; border-radius:5px; text-align:center; font-weight:bold; font-size:15px; }}
    </style>
</head>
<body>
    <div id="ui-panel">
        <div id="msg">📍 대지를 클릭하세요.</div>
        <a id="search-link" href="" target="_blank">🔍 건물 정보 조회하기 (새창)</a>
    </div>
    <div id="map"></div>

    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
    <script>
        var map_obj;
        kakao.maps.load(function() {{
            var container = document.getElementById('map');
            var options = {{ center: new kakao.maps.LatLng(37.5668, 126.9786), level: 2 }};
            map_obj = new kakao.maps.Map(container, options);
            map_obj.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

            kakao.maps.event.addListener(map_obj, 'click', function(e) {{
                var latlng = e.latLng;
                var lat = latlng.getLat();
                var lng = latlng.getLng();
                
                // [핵심] 현재 부모 창의 URL을 가져와서 쿼리 파라미터 생성
                var currentUrl = window.parent.location.href.split('?')[0];
                var nextUrl = currentUrl + '?lat=' + lat + '&lng=' + lng;
                
                document.getElementById('msg').innerHTML = "<b>위치 선택됨!</b>";
                var link = document.getElementById('search-link');
                link.style.display = "block";
                link.href = nextUrl; // 새 창으로 열릴 주소 설정
            }});
        }});
    </script>
</body>
</html>
"""
components.html(map_html, height=580)
