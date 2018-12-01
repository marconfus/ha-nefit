"""
Nefit thermostat.
Tested with Junkers CT100

Based on nefit-client-python
https://github.com/patvdleer/nefit-client-python
"""

REQUIREMENTS = ['sleekxmpp==1.3.3','pyaes==1.6.1','pyasn1==0.3.7','nefit-client==0.2.5']

import logging
from datetime import datetime, timedelta
import math
#import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA,
                                              STATE_AUTO, STATE_MANUAL, STATE_IDLE,
                                              SUPPORT_TARGET_TEMPERATURE,
                                              SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.const import STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF)

CONF_NAME = "name"
CONF_SERIAL = "serial"
CONF_ACCESSKEY = "accesskey"
CONF_PASSWORD = "password"
CONF_HOLIDAY_TEMP = "holiday_temp"
CONF_HOLIDAY_DURATION = "holiday_duration"

OPERATION_MANUAL = "heat" #manual
OPERATION_AUTO = "auto"
OPERATION_HOLIDAY = "off"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SERIAL): cv.string,
    vol.Required(CONF_ACCESSKEY): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_HOLIDAY_TEMP, default=7): vol.Coerce(float),
    vol.Optional(CONF_HOLIDAY_DURATION, default=31): vol.Coerce(int)
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Nefit thermostat."""
    name = config.get(CONF_NAME)
    serial = config.get(CONF_SERIAL)
    accesskey = config.get(CONF_ACCESSKEY)
    password = config.get(CONF_PASSWORD)
    holiday_temp = config.get(CONF_HOLIDAY_TEMP)
    holiday_duration = config.get(CONF_HOLIDAY_DURATION)

    add_devices([NefitThermostat(
        hass, name, serial, accesskey, password, holiday_temp, holiday_duration)], True)


class NefitThermostat(ClimateDevice):
    """Representation of a NefitThermostat device."""

    def __init__(self, hass, name, serial, accesskey, password, holiday_temp, holiday_duration):
        from nefit import NefitClient
        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self._serial = serial
        self._accesskey = accesskey
        self._password = password
        self._unit_of_measurement = TEMP_CELSIUS
        self._data = {}
        self._attributes = {}
        self._attributes["connection_error_count"] = 0
        self._operation_list = [OPERATION_MANUAL, OPERATION_AUTO, OPERATION_HOLIDAY]
        self.override_target_temp = False
        self.new_target_temp = 0
        self._manual = False
        self._holiday_mode = False
        self._holiday_temp = holiday_temp
        self._holiday_duration = holiday_duration

        _LOGGER.debug("Constructor for %s called.", self._name)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             self._shutdown)

        self._client = NefitClient(serial_number=self._serial,
                                   access_key=self._accesskey,
                                   password=self._password)
        self._client.connect()


    @property
    def name(self):
        """Return the name of the ClimateDevice."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    def update(self):
        """Get latest data"""
        _LOGGER.debug("update called.")

        try:
            data = self._client.get_status()
            _LOGGER.debug("update finished. result=%s", data)

            if isinstance(data, dict) and "user mode" in data:
                self._attributes["connection_state"] = "ok"
                self._manual = (data.get("user mode") == "manual")
            else:
                self._attributes["connection_state"] = "error"
                self._attributes["connection_error_count"] += self._attributes["connection_error_count"]

            if data:
                self._data = data

            self._attributes["boiler_indicator"] = self._data.get("boiler indicator")
            self._attributes["control"] = self._data.get("control")

            year_total, year_total_uom = self._client.get_year_total()
            _LOGGER.debug("Fetched get_year_total: %s %s", year_total, year_total_uom)
            self._attributes["year_total"] = year_total
            self._attributes["year_total_unit_of_measure"] = year_total_uom

            r = self._client.get("/ecus/rrc/userprogram/activeprogram")
            self._attributes["active_program"] = r.get("value")

            r = self._client.get("/ecus/rrc/dayassunday/day10/active")
            self._attributes["today_as_sunday"] = (r.get("value") == "on")

            r = self._client.get("/ecus/rrc/dayassunday/day11/active")
            self._attributes["tomorrow_as_sunday"] = (r.get("value") == "on")

            r = self._client.get("/system/appliance/systemPressure")
            self._attributes["system_pressure"] = r.get("value")

            r = self._client.get("/heatingCircuits/hc1/actualSupplyTemperature")
            self._attributes["supply_temp"] = r.get("value")

            r = self._client.get("/system/sensors/temperatures/outdoor_t1")
            self._attributes["outside_temp"] = r.get("value")

            r = self._client.get("/heatingCircuits/hc1/holidayMode/activated")
            self._holiday_mode = (r.get("value") == "on")

            dc = self._client.get_display_code()
            self._attributes["display_code"] = dc
        except Exception as exc:
            _LOGGER.warning("Nefit api returned invalid data: %s", exc)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        _LOGGER.debug("current_temperature called.")

        return self._data.get("in house temp", None)

    @property
    def current_operation(self):
        if self._manual:
            return OPERATION_MANUAL
        elif self._holiday_mode:
            return OPERATION_HOLIDAY
        else:
            return OPERATION_AUTO

    @property
    def target_temperature(self):

        #update happens too fast after setting new target, so value is not changed on server yet.
        #assume for this first update that the set target was succesful
        if self.override_target_temp:
            self._target_temperature = self.new_target_temp
            self.override_target_temp = False
        else:
            self._target_temperature = self._data.get("temp setpoint", None)

        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        try:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            _LOGGER.debug("set_temperature called (temperature=%s).", temperature)

            if temperature is None:
                return None

            self._client.set_temperature(temperature)

            self.override_target_temp = True
            self.new_target_temp = temperature

        except:
            _LOGGER.error("Error setting target temperature")

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        _LOGGER.debug("set_operation_mode called mode=%s.", operation_mode)
        if operation_mode == OPERATION_HOLIDAY:
            self.turn_holidaymode_on()
        else:
            if self._holiday_mode:
                self.turn_holidaymode_off()
            if operation_mode == OPERATION_MANUAL:
                self._client.put("/heatingCircuits/hc1/usermode", {"value": "manual"})
            else:
                self._client.put("/heatingCircuits/hc1/usermode", {"value": "clock"})
        self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return self._attributes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._manual or not self._holiday_mode

    def _shutdown(self, event):
        _LOGGER.debug("shutdown")
        self._client.disconnect()

    def turn_on(self):
        """Turn on."""
        self.set_operation_mode(OPERATION_AUTO)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self.set_operation_mode(OPERATION_HOLIDAY)
        self.schedule_update_ha_state()

    def turn_holidaymode_on(self):
        if self._manual:
            self._client.put("/heatingCircuits/hc1/usermode", {"value": "clock"})

        start_data = self._client.get("/heatingCircuits/hc1/holidayMode/start")
        start = datetime.strptime(start_data["value"], DATE_FORMAT)
        end = start + timedelta(days=self._holiday_duration)
        self._client.put("/heatingCircuits/hc1/holidayMode/activated",
                         {"value": "on"})
        self._client.put("/heatingCircuits/hc1/holidayMode/temperature",
                         {"value": self._holiday_temp})
        self._client.put("/heatingCircuits/hc1/holidayMode/end",
                         {"value": end.strftime(DATE_FORMAT)})

        self.override_target_temp = True
        self.new_target_temp = self._holiday_temp
        self._holiday_mode = True

    def turn_holidaymode_off(self):
        self._client.put("/heatingCircuits/hc1/holidayMode/activated", {"value": "off"})
        self._holiday_mode = False
