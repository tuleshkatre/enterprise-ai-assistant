from app.utils.sse import sse_data, sse_event


def test_sse_data_format():
    assert sse_data("chunk") == "data: chunk\n\n"


def test_sse_named_event_format():
    assert sse_event("done", "completed") == "event: done\ndata: completed\n\n"
