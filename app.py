import streamlit as st
import streamlit.components.v1 as components

# --- [설정] 모든 키 입력 ---
MAP_JS_KEY = "ede7b455451821c17720156a3e8b5011"
VWORLD_KEY = "D2A7A3D2-EBE4-339F-A5A7-3C32E6751F98"
GOV_API_KEY = "9619e124e16b9e57bad6cfefdc82f6c87749176260b4caff32eda964aad5de1b"

st.set_page_config(page_title="부동산 통합 플랫폼", layout="wide")

# Streamlit의 기본 여백을 제거하여 꽉 찬 화면 만들기
st.markdown("""
    <style>
    .main .block-container { padding: 0; max-width: 100%; }
    iframe { border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- [올인원 HTML 컴포넌트] ---
all_in_one_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
    <style>
        body, html {{ margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; font-family: 'Malgun Gothic', sans-serif; }}
        #map {{ width: 100%; height: 100vh; position: relative; z-index: 1; }}
        
        /* 왼쪽 정보 팝업 스타일 */
        #side-panel {{
            position: absolute; top: 0; left: -400px; width: 350px; height: 100%;
            background: white; z-index: 100; transition: 0.3s;
            box-shadow: 2px 0 10px rgba(0,0,0,0.2); padding: 20px; overflow-y: auto;
        }}
        #side-panel.open {{ left: 0; }}
        #close-btn {{ position: absolute; top: 15px; right: 15px; cursor: pointer; font-size: 20px; font-weight: bold; color: #888; }}
        
        .loading {{ color: #007bff; font-weight: bold; }}
        .building-card {{ border: 1px solid #eee; padding: 15px; border-radius: 8px; margin-bottom: 15px; background: #f9f9f9; }}
        .addr-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #333; }}
        .info-row {{ font-size: 14px; margin: 5px 0; color: #555; }}
        .badge {{ display: inline-block; padding: 3px 8px; background: #007bff; color: white; border-radius: 4px; font-size: 12px; }}
    </style>
</head>
<body>

    <!-- 왼쪽 정보 창 -->
    <div id="side-panel">
        <div id="close-btn" onclick="closePanel()">×</div>
        <div id="content">
            <p>지도의 건물을 클릭하면 상세 정보가 나타납니다.</p>
        </div>
    </div>

    <!-- 지도 영역 -->
    <div id="map"></div>

    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
    <script>
        var map, currentPoly;

        kakao.maps.load(function() {{
            var container = document.getElementById('map');
            map = new kakao.maps.Map(container, {{ center: new kakao.maps.LatLng(37.5668, 126.9786), level: 2 }});
            map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT); // 지적도 활성화

            var geocoder = new kakao.maps.services.Geocoder();

            // 지도 클릭 이벤트
            kakao.maps.event.addListener(map, 'click', function(e) {{
                var lat = e.latLng.getLat();
                var lng = e.latLng.getLng();
                
                openPanel();
                document.getElementById('content').innerHTML = '<p class="loading">⏳ 정보를 분석 중입니다...</p>';

                // 1. 주소 및 PNU 추출
                geocoder.coord2Address(lng, lat, function(res, stat) {{
                    if (stat === kakao.maps.services.Status.OK && res[0].address) {{
                        var a = res[0].address;
                        var pnu = a.b_code + '1' + a.main_address_no.padStart(4, '0') + a.sub_address_no.padStart(4, '0');
                        fetchData(a.address_name, pnu, a.b_code, a.main_address_no, a.sub_address_no);
                        drawHighlight(pnu);
                    }} else {{
                        document.getElementById('content').innerHTML = '<p>❌ 지번 정보가 없는 지점입니다.</p>';
                    }}
                }});
            }});
        }});

        function openPanel() {{ document.getElementById('side-panel').classList.add('open'); }}
        function closePanel() {{ document.getElementById('side-panel').classList.remove('open'); }}

        // 2. 하이라이트 (Vworld)
        function drawHighlight(pnu) {{
            if (currentPoly) currentPoly.setMap(null);
            var vUrl = "https://api.vworld.kr/req/data?service=data&request=GetFeature&data=LP_PA_CBND_BU_GEOM&key={VWORLD_KEY}&domain=" + window.location.origin + "&attrFilter=pnu:=" + pnu + "&crs=EPSG:4326&callback=vCallback";
            var script = document.createElement('script');
            script.src = vUrl;
            document.body.appendChild(script);
        }}

        window.vCallback = function(data) {{
            if(data.response && data.response.status === 'OK') {{
                var geom = data.response.result.featureCollection.features[0].geometry.coordinates;
                while(Array.isArray(geom[0][0])) {{ geom = geom[0]; }}
                var path = geom.map(c => new kakao.maps.LatLng(c[1], c[0]));
                currentPoly = new kakao.maps.Polygon({{ path: path, strokeWeight: 3, strokeColor: '#004cff', fillOpacity: 0.2, map: map }});
            }}
        }};

        // 3. 건축물대장 데이터 가져오기 (정부 API 직접 호출)
        function fetchData(addr, pnu, b_code, bun, ji) {{
            var sigungu = b_code.substring(0, 5);
            var bjdong = b_code.substring(5, 10);
            var url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo?serviceKey={GOV_API_KEY}&sigunguCd=" + sigungu + "&bjdongCd=" + bjdong + "&platGbCd=0&bun=" + bun.padStart(4, '0') + "&ji=" + ji.padStart(4, '0') + "&_type=json&numOfRows=10";

            fetch(url)
                .then(res => res.json())
                .then(data => {{
                    var items = data.response.body.items.item;
                    if(!items) {{
                        document.getElementById('content').innerHTML = '<div class="addr-title">' + addr + '</div><p>등록된 건축물 정보가 없습니다.</p>';
                        return;
                    }}
                    if(!Array.isArray(items)) items = [items];

                    var html = '<div class="addr-title">' + addr + '</div>';
                    items.forEach(item => {{
                        html += '<div class="building-card">';
                        html += '<div class="badge">' + (item.bldNm || '건물명 없음') + '</div>';
                        html += '<div class="info-row"><b>주용도:</b> ' + item.mainPurpsCdNm + '</div>';
                        html += '<div class="info-row"><b>층수:</b> ' + item.grndFlrCnt + 'F / B' + item.ugrndFlrCnt + '</div>';
                        html += '<div class="info-row"><b>연면적:</b> ' + item.totArea + ' ㎡</div>';
                        html += '<div class="info-row"><b>승인일:</b> ' + item.useAprvDe + '</div>';
                        html += '</div>';
                    }});
                    document.getElementById('content').innerHTML = html;
                }})
                .catch(err => {{
                    document.getElementById('content').innerHTML = '<p>❌ 데이터 로드 중 오류가 발생했습니다.</p>';
                }});
        }}
    </script>
</body>
</html>
"""

# 화면에 표시 (높이를 100vh에 가깝게 설정)
components.html(all_in_one_html, height=850)
