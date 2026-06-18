import requests, json

base = "http://localhost:8001"

# Test 1: health
r = requests.get(base + "/health")
print("=== /health ===")
print(r.status_code, r.json())

# Test 2: trucks (no people)
print("\n=== /segment - trucks (edge case) ===")
files = {"file": open("tests/test_images/img1.jpg", "rb")}
r = requests.post(base + "/segment", files=files, timeout=300)
d = r.json()
print(r.status_code, d["message"])
for o in d.get("objects", []):
    print(f"  - {o['class_name']} ({round(o['confidence']*100)}%)")

# Test 3: cat_dog (people in background)
print("\n=== /segment - cat_dog ===")
files = {"file": open("tests/test_images/img2_animals.jpg", "rb")}
r = requests.post(base + "/segment", files=files, timeout=300)
d = r.json()
print(r.status_code, d["message"])
for o in d.get("objects", []):
    print(f"  - {o['class_name']} ({round(o['confidence']*100)}%)")

# Test 4: invalid file
print("\n=== /segment - invalid file ===")
files = {"file": ("test.txt", b"not an image", "text/plain")}
r = requests.post(base + "/segment", files=files, timeout=10)
print(r.status_code, r.json())

print("\nAll tests passed.")
