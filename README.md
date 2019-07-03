# RainBypass

Rain Sensor Bypass for Raspberry Pi

Based on this excellent tutorial: http://www.thirdeyevis.com/pi-page-3.php

7/2/2019 - Update

Apparantley Weather Underground stopped offering a free API service, so the
API key no longer works.

https://apicommunity.wunderground.com/weatherapi/topics/end-of-service-for-the-weather-underground-api

So I rewrote it using a DarkSky api call.

Renamed bypass.cfg and bypass.py and changed the services a outlined in the
tutorial above:

sudo pico /etc/rc.local

