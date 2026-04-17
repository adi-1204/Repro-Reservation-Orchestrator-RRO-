"""
mock_api_server.py
------------------
A local Flask server that mimics the Bugzilla REST API used by the real system.
External users run this server so that bug_info.py --mock makes real HTTP calls
to a local endpoint, exercising the full integration path.
 
Endpoints (mirrors the real Bugzilla REST API structure):
  GET  /rest/login?login=<user>&password=<pass>  -> returns a mock token
  GET  /rest/bug?token=<token>&version=<version> -> returns bug list from mock_bugs.json
 
Usage:
  python3 mock_api_server.py            # starts on http://localhost:5000
  python3 mock_api_server.py --port 8080
 
Then in another terminal:
  python3 bug_info.py 3.3.1.648 engineer.txt --mock
"""
 
import argparse
import json
import os
from flask import Flask, jsonify, request
 
app = Flask(__name__)
 
# Path to mock data file (same directory as this script)
MOCK_BUGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_bugs.json")
 
 
def load_mock_bugs():
    with open(MOCK_BUGS_FILE, "r") as f:
        return json.load(f)
 
 
@app.route("/")
def health():
    return jsonify({"status": "mock API running", "endpoints": [
        "GET /rest/login?login=<user>&password=<pass>",
        "GET /rest/bug?token=<token>&version=<version>",
        "GET /rest/bug/<bug_id>/comment?token=<token>"
    ]})
 
 
@app.route("/rest/login")
def login():
    """Mock login — accepts any credentials and returns a fake token."""
    return jsonify({"id": 1, "token": "mock-token-123"})
 
 
@app.route("/rest/bug")
def get_bugs():
    """
    Return bug list from mock_bugs.json.
    The 'version' query param is accepted but all mock bugs are returned
    regardless of version, so the full filter logic in bug_info.py is testable.
    """
    token = request.args.get("token", "")
    version = request.args.get("version", "")
 
    if not token:
        return jsonify({"error": "Missing token. Call /rest/login first."}), 401
 
    try:
        bugs = load_mock_bugs()
    except FileNotFoundError:
        return jsonify({"error": f"mock_bugs.json not found at {MOCK_BUGS_FILE}"}), 500
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid mock_bugs.json: {str(e)}"}), 500
 
    print(f"[mock API] GET /rest/bug  version={version!r}  returning {len(bugs)} bugs")
    return jsonify(bugs)
 
 
@app.route("/rest/bug/<bug_id>/comment")
def get_bug_comments(bug_id):
    """
    Return mock comments for a given bug ID in the Bugzilla REST API format.
    GET /rest/bug/<bug_id>/comment?token=<token>
    """
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "Missing token. Call /rest/login first."}), 401
 
    try:
        bugs = load_mock_bugs()
    except FileNotFoundError:
        return jsonify({"error": f"mock_bugs.json not found at {MOCK_BUGS_FILE}"}), 500
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid mock_bugs.json: {str(e)}"}), 500
 
    bug = next((b for b in bugs if str(b.get("Bug Id", "")) == str(bug_id)), None)
    if bug is None:
        return jsonify({"error": f"Bug {bug_id} not found"}), 404
 
    # Serve comments from mock_bugs.json if present
    if "Comments" in bug and isinstance(bug["Comments"], list):
        mock_comments = bug["Comments"]
    else:
        # Fallback: generate generic comments if the bug has no Comments array
        mock_comments = [
            {
                "id": 1,
                "creator": bug.get("Reporter", "reporter@hpe.com"),
                "creation_time": "2024-01-10T08:00:00Z",
                "text": (
                    f"Initial report: Observed issue in {bug.get('Component', 'component')} "
                    f"for {bug.get('Product', 'product')}. Needs immediate attention."
                )
            },
            {
                "id": 2,
                "creator": bug.get("Assignee", "assignee@hpe.com"),
                "creation_time": "2024-01-11T09:30:00Z",
                "text": (
                    f"Assigned and investigating. Status: {bug.get('Developer Progress', 'In Progress')}. "
                    "Will update after reproducing."
                )
            },
        ]
 
    print(f"[mock API] GET /rest/bug/{bug_id}/comment  returning {len(mock_comments)} comments")
    return jsonify({"bugs": {str(bug_id): {"comments": mock_comments}}})
 
 
# ---------------------------------------------------------------------------
# Mock ChatHPE endpoints (used when bug_info.py runs with --mock --analyze)
# ---------------------------------------------------------------------------
 
@app.route("/v2.8/sessionId_generator", methods=["GET"])
def chathpe_session_id():
    """Return a mock ChatHPE session ID in the same text format as the real API."""
    return "sessionId: mock-session-abc123", 200, {"Content-Type": "text/plain"}
 
 
@app.route("/v2.8/preferences", methods=["POST"])
def chathpe_preferences():
    """Accept and acknowledge mock preference settings."""
    return jsonify({"status": "ok", "message": "Preferences set (mock)."})
 
 
@app.route("/v2.8/call/chatlite", methods=["POST"])
def chathpe_chatlite():
    """
    Return a canned but structured mock analysis response.
    Parses the user_query from the request body to echo the bug ID.
    """
    import re as _re
    body = request.get_json(force=True, silent=True) or {}
    user_query = body.get("user_query", "")
 
    # Try to extract the bug ID from the prompt (e.g. "Bug 100001")
    bug_id_match = _re.search(r"Bug\s+(\d+)", user_query)
    bug_id = bug_id_match.group(1) if bug_id_match else "UNKNOWN"
 
    # Extract test name if present in the prompt for a more realistic mock
    test_match = _re.search(r"Test Name.*?:\s*(\S+)", user_query)
    test_name = test_match.group(1) if test_match else "N/A"
 
    analysis = (
        f"1. REPRO ACTIONS\n"
        f"   To reproduce Bug {bug_id}, use the `{test_name}` script on the original cluster. "
        f"Observe state transitions in the logs.\n\n"
        f"2. CONFIG CHANGES\n"
        f"   Set the number of nodes to ensure the cluster configuration matches "
        f"the original setup recorded in the metadata.\n\n"
        f"3. REPRO READINESS\n"
        f"   NOW. The failure signature is clear and logs indicate a timing issue. "
        f"No additional info is required.\n\n"
        f"SUMMARY\n"
        f"Bug {bug_id} shows a failure in `{test_name}`. Intermittent timing issue "
        f"correlated with high-load conditions."
    )
 
    print(f"[mock ChatHPE] POST /v2.8/call/chatlite  bug_id={bug_id}")
    return jsonify({"message": analysis})
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Bugzilla REST API server")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    args = parser.parse_args()
 
    print(f"Starting mock Bugzilla API on http://{args.host}:{args.port}")
    print(f"Serving data from: {MOCK_BUGS_FILE}")
    app.run(host=args.host, port=args.port, debug=False)