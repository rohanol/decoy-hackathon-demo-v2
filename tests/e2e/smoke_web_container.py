# Run manually after building dg-web-decoy:m4; only loopback HTTP is used.
import hashlib, http.client, json, os, subprocess, tempfile, time
from pathlib import Path
from urllib.parse import urlencode
from jsonschema import Draft202012Validator, FormatChecker
root = Path(__file__).resolve().parents[2]
def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()
with tempfile.TemporaryDirectory(prefix="dg-m4-smoke-") as directory:
    state = Path(directory)
    (state / "logs").mkdir()
    (state / "blocklist.json").write_text('{"version":0,"entries":[]}')
    (state / "honeytokens.yaml").write_bytes((root / "config/honeytokens.yaml").read_bytes())
    name = "dg-m4-smoke-" + str(os.getpid())
    try:
        docker("run", "-d", "--name", name, "--read-only", "--tmpfs", "/tmp",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "-p", "127.0.0.1::8080",
               "--mount", f"type=bind,src={state},dst=/config,readonly",
               "--mount", f"type=bind,src={state},dst=/state,readonly",
               "--mount", f"type=bind,src={state / 'logs'},dst=/logs",
               "-e", "HONEYTOKENS_PATH=/config/honeytokens.yaml",
               "-e", "BLOCKLIST_PATH=/state/blocklist.json",
               "-e", "LOG_PATH=/logs/web.json", "-e", "LAB_RUN_ID=smoke-m4", "dg-web-decoy:m4")
        port = int(docker("port", name, "8080/tcp").rsplit(":", 1)[1])
        def fetch(method, path, data=None):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            headers = {"Content-Type": "application/x-www-form-urlencoded"} if data is not None else {}
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            result = response.status, response.read()
            connection.close()
            return result
        for attempt in range(50):
            try:
                status, body = fetch("GET", "/")
                if status == 200:
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Container did not become ready")
        assert b"Operations Portal" in body
        assert fetch("POST", "/login", urlencode({"username": "svc_portal", "password": "DGLAB-Portal-4471"}))[0] == 200
        assert fetch("GET", "/search?q=x%27%20UNION%20SELECT%20name")[0] == 500
        status, data = fetch("GET", "/download?file=customer_data.csv")
        assert status == 200 and data == (root / "decoys/web/assets/customer_data.csv").read_bytes()
        assert fetch("GET", "/download?file=../../etc/passwd")[0] == 404
        assert fetch("GET", "/.env")[0] == 200
        # Replacing the file, not rewriting its inode, must be visible in-container.
        replacement = state / "blocklist.next"
        replacement.write_text("malformed")
        replacement.replace(state / "blocklist.json")
        assert fetch("GET", "/")[0] == 503
        replacement.write_text('{"version":2,"entries":[]}')
        replacement.replace(state / "blocklist.json")
        assert fetch("GET", "/")[0] == 200
        assert docker("exec", name, "id", "-u") == "1000"
        spec = json.loads(docker("inspect", name))[0]
        assert spec["HostConfig"]["ReadonlyRootfs"]
        assert not spec["HostConfig"]["Privileged"]
        assert "ALL" in spec["HostConfig"]["CapDrop"]
        events = [json.loads(line) for line in (state / "logs/web.json").read_text().splitlines()]
        validate = Draft202012Validator(json.loads((root / "contracts/event.schema.json").read_text()), format_checker=FormatChecker())
        for event in events:
            validate.validate(event)
        assert any(e["event_type"] == "auth_success" for e in events)
        served = next(e for e in events if e["event_type"] == "synthetic_file_access")
        assert served["attributes"]["sha256"] == hashlib.sha256(data).hexdigest()
        assert "DGLAB-Portal-4471" not in (state / "logs/web.json").read_text()
        print(f"PASS: live HTTP login/search/download/hidden route; {len(events)} schema-valid events; atomic state replacement observed; UID 1000, read-only root, no privileges/capabilities")
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, check=False)
