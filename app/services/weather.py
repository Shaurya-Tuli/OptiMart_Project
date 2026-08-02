import os
import httpx
from typing import Optional


OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")


async def get_temperature_c(
    lat: Optional[float] = None, lng: Optional[float] = None
) -> float:
    """Fetch current ambient temperature in Celsius from OpenWeather API or return default 25.0°C fallback."""
    if not OPENWEATHER_API_KEY or lat is None or lng is None:
        return 25.0

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lng,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                return float(data.get("main", {}).get("temp", 25.0))
    except Exception:
        pass

    return 25.0
