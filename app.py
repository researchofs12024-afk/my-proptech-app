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
query_params = st.query_params

# 지도 중심점 설정
map_lat = 37.5668
map_lng = 126.9786
if "lat" in query_params:
    map_lat = float(query_params["lat"])
    map_lng = float(query_params["lng"])

with col1:
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            html, body {{ margin:0; padding:0; height:100%; width:100%; }}
            #map {{ width:100%; height:650px; border-radius:10px; border:1px solid #ccc; }}
            #status {{ position: absolute; top: 10px; left: 10px; z-index: 10; padding:10px; background:white; border:2px solid #333; font-size:13px; font-weight:bold; border-radius:5px; }}
        </style>
    </head>
    <body>
        <div id="status">📍 지도의 건물(필지)을 클릭하세요.</div>
        <div id="map"></div>

        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map, currentPoly, marker;
            
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                map = new kakao.maps.Map(container, {{ 
                    center: new kakao.maps.LatLng({map_lat}, {map_lng}), 
                    level: 2 
                }});
                map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                var geocoder = new kakao.maps.services.Geocoder();

                kakao.maps.event.addListener(map, 'click', function(e) {{
                    var lat = e.latLng.getLat();
                    var lng = e.latLng.getLng();
                    document.getElementById('status').innerText = "⏳ 주소 데이터 분석 중...";

                    // 1. 주소 및 지번 정보 추출 시도
                    geocoder.coord2Address(lng, lat, function(res, stat) {{
                        // 2. 행정동/법정동 코드 추출 시도 (백업용)
                        geocoder.coord2RegionCode(lng, lat, function(resReg, statReg) {{
                            
                            var b_code = "", addr_name = "알 수 없는 주소", bun = "0", ji = "0";

                            // 지번 정보가 있다면 추출
                            if (stat === kakao.maps.services.Status.OK && res[0].address) {{
                                var a = res[0].address;
                                b_code = a.b_code;
                                addr_name = a.address_name;
                                bun = a.main_address_no;
                                ji = a.sub_address_no || '0';
                            }} 
                            // 지번 정보가 없으면 행정구역 정보에서 코드라도 가져옴
                            else if (statReg === kakao.maps.services.Status.OK) {{
                                for(var i=0; i<resReg.length; i++) {{
                                    if(resReg[i].region_type === 'B') {{
                                        b_code = resReg[i].code;
                                        addr_name = resReg[i].address_name;
                                        break;
                                    }}
                                }}
                            }}

                            if (b_code) {{
                                var pnu = b_code + '1' + bun.padStart(4, '0') + ji.padStart(4, '0');
                                var newUrl = window.location.origin + window.location.pathname + 
                                             '?b_code=' + b_code + '&bun=' + bun + '&ji=' + ji + 
                                             '&addr=' + encodeURIComponent(addr_name) + '&pnu=' + pnu +
                                             '&lat=' + lat + '&lng=' + lng;
                                window.top.location.href = newUrl;
                            }} else {{
                                document.getElementById('status').innerText = "❌ 주소 정보를 찾을 수 없습니다. 다른 곳을 클릭하세요.";
                            }}
                        }});
                    }});
                }});

                // 하이라이트 및 마커 그리기
                var params = new URLSearchParams(window.location.search);
                var pnu = params.get('pnu');
                if(pnu) {{
                    fetch("https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback", {{mode: 'no-cors'}})
                    .then(() => {{
                        var script = document.createElement('script');
                        script.src = "https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback";
                        document.body.appendChild(script);
                    }});
                }}
            }});

            window.vCallback = function(data) {{
                if(data.response && data.response.status === 'OK') {{
                    var geom = data.response.result.featureCollection.features[0].geometry.coordinates;
                    while(Array.isArray(geom[0][0])) {{ geom = geom[0]; }}
                    var path = geom.map(c => new kakao.maps.LatLng(c[1], c[0]));
                    currentPoly = new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map }});
                    document.getElementById('status').innerText = "✅ 필지 확인 완료";
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=670)

with col2:
    st.subheader("📋 건축물 상세 정보")
    if "b_code" in query_params:
        addr = query_params["addr"]
        st.success(f"📍 {addr}")
        items = get_ledger_data(query_params["b_code"], query_params["bun"], query_params["ji"])
        if items:
            for item in items:
                with st.expander(f"🏢 {item.get('bldNm', '명칭 없음')}", expanded=True):
                    st.write(f"**주용도:** {item.get('mainPurpsCdNm')}")
                    st.write(f"**층수:** {item.get('grndFlrCnt')}층 / {item.get('ugrndFlrCnt')}층")
                    st.write(f"**연면적:** {item.get('totArea')} ㎡")
        else:
            st.warning("등록된 건축물 정보가 없습니다.")
    else:
        st.info("지도의 대지를 클릭해 주세요.")
