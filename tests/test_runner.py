# tests/test_runner.py
def test_runner_importable():
    from agents.runner import run_research_agent, run_general_agent
    assert callable(run_research_agent)
    assert callable(run_general_agent)
