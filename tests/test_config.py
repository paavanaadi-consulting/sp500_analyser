from sp500_analyser import config


class TestConfigDefaults:
    def test_lookback_days_positive(self):
        assert config.LOOKBACK_DAYS > 0

    def test_ema200_band_valid(self):
        assert config.EMA200_NEAR_PCT_MIN < config.EMA200_NEAR_PCT_MAX
        assert config.EMA200_NEAR_PCT_MIN >= 0

    def test_polygon_period_default(self):
        assert config.POLYGON_EMA200_PERIOD == 200

    def test_output_dir_is_string(self):
        assert isinstance(config.OUTPUT_DIR, str)

    def test_output_dir_ends_with_sp500_output(self):
        assert config.OUTPUT_DIR.endswith("sp500_output")
