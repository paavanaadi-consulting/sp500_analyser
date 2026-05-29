from sp500_analyser.analyzer import parse_pct, parse_number, fv_get


class TestParsePct:
    def test_basic_percentage(self):
        assert parse_pct("5.25%") == 5.25

    def test_negative_percentage(self):
        assert parse_pct("-3.10%") == -3.10

    def test_no_percent_sign(self):
        assert parse_pct("2.5") == 2.5

    def test_none_input(self):
        assert parse_pct(None) is None

    def test_invalid_string(self):
        assert parse_pct("N/A") is None

    def test_zero(self):
        assert parse_pct("0%") == 0.0


class TestParseNumber:
    def test_integer(self):
        assert parse_number("1000") == 1000.0

    def test_with_commas(self):
        assert parse_number("1,234,567") == 1234567.0

    def test_with_percent(self):
        assert parse_number("5.5%") == 5.5

    def test_dash(self):
        assert parse_number("-") is None

    def test_none(self):
        assert parse_number(None) is None

    def test_negative(self):
        assert parse_number("-42.5") == -42.5

    def test_invalid(self):
        assert parse_number("N/A") is None


class TestFvGet:
    def test_canonical_key(self):
        data = {"Price": "185.50"}
        assert fv_get(data, "Price") == "185.50"

    def test_alias_lookup(self):
        data = {"market_cap": "2.9T"}
        assert fv_get(data, "Market Cap") == "2.9T"

    def test_missing_key_default(self):
        assert fv_get({}, "Price") is None
        assert fv_get({}, "Price", "N/A") == "N/A"

    def test_unknown_canonical_key(self):
        data = {"SomeKey": "val"}
        assert fv_get(data, "SomeKey") == "val"
