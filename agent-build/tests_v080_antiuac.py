"""Test logica anti-UAC v0.8.0 dell'agent Windows (parti OS-independent).
Esecuzione: cd /app/agent-build && python3 tests_v080_antiuac.py"""
import sys, os, tempfile

sys.argv = ["forgefps-agent", "--register-protocol"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forgefps_agent as fa


def main():
    tmp = tempfile.mkdtemp()
    fa._APPDATA_DIR = tmp
    vbs = os.path.join(tmp, "launcher.vbs")

    assert fa.AGENT_VERSION == "0.8.0"

    p = fa._write_hidden_launcher()
    assert p == vbs and os.path.exists(vbs)
    exe, ver = fa._parse_launcher_target(vbs)
    assert ver == "0.8.0", (exe, ver)
    print("1. scrittura + marker OK")

    newer = os.path.join(tmp, "newer.exe"); open(newer, "w").write("x")
    open(vbs, "w").write(f"' ## target={newer}|version=9.9.9\nOption Explicit\n")
    before = open(vbs).read()
    fa._write_hidden_launcher()
    assert open(vbs).read() == before, "anti-downgrade fallito"
    print("2. anti-downgrade OK")

    open(vbs, "w").write(f"' ## target={os.path.join(tmp,'ghost.exe')}|version=9.9.9\n")
    fa._write_hidden_launcher()
    assert fa._parse_launcher_target(vbs)[1] == "0.8.0"
    print("3. self-heal target inesistente OK")

    older = os.path.join(tmp, "older.exe"); open(older, "w").write("x")
    open(vbs, "w").write(f"' ## target={older}|version=0.0.1\n")
    fa._write_hidden_launcher()
    assert fa._parse_launcher_target(vbs)[1] == "0.8.0"
    print("4. upgrade da versione vecchia OK")

    open(vbs, "w").write("' FrameForge silent launcher - v0.7.6\nOption Explicit\n")
    fa._write_hidden_launcher()
    assert fa._parse_launcher_target(vbs)[1] == "0.8.0"
    print("5. migrazione vbs legacy OK")

    # launch_secure_gui: firma con allow_elevation presente e default True
    import inspect
    sig = inspect.signature(fa.launch_secure_gui)
    assert "allow_elevation" in sig.parameters
    assert sig.parameters["allow_elevation"].default is True
    print("6. firma launch_secure_gui(allow_elevation) OK")

    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "forgefps_agent.py")).read()
    assert 'launch_secure_gui(mode=_args.mode, allow_elevation=not _args.uri)' in src
    assert 'launch_secure_gui(mode="optimize", allow_elevation=not _args.uri)' in src
    assert src.count('"runas"') == 1, "runas deve esistere SOLO dentro launch_secure_gui"
    print("7. call-site URI senza elevazione OK (runas unico e gated)")

    print("\nALL PASS")


if __name__ == "__main__":
    main()
