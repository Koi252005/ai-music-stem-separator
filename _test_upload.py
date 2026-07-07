"""Quick upload test for the API server."""
import json
import urllib.request

# Read the test wav file
with open("test_cli_input.wav", "rb") as f:
    wav_data = f.read()

boundary = "BOUNDARY12345XYZ"
body = b""
# model_id field
body += b"--" + boundary.encode() + b"\r\n"
body += b"Content-Disposition: form-data; name=\"model_id\"\r\n\r\n"
body += b"guitar\r\n"
# device field
body += b"--" + boundary.encode() + b"\r\n"
body += b"Content-Disposition: form-data; name=\"device\"\r\n\r\n"
body += b"cpu\r\n"
# file field
body += b"--" + boundary.encode() + b"\r\n"
body += b"Content-Disposition: form-data; name=\"file\"; filename=\"test_song.wav\"\r\n"
body += b"Content-Type: audio/wav\r\n\r\n"
body += wav_data + b"\r\n"
body += b"--" + boundary.encode() + b"--\r\n"

req = urllib.request.Request(
    "http://127.0.0.1:8080/api/jobs",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
resp = urllib.request.urlopen(req)
job = json.loads(resp.read())
job_id = job["id"]
print(f"Job created: {job_id}")
print(f"Status: {job['status']}")
print(f"Model: {job['model_id']}")

# Poll for completion
import time
for _ in range(60):
    time.sleep(5)
    resp2 = urllib.request.urlopen(f"http://127.0.0.1:8080/api/jobs/{job_id}")
    status_data = json.loads(resp2.read())
    st = status_data["status"]
    detail = status_data.get("stage_detail", "")
    elapsed = status_data.get("elapsed_seconds")
    print(f"  {st}: {detail} ({elapsed}s)")
    if st in ("completed", "failed"):
        if st == "completed":
            print("SUCCESS! Stems:", list(status_data["stems"].keys()))
        else:
            print("FAILED:", status_data.get("error"))
        break
