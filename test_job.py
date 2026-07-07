"""Test guitar job pipeline end-to-end."""
import sys
import urllib.request
import json
import time

TEST_FILE = r'F:\THE FUCKING PROJECT\guitar_backingtrack-main\uploads\02d641eb-280c-466a-884f-5e3345c0575a\input.mp3'
BASE_URL = 'http://127.0.0.1:7860'

boundary = b'TESTBOUNDARY12345'
with open(TEST_FILE, 'rb') as f:
    fdata = f.read()

sep = b'--' + boundary + b'\r\n'
end = b'--' + boundary + b'--\r\n'
body = (
    sep +
    b'Content-Disposition: form-data; name="file"; filename="test.mp3"\r\n' +
    b'Content-Type: audio/mpeg\r\n\r\n' +
    fdata + b'\r\n' +
    sep +
    b'Content-Disposition: form-data; name="model_id"\r\n\r\nguitar\r\n' +
    sep +
    b'Content-Disposition: form-data; name="device"\r\n\r\ncpu\r\n' +
    end
)

print(f'Uploading {len(fdata)/1024:.1f} KB...')
req = urllib.request.Request(
    BASE_URL + '/api/jobs',
    data=body,
    headers={'Content-Type': 'multipart/form-data; boundary=TESTBOUNDARY12345'},
    method='POST',
)
try:
    r = urllib.request.urlopen(req, timeout=60)
    job = json.loads(r.read())
    job_id = job['id']
    print(f'Job created: {job_id}')
    print(f'Status: {job["status"]} | Model: {job["model_id"]}')
except Exception as e:
    print(f'ERROR creating job: {e}')
    sys.exit(1)

print('\nPolling job status (guitar model takes 30-90s on CPU)...')
for i in range(120):
    time.sleep(5)
    try:
        r2 = urllib.request.urlopen(f'{BASE_URL}/api/jobs/{job_id}', timeout=10)
        j = json.loads(r2.read())
        elapsed = j.get('elapsed_seconds') or 0
        print(f'  [{i*5:3d}s] status={j["status"]:<15} detail={str(j.get("stage_detail",""))[:35]:<35} elapsed={elapsed:.0f}s')
        if j['status'] == 'completed':
            stems_list = list(j['stems'].keys())
            print(f'\nSUCCESS! Stems: {stems_list}')
            print(f'Download: {j.get("download_url")}')
            sys.exit(0)
        if j['status'] == 'failed':
            print(f'\nFAILED: {j.get("error")}')
            sys.exit(1)
    except Exception as e:
        print(f'  Poll error: {e}')

print('\nTIMEOUT - job still running after 10 minutes')
