import streamlit as st
import pandas as pd
import requests
import urllib3
import folium
from streamlit_folium import st_folium

# 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- [설정] 키 세팅 ---
ADDR_REST_KEY = "c5af33c0d1d6a654362d3fea152cc076" 
LEDGER_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide")

# --- 1. 데이터 처리 함수 ---
def get_info(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return None
        
        addr_info = addr_res['documents'][0]['address']
        pnu = b_code + '1' + addr_info['main_address_no'].zfill(4) + (addr_info['sub_address_no'] or '0').zfill(4)
        
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10], 'platGbCd': '0', 'bun': addr_info['main_address_no'].zfill(4), 'ji': (addr_info['sub_address_no'] or '0').zfill(4), 'pageNo': '1', 'numOfRows': '30', '_type': 'json'}
        res = requests.get(url, params=params, verify=False, timeout=5).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        return {"addr": addr_info['address_name'], "pnu": pnu, "items": [items] if isinstance(items, dict) else items}
    except:
        return None

# --- 2. 페이지 상태 관리 ---
if "map_center" not in st.session_state:
    st.session_state.map_center = [37.5668, 126.9786]
if "selected_data" not in st.session_state:
    st.session_state.selected_data = None
if "polygon_geom" not in st.session_state:
    st.session_state.polygon_geom = None

st.title("🏗️ 부동산 정보 통합 플랫폼")

# --- 3. 화면 레이아웃 ---
col1, col2 = st.columns([2, 1])

with col1:
    # 지도 생성 (배경 타일 없이 생성하여 브이월드 타일을 입힘)
    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=18,
        tiles=None # 기본 OSM 지도를 제거
    )
    
    # [변경] 브이월드 기본 배경지도 (도로와 건물 위주)
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
        attr="Vworld Base", name="배경지도", overlay=False, control=False
    ).add_to(m)

    # [변경] 지적도 레이어를 투명하게 설정 (필지 선만 보이도록)
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wms?SERVICE=WMS&REQUEST=GetMap&LAYERS=lp_pa_cbnd_bu&STYLES=lp_pa_cbnd_bu&FORMAT=image/png&TRANSPARENT=TRUE&KEY={VWORLD_KEY}&DOMAIN=http://localhost&SRS=EPSG:3857&WIDTH=256&HEIGHT=256",
        attr="Vworld Cadastral", name="지적도", overlay=True, control=True, opacity=0.4 # 투명도를 낮춰 배경이 잘 보이게 함
    ).add_to(m)

    # 선택된 대지 하이라이트
    if st.session_state.polygon_geom:
        folium.GeoJson(
            st.session_state.polygon_geom,
            style_function=lambda x: {'fillColor': '#ff0000', 'color': '#ff0000', 'weight': 3, 'fillOpacity': 0.2}
        ).add_to(m)

    # 지도 표시
    output = st_folium(m, width="100%", height=650, key="main_map")

    # 클릭 감지 및 처리
    if output.get("last_clicked") and (st.session_state.get('last_click_pos') != output["last_clicked"]):
        st.session_state.last_click_pos = output["last_clicked"]
        lat, lng = output["last_clicked"]["lat"], output["last_clicked"]["lng"]
        
        data = get_info(lat, lng)
        if data:
            st.session_state.selected_data = data
            # 브이월드에서 경계선 가져오기
            v_url = f"https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=http://localhost&attrFilter=pnu:={data['pnu']}&crs=EPSG:4326"
            try:
                v_res = requests.get(v_url, timeout=3).json()
                if v_res.get('response', {}).get('status') == 'OK':
                    st.session_state.polygon_geom = v_res['response']['result']['featureCollection']
                else: st.session_state.polygon_geom = None
            except: st.session_state.polygon_geom = None
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
                    c1.metric("지상", f"{item.get('grndFlrCnt')}F")
                    c2.metric("지하", f"B{item.get('ugrndFlrCnt')}")
                    st.write(f"**용도:** {item.get('mainPurpsCdNm')}")
                    st.write(f"**면적:** {item.get('totArea')} ㎡")
                    st.write(f"**사용승인:** {item.get('useAprvDe')}")
        else: st.warning("등록된 건물이 없습니다.")
    else: st.info("지도를 클릭하세요.")
