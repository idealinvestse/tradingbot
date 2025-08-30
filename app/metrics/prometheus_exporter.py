"""Prometheus metrics exporter for Grafana dashboards."""


from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("prometheus_exporter")


# Define Prometheus metrics
TRADES_COUNTER = Counter(
    "trading_bot_trades_total", "Total number of trades", ["strategy", "exchange", "result"]
)
PROFIT_GAUGE = Gauge("trading_bot_profit_total", "Total profit/loss", ["strategy", "exchange"])
POSITION_GAUGE = Gauge(
    "trading_bot_positions_open", "Number of open positions", ["strategy", "exchange"]
)
LATENCY_HISTOGRAM = Histogram("trading_bot_latency_seconds", "Operation latency", ["operation"])
ERROR_COUNTER = Counter("trading_bot_errors_total", "Total errors", ["error_type", "strategy"])
BACKTEST_SUMMARY = Summary("trading_bot_backtest_duration", "Backtest execution time", ["strategy"])
RISK_GAUGE = Gauge("trading_bot_risk_metrics", "Risk metrics", ["metric_type"])
API_REQUESTS = Counter(
    "trading_bot_api_requests", "API requests", ["exchange", "endpoint", "status"]
)


class MetricsExporter:
    """Export metrics to Prometheus."""

    def __init__(self, port: int = 8000):
        """Initialize metrics exporter."""
        self.port = port
        self.started = False

    def start(self):
        """Start Prometheus HTTP server."""
        if not self.started:
            start_http_server(self.port)
            self.started = True
            logger.info(f"Prometheus metrics server started on port {self.port}")

    def record_trade(self, strategy: str, exchange: str, result: str, profit: float):
        """Record trade metrics."""
        TRADES_COUNTER.labels(strategy=strategy, exchange=exchange, result=result).inc()
        PROFIT_GAUGE.labels(strategy=strategy, exchange=exchange).set(profit)

    def update_positions(self, strategy: str, exchange: str, count: int):
        """Update open positions count."""
        POSITION_GAUGE.labels(strategy=strategy, exchange=exchange).set(count)

    def record_latency(self, operation: str, duration: float):
        """Record operation latency."""
        LATENCY_HISTOGRAM.labels(operation=operation).observe(duration)

    def record_error(self, error_type: str, strategy: str):
        """Record error occurrence."""
        ERROR_COUNTER.labels(error_type=error_type, strategy=strategy).inc()

    def record_backtest(self, strategy: str, duration: float):
        """Record backtest execution."""
        BACKTEST_SUMMARY.labels(strategy=strategy).observe(duration)

    def update_risk_metrics(self, metrics: dict[str, float]):
        """Update risk metrics."""
        for metric_name, value in metrics.items():
            RISK_GAUGE.labels(metric_type=metric_name).set(value)

    def record_api_request(self, exchange: str, endpoint: str, status: str):
        """Record API request."""
        API_REQUESTS.labels(exchange=exchange, endpoint=endpoint, status=status).inc()


class GrafanaDashboard(BaseModel):
    """Grafana dashboard configuration."""

    name: str = "Trading Bot Monitor"
    uid: str = "trading-bot"
    refresh: str = "5s"
    time_from: str = "now-6h"
    time_to: str = "now"

    def generate_config(self) -> dict:
        """Generate Grafana dashboard JSON config."""
        return {
            "dashboard": {
                "title": self.name,
                "uid": self.uid,
                "refresh": self.refresh,
                "time": {"from": self.time_from, "to": self.time_to},
                "panels": [
                    self._profit_panel(),
                    self._trades_panel(),
                    self._positions_panel(),
                    self._latency_panel(),
                    self._errors_panel(),
                    self._risk_panel(),
                ],
            }
        }

    def _profit_panel(self) -> dict:
        """Profit/Loss panel configuration."""
        return {
            "title": "Profit/Loss",
            "type": "graph",
            "targets": [{"expr": "trading_bot_profit_total", "legendFormat": "{{strategy}}"}],
        }

    def _trades_panel(self) -> dict:
        """Trades counter panel."""
        return {
            "title": "Trade Count",
            "type": "stat",
            "targets": [
                {"expr": "sum(rate(trading_bot_trades_total[5m]))", "legendFormat": "Trades/min"}
            ],
        }

    def _positions_panel(self) -> dict:
        """Open positions panel."""
        return {
            "title": "Open Positions",
            "type": "gauge",
            "targets": [{"expr": "sum(trading_bot_positions_open)", "legendFormat": "Positions"}],
        }

    def _latency_panel(self) -> dict:
        """Latency histogram panel."""
        return {
            "title": "Operation Latency",
            "type": "heatmap",
            "targets": [
                {
                    "expr": "histogram_quantile(0.95, trading_bot_latency_seconds_bucket)",
                    "legendFormat": "P95 Latency",
                }
            ],
        }

    def _errors_panel(self) -> dict:
        """Error rate panel."""
        return {
            "title": "Error Rate",
            "type": "graph",
            "targets": [
                {"expr": "rate(trading_bot_errors_total[5m])", "legendFormat": "{{error_type}}"}
            ],
        }

    def _risk_panel(self) -> dict:
        """Risk metrics panel."""
        return {
            "title": "Risk Metrics",
            "type": "table",
            "targets": [{"expr": "trading_bot_risk_metrics", "format": "table"}],
        }
