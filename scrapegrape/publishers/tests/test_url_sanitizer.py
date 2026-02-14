from publishers.url_sanitizer import sanitize_url, extract_domain


class TestSanitizeUrl:
    def test_strips_www(self):
        result = sanitize_url("https://www.example.com/page")
        assert result == "https://example.com/page"

    def test_bare_domain_matches_www(self):
        www_result = sanitize_url("https://www.example.com/page")
        bare_result = sanitize_url("https://example.com/page")
        assert www_result == bare_result

    def test_strips_fragments(self):
        result = sanitize_url("https://example.com/page#section")
        assert result == "https://example.com/page"

    def test_sorts_query_params(self):
        result = sanitize_url("https://example.com/page?z=1&a=2")
        assert result == "https://example.com/page?a=2&z=1"

    def test_strips_utm_params(self):
        result = sanitize_url(
            "https://example.com/page?utm_source=fb&utm_medium=social&id=1"
        )
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=1" in result

    def test_strips_fbclid(self):
        result = sanitize_url(
            "https://example.com/page?fbclid=abc123&id=1"
        )
        assert "fbclid" not in result
        assert "id=1" in result

    def test_strips_gclid(self):
        result = sanitize_url("https://example.com/page?gclid=xyz789")
        assert "gclid" not in result

    def test_lowercase_hostname(self):
        result = sanitize_url("https://EXAMPLE.COM/page")
        assert "example.com" in result

    def test_preserves_trailing_slash(self):
        result = sanitize_url("https://example.com/page/")
        assert result.endswith("/page/")

    def test_normalizes_http_to_https(self):
        result = sanitize_url("http://example.com/page")
        assert result.startswith("https://")

    def test_preserves_non_tracking_query_params(self):
        result = sanitize_url("https://example.com/search?q=test&page=2")
        assert "q=test" in result
        assert "page=2" in result

    def test_unicode_url(self):
        result = sanitize_url("https://example.com/path/%E4%B8%AD%E6%96%87")
        assert "example.com" in result

    def test_mixed_case_scheme(self):
        result = sanitize_url("HTTP://example.com/page")
        assert result.startswith("https://")

    def test_strips_all_utm_variants(self):
        result = sanitize_url(
            "https://example.com/page?utm_term=a&utm_content=b&utm_campaign=c"
        )
        assert "utm_term" not in result
        assert "utm_content" not in result
        assert "utm_campaign" not in result

    def test_empty_query_after_stripping(self):
        result = sanitize_url(
            "https://example.com/page?utm_source=fb&utm_medium=social"
        )
        assert "?" not in result


class TestExtractDomain:
    def test_extracts_domain(self):
        result = extract_domain("https://www.nytimes.com/article/123")
        assert result == "nytimes.com"

    def test_strips_www_from_domain(self):
        result = extract_domain("https://www.bbc.co.uk/news")
        assert result == "bbc.co.uk"

    def test_extracts_domain_from_http(self):
        result = extract_domain("http://example.com/page")
        assert result == "example.com"

    def test_extracts_subdomain(self):
        result = extract_domain("https://blog.example.com/post")
        assert result == "blog.example.com"
