from src.hello import greet


def test_greet():
    assert greet("ci") == "hello, ci"
