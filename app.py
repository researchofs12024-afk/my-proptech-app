import streamlit as st
import pandas as pd
import requests
import urllib3
import folium
from streamlit_folium import st_folium

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 모든 키 입력 ---
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 (검증된 로직) ---
def get_info(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 법정동코드 조회 (카카오 REST API)
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        
        # 지번 주소 조회 (카카오 REST API)
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return None
        
        addr_info = addr_res['documents'][0]['address']
        pnu = b_code + '1' + addr_info['main_address_no'].zfill(4) + (addr_info['sub_address_no'] or '0').zfill(4)
        
        # 건축물대장 Hub API 조회
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {
            'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10],
            'platGbCd': '0', 'bun': addr_info['main_address_no'].zfill(4), 
            'ji': (addr_info['sub_address_no'] or '0').zfill(4), 
            'pageNo': '1', 'numOfRows': '30', '_type': 'json'
        }
        res = requests.get(url, params=params, verify=False, timeout=5).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        return {
            "addr": addr_info['address_name'],
            "pnu": pnu,
            "items": [items] if isinstance(items, dict) else items
        }
    except:
        return None

# --- 2. 세션 상태 관리 (번쩍임 방지 핵심) ---
if "map_center" not in st.session_state:
    st.session_state.map_center = [37.5668, 126.9786]
if "selected_data" not in st.session_state:
    st.session_state.selected_data = None
if "polygon_geom" not in st.session_state:
    st.session_state.polygon_geom = None

st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")

# --- 3. 화면 레이아웃 ---
col1, col2 = st.columns([2, 1])

with col1:
    # 지도 객체 생성
    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=18,
        tiles=None
    )
    
    # 배경: 브이월드 기본지도 (Base)
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
        attr="Vworld Base", name="배경지도", overlay=False, control=False
    ).add_to(m)

    # 레이어: 지적도 (투명도 조절로 도로가 보이게 함)
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wms?SERVICE=WMS&REQUEST=GetMap&LAYERS=lp_pa_cbnd_bu&STYLES=lp_pa_cbnd_bu&FORMAT=image/png&TRANSPARENT=TRUE&KEY={VWORLD_KEY}&DOMAIN=http://localhost&SRS=EPSG:3857&WIDTH=256&HEIGHT=256",
        attr="Vworld Cadastral", name="지적도", overlay=True, control=True, opacity=0.5
    ).add_to(m)

    # 하이라이트 표시 (클릭된 필지 모양)
    if st.session_state.polygon_geom:
        folium.GeoJson(
            st.session_state.polygon_geom,
            style_function=lambda x: {'fillColor': '#004cff', 'color': '#004cff', 'weight': 3, 'fillOpacity': 0.3}
        ).add_to(m)

    # 스트림릿에 지도 표시 (key="main_map"으로 고정하여 상태 유지)
    map_output = st_folium(m, width="100%", height=650, key="main_map")

    # [클릭 감지 로직]
    if map_output.get("last_clicked"):
        last_clicked = map_output["last_clicked"]
        # 이전에 클릭한 위치와 다를 때만 실행 (무한루프 방지)
        if st.session_state.get('prev_click') != last_clicked:
            st.session_state.prev_click = last_clicked
            
            # 1. 데이터 분석
            res_data = get_info(last_clicked["lat"], last_clicked["lng"])
            if res_data:
                st.session_state.selected_data = res_data
                st.session_state.map_center = [last_clicked["lat"], last_clicked["lng"]]
                
                # 2. 브이월드 경계선(하이라이트) 가져오기
                v_url = f"https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=http://localhost&attrFilter=pnu:={res_data['pnu']}&crs=EPSG:4326"
                try:
                    v_res = requests.get(v_url, timeout=3).json()
                    if v_res.get('response', {}).get('status') == 'OK':
                        st.session_state.polygon_geom = v_res['response']['result']['featureCollection']
                    else:
                        st.session_state.polygon_geom = None
                except:
                    st.session_state.polygon_geom = None
                
                # 즉시 새로고침하여 데이터 반영
                st.rerun()

with col2:
    st.subheader("📋 건축물 상세 정보")
    if st.session_state.selected_data:
        data = st.session_state.selected_data
        st.success(f"📍 {data['addr']}")
        
        if data['items']:
            for item in data['items']:
                with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                    c1, c2 = st.columns(2)
                    c1.metric("지상층수", f"{item.get('grndFlrCnt')}F")
                    c2.metric("지하층수", f"B{item.get('ugrndFlrCnt')}")
                    st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                    st.write(f"**구조:** {item.get('strctCdNm')}")
                    st.write(f"**연면적:** {item.get('totArea')} ㎡")
                    st.write(f"**사용승인:** {item.get('useAprvDe', '-')}")
        else:
            st.warning("등록된 건물이 없습니다.")
    else:
        st.info("지도를 클릭하면 정보가 나타납니다.")
