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

# --- 1. 데이터 처리 함수 (기존 성공 로직 그대로 사용) ---
def get_info(lat, lng):
    headers = {"Authorization": f"KakaoAK {ADDR_REST_KEY}"}
    try:
        # 카카오 법정동코드 조회
        reg_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        b_code = next((doc['code'] for doc in reg_res.get('documents', []) if doc.get('region_type') == 'B'), None)
        # 카카오 주소 조회
        addr_res = requests.get(f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lng}&y={lat}", headers=headers, timeout=5).json()
        
        if not b_code or not addr_res.get('documents'):
            return "주소 없음", None, None, None

        doc = addr_res['documents'][0]
        addr_name = doc['address']['address_name'] if doc.get('address') else doc.get('address_name', "주소 미상")
        bun = doc['address']['main_address_no'] if doc.get('address') else "0"
        ji = doc['address']['sub_address_no'] if doc.get('address') else "0"
        pnu = b_code + '1' + bun.zfill(4) + ji.zfill(4)
        
        # 건축물대장 Hub API 조회
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
        params = {'serviceKey': LEDGER_KEY, 'sigunguCd': b_code[:5], 'bjdongCd': b_code[5:10], 'platGbCd': '0', 'bun': bun.zfill(4), 'ji': ji.zfill(4), 'pageNo': '1', 'numOfRows': '10', '_type': 'json'}
        res = requests.get(url, params=params, verify=False, timeout=5).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        return addr_name, pnu, ([items] if isinstance(items, dict) else items), b_code
    except:
        return "데이터 통신 오류", None, None, None

# --- 2. 화면 구성 ---
st.title("🏗️ 맞춤형 부동산 정보 통합 플랫폼")
col1, col2 = st.columns([2, 1])

# 세션 상태 초기화 (클릭 좌표 저장용)
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

with col1:
    st.subheader("🗺️ 지도를 클릭하세요")
    
    # 지도 생성 (브이월드 지도를 기본 배경으로 사용)
    m = folium.Map(location=[37.5668, 126.9786], zoom_start=18, tiles=None)
    
    # 배경: 브이월드 일반지도
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
        attr="Vworld", name="브이월드 일반", overlay=False, control=True
    ).add_to(m)

    # 지적도 레이어 추가 (항시 표시)
    folium.TileLayer(
        tiles=f"https://api.vworld.kr/req/wms?SERVICE=WMS&REQUEST=GetMap&LAYERS=lp_pa_cbnd_bu&STYLES=lp_pa_cbnd_bu&FORMAT=image/png&TRANSPARENT=TRUE&KEY={VWORLD_KEY}&DOMAIN=http://localhost&SRS=EPSG:3857&WIDTH=256&HEIGHT=256",
        attr="Vworld Cadastral", name="지적도", overlay=True, control=True, opacity=0.6
    ).add_to(m)

    # 지도를 스트림릿에 표시하고 클릭 이벤트 수집
    output = st_folium(m, width="100%", height=600, key="map")

    # 클릭된 좌표가 있다면 세션에 저장
    if output.get("last_clicked"):
        st.session_state.last_clicked = output["last_clicked"]

with col2:
    st.subheader("📋 건축물 상세 정보")
    
    if st.session_state.last_clicked:
        lat = st.session_state.last_clicked["lat"]
        lng = st.session_state.last_clicked["lng"]
        
        with st.spinner("🚀 정보를 분석 중입니다..."):
            addr, pnu, items, b_code = get_info(lat, lng)
            
        if pnu:
            st.success(f"📍 {addr}")
            
            # 하이라이트 (Vworld Polygon) 표시를 위한 안내
            st.caption(f"PNU: {pnu}")
            
            if items:
                for item in items:
                    with st.expander(f"🏢 {item.get('bldNm', '건물명 없음')}", expanded=True):
                        st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                        st.write(f"**층수:** {item.get('grndFlrCnt')}F / B{item.get('ugrndFlrCnt')}")
                        st.write(f"**연면적:** {item.get('totArea')} ㎡")
            else:
                st.warning("등록된 건물이 없습니다.")
        else:
            st.error("지번 정보가 없는 지점입니다.")
    else:
        st.info("지도에서 대지를 클릭해 보세요.")
