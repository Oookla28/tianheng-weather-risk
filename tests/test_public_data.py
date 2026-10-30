from src.ui.public_data import _parse_osm_xml, _parse_overpass


def test_parse_overpass_extracts_hospital_roads_and_boundary():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": 43.88, "lon": 125.32, "tags": {"amenity": "hospital", "name": "示例医院"}},
            {"type": "way", "id": 2, "tags": {"highway": "primary", "name": "示例道路"}, "geometry": [{"lat": 43.87, "lon": 125.30}, {"lat": 43.89, "lon": 125.34}]},
            {"type": "relation", "id": 3, "tags": {"boundary": "administrative", "admin_level": "8", "name": "示例区"}, "geometry": [{"lat": 43.86, "lon": 125.30}, {"lat": 43.90, "lon": 125.30}]},
        ]
    }
    result = _parse_overpass(payload)
    assert result["hospitals"][0]["name"] == "示例医院"
    assert result["roads"][0]["lat"] == [43.87, 43.89]
    assert result["boundaries"][0]["name"] == "示例区"


def test_parse_osm_map_extracts_realistic_way_layers():
    xml = '''<osm><node id="1" lat="43.87" lon="125.30"/><node id="2" lat="43.89" lon="125.34"/>
    <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/><tag k="name" v="主干道"/></way>
    <way id="11"><nd ref="1"/><nd ref="2"/><tag k="amenity" v="hospital"/><tag k="name" v="医院"/></way></osm>'''.encode("utf-8")
    result = _parse_osm_xml(xml)
    assert result["roads"][0]["name"] == "主干道"
    assert result["hospitals"][0]["name"] == "医院"
