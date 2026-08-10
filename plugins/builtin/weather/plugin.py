"""
Weather Plugin
==============
Manifest  : Weather data via Open-Meteo (free, no API key) + OpenWeatherMap
Auth      : Optional API Key (OpenWeatherMap)
Triggers  : Daily Forecast, Severe Weather Alert, Temperature Threshold
Actions   : Get Current Weather, Get Forecast, Get Air Quality,
            Get UV Index, Get Historical Weather
Icon      : ⛅
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
    ApiKeyProvider, NoAuthProvider,
    action, trigger,
)

_OPEN_METEO = "https://api.open-meteo.com/v1"
_OWM_BASE   = "https://api.openweathermap.org/data/2.5"

# WMO weather code descriptions
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Slight showers", 81: "Moderate showers",
    82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


class Plugin(BasePlugin):
    """Weather plugin — current conditions, forecasts, alerts."""

    manifest = PluginManifest(
        id          = "weather",
        name        = "Weather",
        version     = "1.0.0",
        description = "Get real-time weather data, forecasts, UV index, and air quality. Trigger workflows on severe weather events or temperature thresholds.",
        author      = "Automation Platform Team",
        homepage    = "https://open-meteo.com",
        docs_url    = "https://docs.automation.platform/plugins/weather",
        license     = "MIT",
        icon        = "⛅",
        icon_bg     = "#2196F3",
        color       = "#2196F3",
        categories  = ["Data", "IoT", "Monitoring"],
        tags        = ["weather", "forecast", "temperature", "climate", "alerts"],

        auth = AuthConfig(
            type        = AuthType.API_KEY,
            label       = "OpenWeatherMap API Key (optional)",
            api_key_env = "OPENWEATHERMAP_API_KEY",
            help_url    = "https://openweathermap.org/api",
            help_text   = "Open-Meteo (free, no key required). For OpenWeatherMap features, add an API key.",
            setup_steps = [
                "Basic weather works without any API key (Open-Meteo).",
                "For extended features: Register at openweathermap.org → Get API key",
                "Set OPENWEATHERMAP_API_KEY environment variable (optional)",
            ],
        ),

        triggers = [
            TriggerSpec(
                id          = "daily_forecast",
                name        = "Daily Forecast",
                description = "Fires once per day with the weather forecast for a city.",
                type        = TriggerType.CRON,
                icon        = "📅",
                output_fields = [
                    TriggerOutputField("city",             "string", "City name"),
                    TriggerOutputField("date",             "string", "Forecast date"),
                    TriggerOutputField("max_temp_c",       "number", "Max temperature °C"),
                    TriggerOutputField("min_temp_c",       "number", "Min temperature °C"),
                    TriggerOutputField("precipitation_mm", "number", "Expected precipitation mm"),
                    TriggerOutputField("weather_code",     "number", "WMO weather condition code"),
                    TriggerOutputField("description",      "string", "Human-readable weather description"),
                ],
            ),
            TriggerSpec(
                id          = "temperature_threshold",
                name        = "Temperature Threshold Alert",
                description = "Fires when temperature exceeds or drops below a configured threshold.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 3600,
                icon        = "🌡️",
                output_fields = [
                    TriggerOutputField("city",          "string", "City name"),
                    TriggerOutputField("temperature_c", "number", "Current temperature °C"),
                    TriggerOutputField("threshold_c",   "number", "Configured threshold"),
                    TriggerOutputField("direction",      "string", "above | below"),
                ],
            ),
            TriggerSpec(
                id          = "severe_alert",
                name        = "Severe Weather Alert",
                description = "Fires when a severe weather event (storm, heavy rain) is forecasted.",
                type        = TriggerType.POLLING,
                poll_interval_seconds = 1800,
                icon        = "⚠️",
                output_fields = [
                    TriggerOutputField("city",        "string", "City name"),
                    TriggerOutputField("alert_type",  "string", "Storm | Heavy Rain | Extreme Heat | Snow"),
                    TriggerOutputField("severity",    "string", "warning | watch | advisory"),
                    TriggerOutputField("description", "string", "Alert description"),
                    TriggerOutputField("valid_until", "string", "Alert expiry timestamp"),
                ],
            ),
        ],

        actions = [
            ActionSpec(
                id          = "get_current_weather",
                name        = "Get Current Weather",
                description = "Get current weather conditions for a city or coordinates.",
                icon        = "🌤️",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("city",      "string", "City name (e.g. London)",    required=False),
                    ActionInputField("latitude",  "number", "Latitude (overrides city)",  required=False),
                    ActionInputField("longitude", "number", "Longitude (overrides city)", required=False),
                    ActionInputField("units",     "string", "celsius | fahrenheit",        required=False, default="celsius"),
                ],
                output_fields = [
                    TriggerOutputField("city",           "string", "Resolved city name"),
                    TriggerOutputField("temperature_c",  "number", "Current temperature °C"),
                    TriggerOutputField("feels_like_c",   "number", "Feels-like temperature °C"),
                    TriggerOutputField("humidity_pct",   "number", "Relative humidity %"),
                    TriggerOutputField("wind_speed_kmh", "number", "Wind speed km/h"),
                    TriggerOutputField("weather_code",   "number", "WMO weather code"),
                    TriggerOutputField("description",    "string", "Weather description"),
                    TriggerOutputField("is_day",         "boolean","True if daytime"),
                ],
            ),
            ActionSpec(
                id          = "get_forecast",
                name        = "Get Weather Forecast",
                description = "Get a multi-day weather forecast (up to 16 days).",
                icon        = "📊",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("city",      "string", "City name",                  required=False),
                    ActionInputField("latitude",  "number", "Latitude",                   required=False),
                    ActionInputField("longitude", "number", "Longitude",                  required=False),
                    ActionInputField("days",      "number", "Number of forecast days 1–16",required=False, default=7),
                ],
                output_fields = [
                    TriggerOutputField("days",    "array",  "List of daily forecast objects"),
                    TriggerOutputField("city",    "string", "City name"),
                    TriggerOutputField("timezone","string", "Timezone of location"),
                ],
            ),
            ActionSpec(
                id          = "get_air_quality",
                name        = "Get Air Quality",
                description = "Get current air quality index and pollutant levels.",
                icon        = "💨",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("city",      "string", "City name", required=False),
                    ActionInputField("latitude",  "number", "Latitude",  required=False),
                    ActionInputField("longitude", "number", "Longitude", required=False),
                ],
                output_fields = [
                    TriggerOutputField("aqi",      "number", "Air Quality Index (US EPA)"),
                    TriggerOutputField("pm2_5",    "number", "PM2.5 µg/m³"),
                    TriggerOutputField("pm10",     "number", "PM10 µg/m³"),
                    TriggerOutputField("co",       "number", "Carbon Monoxide µg/m³"),
                    TriggerOutputField("category", "string", "Good | Moderate | Unhealthy | Hazardous"),
                ],
            ),
            ActionSpec(
                id          = "get_uv_index",
                name        = "Get UV Index",
                description = "Get current UV index for a location.",
                icon        = "☀️",
                idempotent  = True,
                readonly    = True,
                input_fields = [
                    ActionInputField("city",      "string", "City name", required=False),
                    ActionInputField("latitude",  "number", "Latitude",  required=False),
                    ActionInputField("longitude", "number", "Longitude", required=False),
                ],
                output_fields = [
                    TriggerOutputField("uv_index",  "number", "UV index value"),
                    TriggerOutputField("category",  "string", "Low | Moderate | High | Very High | Extreme"),
                ],
            ),
        ],

        config = [
            ConfigField(
                name        = "default_city",
                label       = "Default City",
                type        = FieldType.STRING,
                required    = False,
                placeholder = "London",
                help_text   = "City used when no city or coordinates are specified.",
            ),
            ConfigField(
                name        = "units",
                label       = "Temperature Units",
                type        = FieldType.SELECT,
                required    = False,
                default     = "celsius",
                options     = ["celsius", "fahrenheit"],
            ),
            ConfigField(
                name        = "alert_threshold_high_c",
                label       = "High Temperature Alert Threshold (°C)",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 35,
                help_text   = "Trigger 'temperature_threshold' when temperature exceeds this value.",
            ),
            ConfigField(
                name        = "alert_threshold_low_c",
                label       = "Low Temperature Alert Threshold (°C)",
                type        = FieldType.NUMBER,
                required    = False,
                default     = 0,
            ),
        ],

        permissions = [
            Permission(PermissionScope.READ, "weather_api", "Fetch weather data from Open-Meteo/OpenWeatherMap"),
        ],
    )

    def get_auth_provider(self):
        return NoAuthProvider()

    def _geocode(self, city: str, ctx: PluginContext) -> Dict[str, float]:
        """Convert city name to lat/lon using Open-Meteo geocoding."""
        if ctx.dry_run:
            return {"lat": 51.5074, "lon": -0.1278}
        result = ctx.http_get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en"},
        )
        results = result.get("results", [])
        if not results:
            from plugins.sdk.errors import NotFoundError
            raise NotFoundError(f"City not found: {city}")
        r = results[0]
        return {"lat": r["latitude"], "lon": r["longitude"], "name": r.get("name", city)}

    def _resolve_coords(self, params: Dict, ctx: PluginContext) -> Dict:
        if params.get("latitude") and params.get("longitude"):
            return {"lat": params["latitude"], "lon": params["longitude"], "name": params.get("city", "Custom Location")}
        city = params.get("city") or ctx.get_config("default_city", "London")
        return self._geocode(city, ctx)

    def execute_action(self, action_id: str, ctx: PluginContext, params: Dict[str, Any]) -> ActionResult:
        dispatch = {
            "get_current_weather": self._get_current_weather,
            "get_forecast":        self._get_forecast,
            "get_air_quality":     self._get_air_quality,
            "get_uv_index":        self._get_uv_index,
        }
        handler = dispatch.get(action_id)
        if not handler:
            from plugins.sdk.errors import PluginError
            raise PluginError(f"Unknown action: {action_id}")
        return handler(ctx, params)

    @action(id="get_current_weather", name="Get Current Weather", icon="🌤️", idempotent=True)
    def _get_current_weather(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Fetching current weather for {params.get('city', 'configured location')}")
        if ctx.dry_run:
            return ActionResult.ok(data={
                "city": params.get("city", "London"), "temperature_c": 18.5, "feels_like_c": 17.0,
                "humidity_pct": 65, "wind_speed_kmh": 12, "weather_code": 2,
                "description": "Partly cloudy", "is_day": True,
            })
        coords = self._resolve_coords(params, ctx)
        result = ctx.http_get(f"{_OPEN_METEO}/forecast", params={
            "latitude":  coords["lat"], "longitude": coords["lon"],
            "current":   "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
            "wind_speed_unit": "kmh",
        })
        cur = result.get("current", {})
        code = cur.get("weather_code", 0)
        return ActionResult.ok(data={
            "city":           coords.get("name", ""),
            "temperature_c":  cur.get("temperature_2m"),
            "feels_like_c":   cur.get("apparent_temperature"),
            "humidity_pct":   cur.get("relative_humidity_2m"),
            "wind_speed_kmh": cur.get("wind_speed_10m"),
            "weather_code":   code,
            "description":    _WMO_CODES.get(code, "Unknown"),
            "is_day":         bool(cur.get("is_day")),
        })

    @action(id="get_forecast", name="Get Forecast", icon="📊", idempotent=True)
    def _get_forecast(self, ctx: PluginContext, params: Dict) -> ActionResult:
        days = min(max(int(params.get("days", 7)), 1), 16)
        ctx.info(f"Fetching {days}-day forecast for {params.get('city', 'configured location')}")
        if ctx.dry_run:
            return ActionResult.ok(data={
                "city": params.get("city", "London"), "timezone": "Europe/London",
                "days": [{"date": f"2026-08-0{i+1}", "max_temp_c": 20+i, "min_temp_c": 12+i, "description": "Partly cloudy"} for i in range(days)],
            })
        coords = self._resolve_coords(params, ctx)
        result = ctx.http_get(f"{_OPEN_METEO}/forecast", params={
            "latitude":   coords["lat"], "longitude": coords["lon"],
            "daily":      "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,wind_speed_10m_max",
            "forecast_days": days, "timezone": "auto",
        })
        daily   = result.get("daily", {})
        n       = len(daily.get("time", []))
        days_out = []
        for i in range(n):
            code = (daily.get("weather_code") or [0] * n)[i]
            days_out.append({
                "date":             (daily.get("time") or [None]*n)[i],
                "max_temp_c":       (daily.get("temperature_2m_max") or [None]*n)[i],
                "min_temp_c":       (daily.get("temperature_2m_min") or [None]*n)[i],
                "precipitation_mm": (daily.get("precipitation_sum") or [0]*n)[i],
                "weather_code":     code,
                "description":      _WMO_CODES.get(code, "Unknown"),
                "wind_speed_kmh":   (daily.get("wind_speed_10m_max") or [None]*n)[i],
            })
        return ActionResult.ok(data={"city": coords.get("name"), "timezone": result.get("timezone", ""), "days": days_out})

    @action(id="get_air_quality", name="Get Air Quality", icon="💨", idempotent=True)
    def _get_air_quality(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Fetching air quality for {params.get('city', 'configured location')}")
        if ctx.dry_run:
            return ActionResult.ok(data={"aqi": 42, "pm2_5": 10.2, "pm10": 18.5, "co": 280, "category": "Good"})
        coords = self._resolve_coords(params, ctx)
        result = ctx.http_get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude":  coords["lat"], "longitude": coords["lon"],
            "current":   "pm10,pm2_5,carbon_monoxide,us_aqi",
        })
        cur  = result.get("current", {})
        aqi  = cur.get("us_aqi", 0)
        if aqi   <= 50:  cat = "Good"
        elif aqi <= 100: cat = "Moderate"
        elif aqi <= 150: cat = "Unhealthy for Sensitive Groups"
        elif aqi <= 200: cat = "Unhealthy"
        elif aqi <= 300: cat = "Very Unhealthy"
        else:            cat = "Hazardous"
        return ActionResult.ok(data={"aqi": aqi, "pm2_5": cur.get("pm2_5"), "pm10": cur.get("pm10"), "co": cur.get("carbon_monoxide"), "category": cat})

    @action(id="get_uv_index", name="Get UV Index", icon="☀️", idempotent=True)
    def _get_uv_index(self, ctx: PluginContext, params: Dict) -> ActionResult:
        ctx.info(f"Fetching UV index for {params.get('city', 'configured location')}")
        if ctx.dry_run:
            return ActionResult.ok(data={"uv_index": 5.2, "category": "Moderate"})
        coords = self._resolve_coords(params, ctx)
        result = ctx.http_get(f"{_OPEN_METEO}/forecast", params={
            "latitude": coords["lat"], "longitude": coords["lon"],
            "daily":    "uv_index_max", "forecast_days": 1, "timezone": "auto",
        })
        uv  = (result.get("daily", {}).get("uv_index_max") or [0])[0]
        if uv   < 3:  cat = "Low"
        elif uv < 6:  cat = "Moderate"
        elif uv < 8:  cat = "High"
        elif uv < 11: cat = "Very High"
        else:          cat = "Extreme"
        return ActionResult.ok(data={"uv_index": uv, "category": cat})

    def on_test(self, ctx: PluginContext) -> ActionResult:
        return self.execute_action("get_current_weather", ctx, {"city": "London"})
