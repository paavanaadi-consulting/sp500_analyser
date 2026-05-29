from unittest.mock import patch

from sp500_analyser.daily_alert import (
    analyse,
    format_alert_text,
    _bucket_label,
    _side,
    _market_breadth,
    _extract_ema200_stocks,
)


class TestBucketLabel:
    def test_close(self):
        assert _bucket_label(1.5) == "0-2%"
        assert _bucket_label(-0.3) == "0-2%"

    def test_mid(self):
        assert _bucket_label(3.0) == "2-5%"
        assert _bucket_label(-4.9) == "2-5%"

    def test_far(self):
        assert _bucket_label(7.0) == "5-10%"
        assert _bucket_label(-9.5) == "5-10%"


class TestSide:
    def test_above(self):
        assert _side(5.0) == "above"

    def test_below(self):
        assert _side(-3.0) == "below"

    def test_at(self):
        assert _side(0.0) == "at"

    def test_none(self):
        assert _side(None) == "unknown"


class TestMarketBreadth:
    def test_empty(self):
        assert _market_breadth([]) == {}

    def test_basic(self):
        ranked = [
            {"trend_score": 80},
            {"trend_score": 60},
            {"trend_score": 30},
            {"trend_score": 75},
        ]
        result = _market_breadth(ranked)
        assert result["avg_trend_score"] == 61.2
        assert result["stocks_score_above_70"] == 2
        assert result["stocks_score_below_40"] == 1
        assert result["breadth_pct"] == 50.0


class TestExtractEma200Stocks:
    @patch("sp500_analyser.daily_alert.config")
    def test_extracts_from_near_emas(self, mock_config):
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        near_emas = [
            {
                "ticker": "AAPL",
                "sector": "Technology",
                "ema_proximity": {"EMA200_pct_from_price": 5.0},
                "trend_score": 80,
            },
            {
                "ticker": "MSFT",
                "sector": "Technology",
                "ema_proximity": {"EMA200_pct_from_price": 15.0},
                "trend_score": 70,
            },
        ]
        result = _extract_ema200_stocks(near_emas, [])
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["ema200_distance_pct"] == 5.0


class TestAnalyse:
    @patch("sp500_analyser.daily_alert.config")
    def test_missing_file_returns_error(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        result = analyse(str(tmp_path))
        assert "error" in result

    @patch("sp500_analyser.daily_alert.config")
    def test_with_valid_data(self, mock_config, tmp_path):
        mock_config.OUTPUT_DIR = str(tmp_path)
        mock_config.EMA200_NEAR_PCT_MAX = 10.0
        summary = {
            "metadata": {"total_stocks_analyzed": 2, "generated_at": "2026-05-29T00:00:00"},
            "executive_summary": {"stocks_near_ema": 1, "top_emerging_count": 1},
            "stocks_near_ema200_daily": [],
            "stocks_near_emas": [
                {
                    "ticker": "AAPL",
                    "company": "Apple",
                    "sector": "Technology",
                    "price": 185.0,
                    "ema_position": "near_ema200_daily",
                    "ema_proximity": {"EMA200_pct_from_price": 3.0},
                    "trend_score": 80,
                    "rsi": 55,
                    "period_return": 2.0,
                    "volume_trend": 10.0,
                },
            ],
            "top_emerging_trends": [],
            "sector_heatmap": {},
            "all_stocks_ranked": [
                {"ticker": "AAPL", "trend_score": 80, "ema_position": "near_ema200_daily"},
                {"ticker": "MSFT", "trend_score": 60, "ema_position": "above_all_emas"},
            ],
        }
        (tmp_path / "coworker_summary.json").write_text(__import__("json").dumps(summary))

        result = analyse(str(tmp_path))
        assert result["total_sp500_analyzed"] == 2
        assert result["overview"]["stocks_within_ema200_band"] == 1
        assert result["overview"]["above_ema200"] == 1
        assert "market_breadth" in result


class TestFormatAlertText:
    def test_error_case(self):
        text = format_alert_text({"error": "file not found", "generated_at": "now"})
        assert "ERROR" in text

    def test_full_output(self):
        analysis = {
            "generated_at": "2026-05-29T12:00:00Z",
            "pipeline_generated_at": "2026-05-29T07:00:00",
            "total_sp500_analyzed": 503,
            "ema200_band": "0-10%",
            "overview": {
                "stocks_within_ema200_band": 50,
                "above_ema200": 30,
                "below_ema200": 20,
                "stocks_near_all_emas": 233,
                "top_emerging_count": 100,
            },
            "distance_distribution": {
                "0-2%": {"count": 10, "tickers": ["A", "B"]},
                "2-5%": {"count": 20, "tickers": ["C", "D"]},
            },
            "sector_breakdown": {
                "Technology": {"count": 15, "tickers": [{"ticker": "AAPL"}]},
            },
            "top_bullish_near_ema200": [
                {"ticker": "AAPL", "ema200_distance_pct": 3.0, "trend_score": 85, "rsi": 55, "sector": "Technology"},
            ],
            "top_bearish_recovery_candidates": [
                {"ticker": "XOM", "ema200_distance_pct": -4.0, "trend_score": 70, "rsi": 40, "sector": "Energy"},
            ],
            "market_breadth": {
                "avg_trend_score": 65.0,
                "stocks_score_above_70": 200,
                "stocks_score_below_40": 50,
                "breadth_pct": 39.8,
            },
        }
        text = format_alert_text(analysis)
        assert "SP500 EMA200 DAILY ALERT" in text
        assert "AAPL" in text
        assert "XOM" in text
        assert "Market Breadth" in text
        assert "Technology" in text
