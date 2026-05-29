from unittest.mock import patch

import pytest

from sp500_analyser.analyzer import (
    compute_ema,
    score_emerging_trend,
    classify_ema_position,
    is_near_ema200_daily,
    filter_near_ema200_daily,
    compute_ema_proximity,
    ema200_from_polygon,
    compute_price_trend,
    generate_coworker_summary,
    analyze_all,
)


class TestComputeEma:
    def test_exact_period_returns_sma(self):
        closes = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = compute_ema(closes, 5)
        assert result == 12.0

    def test_insufficient_data(self):
        assert compute_ema([10.0, 11.0], 5) is None

    def test_known_ema_value(self):
        closes = [22.0, 22.5, 22.3, 22.8, 23.0, 23.2, 23.5]
        result = compute_ema(closes, 5)
        assert result is not None
        assert 22.0 <= result <= 23.5

    def test_single_period(self):
        closes = [42.0]
        result = compute_ema(closes, 1)
        assert result == 42.0

    def test_constant_series(self):
        closes = [100.0] * 20
        result = compute_ema(closes, 10)
        assert result == 100.0

    def test_empty_list(self):
        assert compute_ema([], 5) is None


class TestIsNearEma200Daily:
    @patch("sp500_analyser.analyzer.config")
    def test_within_band(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        assert is_near_ema200_daily(5.0) is True
        assert is_near_ema200_daily(-7.5) is True
        assert is_near_ema200_daily(0.5) is True

    @patch("sp500_analyser.analyzer.config")
    def test_outside_band(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        assert is_near_ema200_daily(15.0) is False
        assert is_near_ema200_daily(-11.0) is False

    def test_none_input(self):
        assert is_near_ema200_daily(None) is False

    @patch("sp500_analyser.analyzer.config")
    def test_boundary_values(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        assert is_near_ema200_daily(0.0) is True
        assert is_near_ema200_daily(10.0) is True
        assert is_near_ema200_daily(-10.0) is True


class TestClassifyEmaPosition:
    def test_unknown_when_no_data(self):
        assert classify_ema_position({}) == "unknown"

    def test_converging(self):
        result = classify_ema_position({
            "EMA20_pct_from_price": 1.0,
            "EMA50_pct_from_price": 1.5,
        })
        assert result == "converging_near_ema20_ema50"

    def test_near_ema20_only(self):
        result = classify_ema_position({
            "EMA20_pct_from_price": 1.0,
            "EMA50_pct_from_price": 10.0,
        })
        assert result == "near_ema20"

    def test_near_ema50_only(self):
        result = classify_ema_position({
            "EMA20_pct_from_price": 5.0,
            "EMA50_pct_from_price": 1.5,
        })
        assert result == "near_ema50"

    @patch("sp500_analyser.analyzer.config")
    def test_near_ema200(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        result = classify_ema_position({
            "EMA20_pct_from_price": 5.0,
            "EMA50_pct_from_price": 5.0,
            "EMA200_pct_from_price": 2.5,
        })
        assert result == "near_ema200_daily"

    def test_above_all(self):
        result = classify_ema_position({
            "EMA20_pct_from_price": 5.0,
            "EMA50_pct_from_price": 8.0,
            "EMA200_pct_from_price": 15.0,
        })
        assert result == "above_all_emas"

    def test_below_key_emas(self):
        result = classify_ema_position({
            "EMA20_pct_from_price": -5.0,
            "EMA50_pct_from_price": -8.0,
        })
        assert result == "below_key_emas"


class TestScoreEmergingTrend:
    @patch("sp500_analyser.analyzer.config")
    def test_baseline_score(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        score = score_emerging_trend({}, {}, {})
        assert score == 50.0

    @patch("sp500_analyser.analyzer.config")
    def test_high_score_bullish_setup(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        ema_data = {
            "EMA20_pct_from_price": 1.0,
            "EMA50_pct_from_price": 2.0,
            "EMA200_pct_from_price": 2.5,
        }
        trend_data = {
            "period_return_pct": 5.0,
            "consecutive_up_days": 4,
            "volume_trend_pct": 25.0,
        }
        finviz_data = {"RSI (14)": "45"}
        score = score_emerging_trend(ema_data, trend_data, finviz_data)
        assert score > 80

    @patch("sp500_analyser.analyzer.config")
    def test_low_score_bearish_setup(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        ema_data = {"EMA20_pct_from_price": -10.0}
        trend_data = {
            "period_return_pct": -8.0,
            "consecutive_up_days": 0,
            "volume_trend_pct": -5.0,
        }
        finviz_data = {"RSI (14)": "75"}
        score = score_emerging_trend(ema_data, trend_data, finviz_data)
        assert score < 50

    @patch("sp500_analyser.analyzer.config")
    def test_score_clamped_to_0_100(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        score = score_emerging_trend(
            {"EMA20_pct_from_price": -100},
            {"period_return_pct": -50, "consecutive_up_days": 0},
            {"RSI (14)": "90"},
        )
        assert 0 <= score <= 100

    @patch("sp500_analyser.analyzer.config")
    def test_rsi_oversold_bonus(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        base_score = score_emerging_trend({}, {}, {})
        rsi30_score = score_emerging_trend({}, {}, {"RSI (14)": "35"})
        assert rsi30_score > base_score


class TestEma200FromPolygon:
    @patch("sp500_analyser.analyzer.config")
    def test_with_sufficient_bars(self, mock_config, sample_polygon_entry):
        mock_config.POLYGON_EMA200_PERIOD = 200
        result = ema200_from_polygon(sample_polygon_entry)
        assert result is not None
        assert "ema200" in result
        assert "distance_pct" in result
        assert result["source"] == "polygon"
        assert result["bars_used"] == 220

    @patch("sp500_analyser.analyzer.config")
    def test_with_insufficient_bars(self, mock_config, sample_polygon_entry_short):
        mock_config.POLYGON_EMA200_PERIOD = 200
        result = ema200_from_polygon(sample_polygon_entry_short)
        assert result is None

    def test_with_none_input(self):
        assert ema200_from_polygon(None) is None

    def test_with_empty_results(self):
        assert ema200_from_polygon({"results": []}) is None


class TestComputePriceTrend:
    def test_basic_uptrend(self):
        entry = {
            "results": [
                {"close": 100, "volume": 1_000_000},
                {"close": 102, "volume": 1_100_000},
                {"close": 105, "volume": 1_200_000},
                {"close": 107, "volume": 1_300_000},
                {"close": 110, "volume": 1_500_000},
            ]
        }
        trend = compute_price_trend(entry)
        assert trend["period_return_pct"] == 10.0
        assert trend["up_days"] == 4
        assert trend["down_days"] == 0
        assert trend["consecutive_up_days"] == 4
        assert trend["num_bars"] == 5

    def test_empty_bars(self):
        assert compute_price_trend({"results": []}) == {}

    def test_single_bar(self):
        assert compute_price_trend({"results": [{"close": 100, "volume": 1000}]}) == {}

    def test_downtrend(self):
        entry = {
            "results": [
                {"close": 110, "volume": 1_000_000},
                {"close": 108, "volume": 1_100_000},
                {"close": 105, "volume": 900_000},
            ]
        }
        trend = compute_price_trend(entry)
        assert trend["period_return_pct"] < 0
        assert trend["down_days"] == 2
        assert trend["consecutive_up_days"] == 0


class TestFilterNearEma200Daily:
    def test_filters_correctly(self):
        analyzed = [
            {"ticker": "A", "near_ema200_daily": True, "ema_proximity": {"EMA200_abs_distance_pct": 2.5}},
            {"ticker": "B", "near_ema200_daily": False, "ema_proximity": {}},
            {"ticker": "C", "near_ema200_daily": True, "ema_proximity": {"EMA200_abs_distance_pct": 2.1}},
        ]
        result = filter_near_ema200_daily(analyzed)
        assert len(result) == 2
        assert result[0]["ticker"] == "C"
        assert result[1]["ticker"] == "A"

    def test_empty_input(self):
        assert filter_near_ema200_daily([]) == []


class TestComputeEmaProximity:
    def test_with_ema_values(self, sample_finviz_entry):
        result = compute_ema_proximity(sample_finviz_entry)
        assert "EMA20_pct_from_price" in result
        assert "EMA200_pct_from_price" in result

    def test_with_no_price(self):
        assert compute_ema_proximity({}) == {}

    def test_with_zero_price(self):
        assert compute_ema_proximity({"Price": "0"}) == {}


class TestGenerateCoworkerSummary:
    @patch("sp500_analyser.analyzer.config")
    def test_summary_structure(self, mock_config):
        mock_config.LOOKBACK_DAYS = 10
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        mock_config.POLYGON_EMA200_PERIOD = 200
        mock_config.POLYGON_EMA200_LOOKBACK_DAYS = 320

        analyzed = [
            {
                "ticker": "AAPL",
                "company": "Apple",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "price": 185.0,
                "ema_position": "above_all_emas",
                "near_ema200_daily": False,
                "ema200_distance_pct": 10.0,
                "ema200_source": "polygon",
                "ema_proximity": {},
                "trend": {"period_return_pct": 3.0},
                "technicals": {"rsi_14": "55", "ema200": 168.0, "sma200": 165.0},
                "fundamentals": {},
                "performance": {},
                "analyst": {},
                "emerging_trend_score": 72.0,
            }
        ]
        summary = generate_coworker_summary(analyzed)
        assert "metadata" in summary
        assert "executive_summary" in summary
        assert "stocks_near_ema200_daily" in summary
        assert "sector_heatmap" in summary
        assert "all_stocks_ranked" in summary
        assert summary["metadata"]["total_stocks_analyzed"] == 1


class TestAnalyzeAll:
    @patch("sp500_analyser.analyzer.config")
    def test_merges_polygon_and_finviz(self, mock_config):
        mock_config.POLYGON_EMA200_PERIOD = 200
        mock_config.POLYGON_EMA200_LOOKBACK_DAYS = 320
        mock_config.LOOKBACK_DAYS = 10
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0

        finviz = [{"ticker": "AAPL", "Price": "185", "RSI (14)": "55"}]
        polygon = [
            {
                "ticker": "AAPL",
                "results": [
                    {
                        "date": f"2025-01-{i + 1:02d}",
                        "close": 180 + i * 0.1,
                        "volume": 50_000_000,
                        "open": 180,
                        "high": 182,
                        "low": 179,
                    }
                    for i in range(10)
                ],
            }
        ]
        result = analyze_all(polygon, finviz)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert "emerging_trend_score" in result[0]

    @patch("sp500_analyser.analyzer.config")
    def test_handles_ticker_only_in_one_source(self, mock_config):
        mock_config.POLYGON_EMA200_PERIOD = 200
        mock_config.POLYGON_EMA200_LOOKBACK_DAYS = 320
        mock_config.LOOKBACK_DAYS = 10
        mock_config.EMA200_NEAR_PCT_MIN = 0.0
        mock_config.EMA200_NEAR_PCT_MAX = 10.0

        finviz = [{"ticker": "AAPL", "Price": "185"}]
        polygon = [{"ticker": "MSFT", "results": []}]
        result = analyze_all(polygon, finviz)
        tickers = [r["ticker"] for r in result]
        assert "AAPL" in tickers
        assert "MSFT" in tickers
