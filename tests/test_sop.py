from git_cg.sop import load_sop


def test_load_sop_success():
    # The default behavior should successfully load the bundled SOP matrix
    sop_data = load_sop()

    assert isinstance(sop_data, dict)
    assert "gitmoji_reference_matrix" in sop_data

    matrix = sop_data["gitmoji_reference_matrix"]
    assert isinstance(matrix, list)
    assert len(matrix) > 0

    # Check that rows have standard keys
    first_row = matrix[0]
    assert "intent_id" in first_row or "code" in first_row
    assert "emoji" in first_row
    assert "description" in first_row


def test_load_sop_invalid_path(monkeypatch):
    # Simulate user setting an invalid SOP path in the environment
    monkeypatch.setenv("GIT_CG_SOP_PATH", "/path/to/nonexistent/sop.json")

    # Should fall back to repo config or packaged data without crashing
    sop_data = load_sop()
    assert isinstance(sop_data, dict)
    # It should still load the standard matrix
    assert "gitmoji_reference_matrix" in sop_data
