# 지도 HTML/JS
    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <!-- [핵심] HTTP 요청을 HTTPS로 강제 업그레이드하여 Mixed Content 에러 해결 -->
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            #map {{ width:100%; height:650px; border-radius:10px; border:1px solid #ccc; }}
            #v-status {{ padding:5px; font-size:12px; color:gray; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div id="v-status">필지를 클릭하세요.</div>

        <!-- 카카오 SDK 로드 (https 명시 및 autoload=false 사용) -->
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={MAP_JS_KEY}&libraries=services&autoload=false"></script>
        <script>
            var map, currentPoly;
            
            // SDK 로딩 대기
            kakao.maps.load(function() {{
                var container = document.getElementById('map');
                var options = {{ 
                    center: new kakao.maps.LatLng(37.5668, 126.9786), 
                    level: 2 
                }};
                map = new kakao.maps.Map(container, options);
                map.addOverlayMapTypeId(kakao.maps.MapTypeId.USE_DISTRICT);

                var geocoder = new kakao.maps.services.Geocoder();

                kakao.maps.event.addListener(map, 'click', function(e) {{
                    geocoder.coord2Address(e.latLng.getLng(), e.latLng.getLat(), function(res, stat) {{
                        if (stat === kakao.maps.services.Status.OK && res[0].address) {{
                            var a = res[0].address;
                            var pnu = a.b_code + '1' + a.main_address_no.padStart(4, '0') + a.sub_address_no.padStart(4, '0');
                            
                            // 부모(Streamlit) 주소창 변경
                            var newUrl = window.location.origin + window.location.pathname + '?b_code=' + a.b_code + '&bun=' + a.main_address_no + '&ji=' + (a.sub_address_no || '0') + '&addr=' + encodeURIComponent(a.address_name) + '&pnu=' + pnu;
                            parent.window.location.href = newUrl;
                        }}
                    }});
                }});

                // 하이라이트 실행 (URL에 pnu가 있을 때)
                var params = new URLSearchParams(window.location.search);
                var pnu = params.get('pnu');
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
                    map.setCenter(path[0]);
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(map_html, height=700)
