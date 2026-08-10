"""
Currency Plugin
===============
Manifest  : Currency exchange rates and conversion
Auth      : Optional API Key (Frankfurter is free, no key needed)
Triggers  : Exchange Rate Change, Rate Threshold Alert
Actions   : Get Exchange Rate, Convert Currency, Get Historical Rates,
            Get Supported Currencies, Get Rate Trend
Icon      : 💱
Version   : 1.0.0
"""
from __future__ import annotations

from typing import Any, Dict, List

from plugins.sdk import (
    BasePlugin, PluginManifest, AuthConfig, AuthType,
    TriggerSpec, TriggerType, TriggerOutputField,
    ActionSpec, ActionInputField,
    ConfigField, FieldType,
    Permission, PermissionScope,
    PluginContext, ActionResult, TriggerEvent,
    NoAuthProvider,
    action, trigger,
)

_FRANKFURTER = "https://api.frankfurter.app"


class Plugin(BasePlugin):
    """Currency exchange rate plugin using Frankfurter (free, no API key)."""

    manifest = PluginManifest(
        id          = "currency",
        name        = "Currency Exchange",
        version     = "1.0.0",
        description = "Get live and historical currency exchange rates. Convert amounts, track rate movements, and trigger alerts when thresholds are crossed.",
        author      = "Automation Platform Team",
        homepage    = "https://frankfurter.app",
        docs_url    = "https://docs.automation.platform/plugins/currency",
        license     = "MIT",
        icon        = "💱",
        icon_bg     = "#F59E0B",
        color       = "#F59E0B",
        categories  = ["Finance", "Data"],
        tags        = ["currency", "forex", "exchange-rate", "finance", "conversion"],

        auth = AuthConfig(
            type        = AuthType.NONE,
            label       = "No authentication required",
            help_text   = "Uses Frankfurter API (ECB data, free, no key needed).",
        ),

        triggers = [
            TriggerSpec(
                id          = "rate_threshold",
                name        = "Exchange Rate Threshold Alert",
                description = "Fires when an exchange rate crosses a configured threshold.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 3600,
                icon        = "📊",
                output_fields = [
                    TriggerOutputField("from_currency", "string", "Base currency code"),
                    TriggerOutputField("to_currency",   "string", "Target currency code"),
                    TriggerOutputField("rate",          "number", "Current exchange rate"),
                    TriggerOutputField("threshold",     "number", "Configured threshold"),
                    TriggerOutputField("direction",     "string", "above | below"),
                ],
            ),
            TriggerSpec(
                id          = "daily_rate",
                name        = "Daily Rate Update",
                description = "Fires once per day with the latest exchange rates.",
                type        = TriggerType.CRON,
                icon        = "📅",
                output_fields = [
                    TriggerOutputField("base_currency", "string", "Base currency"),
                    TriggerOutputField("date",          "string", "Rate date"),
                    TriggerOutputField("rates",         "object", "All available rates"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "get_rate",
                name        = "Get Exchange Rate",
                description = "Get the current exchange rate between two currencies.",
                icon        = "💹",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("from_currency", "string", "Source currency code (e.g. USD)", required=True, default="USD"),
                    ActionInputField("to_currency",   "string", "Target currency code (e.g. EUR)", required=True, default="EUR"),
                ],
                output_fields = [
                    TriggerOutputField("rate",          "number", "Exchange rate (1 from = ? to)"),
                    TriggerOutputField("from_currency", "string", "Base currency"),
                    TriggerOutputField("to_currency",   "string", "Target currency"),
                    TriggerOutputField("date",          "string", "Rate date"),
                ],
            ),
            ActionSpec(
                id          = "convert",
                name        = "Convert Currency",
                description = "Convert an amount from one currency to another.",
                icon        = "🔄",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("amount",        "number", "Amount to convert",          required=True),
                    ActionInputField("from_currency", "string", "Source currency (e.g. USD)", required=True),
                    ActionInputField("to_currency",   "string", "Target currency (e.g. EUR)", required=True),
                ],
                output_fields = [
                    TriggerOutputField("amount",          "number", "Original amount"),
                    TriggerOutputField("converted_amount","number", "Converted amount"),
                    TriggerOutputField("rate",            "number", "Exchange rate applied"),
                    TriggerOutputField("from_currency",   "string", "Source currency"),
                    TriggerOutputField("to_currency",     "string", "Target currency"),
                    TriggerOutputField("date",            "string", "Rate date"),
                ],
            ),
            ActionSpec(
                id          = "get_historical_rates",
                name        = "Get Historical Rates",
                description = "Get exchange rates for a specific past date.",
                icon        = "📅",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("date",          "string", "Date in YYYY-MM-DD format",    required=True),
                    ActionInputField("from_currency", "string", "Base currency (default: EUR)", required=False, default="EUR"),
                    ActionInputField("to_currencies", "array",  "List of target currencies",    required=False),
                ],
                output_fields = [
                    TriggerOutputField("date",          "string", "Rate date"),
                    TriggerOutputField("base_currency", "string", "Base currency"),
                    TriggerOutputField("rates",         "object", "Currency → rate mapping"),
                ],
            ),
            ActionSpec(
                id          = "get_rate_trend",
                name        = "Get Rate Trend",
                description = "Get exchange rate trend over a date range.",
                icon        = "📈",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("from_currency", "string", "Base currency",                    required=True, default="USD"),
                    ActionInputField("to_currency",   "string", "Target currency",                  required=True, default="EUR"),
                    ActionInputField("start_date",    "string", "Start date YYYY-MM-DD",            required=True),
                    ActionInputField("end_date",      "string", "End date YYYY-MM-DD (default: today)", required=False),
                ],
                output_fields = [
                    TriggerOutputField("dates",       "array",  "List of dates"),
                    TriggerOutputField("rates",       "array",  "Corresponding rate values"),
                    TriggerOutputField("min_rate",    "number", "Minimum rate in period"),
                    TriggerOutputField("max_rate",    "number", "Maximum rate in period"),
                    TriggerOutputField("avg_rate",    "number", "Average rate in period"),
                    TriggerOutputField("change_pct",  "number", "% change from start to end"),
                ],
            ),
            ActionSpec(
                id          = "get_currencies",
                name        = "List Supported Currencies",
                description = "Get all currencies supported by the exchange API.",
                icon        = "📋",
                idempotent  = True,
                readonly    = True,
                input_fields = [],
                output_fields = [
                    TriggerOutputField("currencies", "object", "Currency code → full name mapping"),
                    TriggerOutputField("count",      "number", "Total number of currencies"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "default_base",
                label       = "Default Base Currency",
                type        = FieldType.STRING,
                required    = False,
                default     = "USD",
                placeholder = "USD",
            ),
            ConfigField(
                name        = "alert_currency_pair",
                label       = "Alert Currency Pair",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "USD/EUR",
                help_text   = "Currency pair to watch for threshold triggers (e.g. USD/EUR).",
            ),
            ConfigField(
                name        = "alert_threshold_high",
                label       = "Alert Threshold (High)",
                type        = FieldType.NUMBER,
                required    = False,
            ),
            ConfigField(
                name        = "alert_threshold_low",
                label       = "Alert Threshold (Low)",
                type        = FieldType.NUMBER,
                required    = False,
            ),
        ],

        permissions = [
            Permission(PermissionScope.READ, "exchange_rates", "Fetch currency exchange rate data"),
        ],
    )

    def get_auth_provider(self):
        return NoAuthProvider()

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        dispatch = {
            "get_rate":             self._get_rate,
            "convert":              self._convert,
            "get_historical_rates": self._get_historical_rates,
            "get_rate_trend":       self._get_rate_trend,
            "get_currencies":       self._get_currencies,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="get_rate", name="Get Exchange Rate", icon="💹", idempotent=True)
    def _get_rate(self, ctx: PluginContext, params: Dict) -> ActionResult:
        frm  = params["from_currency"].upper()
        to   = params["to_currency"].upper()
        ctx.info(f"Fetching exchange rate {frm} → {to}")
        if ctx.dry_run:
            return ActionResult.ok(data={"rate": 0.92, "from_currency": frm, "to_currency": to, "date": "2026-08-05"})
        result = ctx.http_get(f"{_FRANKFURTER}/latest", params={"from": frm, "to": to})
        rate   = result.get("rates", {}).get(to)
        return ActionResult.ok(data={"rate": rate, "from_currency": frm, "to_currency": to, "date": result.get("date")})

    @action(id="convert", name="Convert Currency", icon="🔄", idempotent=True)
    def _convert(self, ctx: PluginContext, params: Dict) -> ActionResult:
        amount = float(params["amount"])
        frm    = params["from_currency"].upper()
        to     = params["to_currency"].upper()
        ctx.info(f"Converting {amount} {frm} → {to}")
        if ctx.dry_run:
            return ActionResult.ok(data={"amount": amount, "converted_amount": round(amount * 0.92, 4), "rate": 0.92, "from_currency": frm, "to_currency": to, "date": "2026-08-05"})
        result   = ctx.http_get(f"{_FRANKFURTER}/latest", params={"from": frm, "to": to, "amount": amount})
        rate     = result.get("rates", {}).get(to, 0)
        converted= result.get("rates", {}).get(to, amount)
        return ActionResult.ok(data={"amount": amount, "converted_amount": round(converted, 4), "rate": rate, "from_currency": frm, "to_currency": to, "date": result.get("date")})

    @action(id="get_historical_rates", name="Get Historical Rates", icon="📅", idempotent=True)
    def _get_historical_rates(self, ctx: PluginContext, params: Dict) -> ActionResult:
        date = params["date"]
        frm  = params.get("from_currency", "EUR").upper()
        ctx.info(f"Fetching historical rates on {date} (base: {frm})")
        if ctx.dry_run:
            return ActionResult.ok(data={"date": date, "base_currency": frm, "rates": {"USD": 1.08, "GBP": 0.86, "JPY": 157.23}})
        qp: Dict[str, Any] = {"from": frm}
        if params.get("to_currencies"):
            qp["to"] = ",".join([c.upper() for c in params["to_currencies"]])
        result = ctx.http_get(f"{_FRANKFURTER}/{date}", params=qp)
        return ActionResult.ok(data={"date": result.get("date"), "base_currency": frm, "rates": result.get("rates", {})})

    @action(id="get_rate_trend", name="Get Rate Trend", icon="📈", idempotent=True)
    def _get_rate_trend(self, ctx: PluginContext, params: Dict) -> ActionResult:
        frm   = params["from_currency"].upper()
        to    = params["to_currency"].upper()
        start = params["start_date"]
        end   = params.get("end_date", "")
        ctx.info(f"Fetching rate trend {frm}/{to} from {start}")
        if ctx.dry_run:
            rates = [0.90 + i * 0.002 for i in range(7)]
            return ActionResult.ok(data={"dates": [f"2026-08-0{i+1}" for i in range(7)], "rates": rates, "min_rate": min(rates), "max_rate": max(rates), "avg_rate": sum(rates)/len(rates), "change_pct": 1.4})
        period = f"{start}..{end}" if end else f"{start}.."
        result = ctx.http_get(f"{_FRANKFURTER}/{period}", params={"from": frm, "to": to})
        series = result.get("rates", {})
        dates  = sorted(series.keys())
        rates  = [series[d].get(to, 0) for d in dates]
        if len(rates) >= 2:
            change_pct = round((rates[-1] - rates[0]) / rates[0] * 100, 4) if rates[0] else 0
        else:
            change_pct = 0
        return ActionResult.ok(data={
            "dates":      dates,
            "rates":      rates,
            "min_rate":   min(rates) if rates else None,
            "max_rate":   max(rates) if rates else None,
            "avg_rate":   round(sum(rates) / len(rates), 6) if rates else None,
            "change_pct": change_pct,
        })

    @action(id="get_currencies", name="List Currencies", icon="📋", idempotent=True)
    def _get_currencies(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info("Fetching supported currencies list")
        if ctx.dry_run:
            return ActionResult.ok(data={"currencies": {"USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound"}, "count": 3})
        result = ctx.http_get(f"{_FRANKFURTER}/currencies")
        return ActionResult.ok(data={"currencies": result, "count": len(result)})

    def on_test(self, ctx: PluginContext) -> ActionResult:
        return self.execute_action("get_rate", ctx, {"from_currency": "USD", "to_currency": "EUR"})
