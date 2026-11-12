from devfest_agents.tools.news_toolset import NewsToolset


async def test_unreachable_server_means_no_tools_then_a_back_off():
    news = NewsToolset("http://127.0.0.1:9/mcp", connect_timeout=1.0, list_timeout_s=5.0)
    assert await news.get_tools() == []
    assert news.last_error is not None and not news.available
    assert await news.get_tools() == []  # backing off: returns at once, no new connection
    await news.shutdown()
