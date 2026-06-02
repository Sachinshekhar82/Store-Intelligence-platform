import httpx

try:
    r = httpx.get("http://127.0.0.1:8000/stores/ST1008/heatmap", params={"camera_id": "CAM1"}, timeout=5.0)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        coords = data.get("coordinates", [])
        print(f"CAM1 coordinates count: {len(coords)}")
        if coords:
            print(f"First coordinates point: {coords[0]}")
    else:
        print(f"Failed: {r.text}")
except Exception as e:
    print(f"Error querying API: {e}")
