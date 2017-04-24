"""
Nefit thermostat.
Tested with Junkers CT100

Based on nefit-client-python
https://github.com/patvdleer/nefit-client-python
"""

REQUIREMENTS = ['nefit-client']

import logging
from datetime import timedelta
import math
#import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval

from homeassistant.components.climate import (ClimateDevice,
                                              STATE_AUTO, PLATFORM_SCHEMA)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.const import STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP

from nefit import NefitClient

_LOGGER = logging.getLogger(__name__)



CONF_NAME = "name"
CONF_SERIAL = "serial"
CONF_ACCESSKEY = "accesskey"
CONF_PASSWORD = "password"

STATE_MANUAL = "manual"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SERIAL): cv.string,
    vol.Required(CONF_ACCESSKEY): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Nefit thermostat."""
    name = config.get(CONF_NAME)
    serial = config.get(CONF_SERIAL)
    accesskey = config.get(CONF_ACCESSKEY)
    password = config.get(CONF_PASSWORD)

    add_devices([NefitThermostat(
        hass, name, serial, accesskey, password)], True)


class NefitThermostat(ClimateDevice):
    """Representation of a NefitThermostat device."""

    def __init__(self, hass, name, serial, accesskey, password):
        """Initialize the thermostat."""
        self.hass = hass
        self._name = name
        self._serial = serial
        self._accesskey = accesskey
        self._password = password
        self._unit_of_measurement = TEMP_CELSIUS
        self._data = {}
        self._year_total = {}

        _LOGGER.debug("Constructor for {} called.".format(self._name))

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
        return [STATE_AUTO, STATE_MANUAL]

    def update(self):
        """Get latest data"""
        _LOGGER.debug("update called.")
        data = self._client.get_status()
        _LOGGER.debug("update finished. result={}".format(data))
        if data:
            self._data = data

        self._year_total = self._client.get_year_total()
        _LOGGER.debug("year_total={}".format(self._year_total))
        #
        # data = self._client.get("/ecus/rrc/recordings/gasusagePointer")
        # p = data.get("value")
        # if p:
        #     page = math.ceil(p / 32)
        #     data = self._client.get("/ecus/rrc/recordings/gasusage?page={}".format(page))
        #
        # data = self._client.get("/heatingCircuits/hc1/actualSupplyTemperature")


    @property
    def current_temperature(self):
        """Return the current temperature."""
        _LOGGER.debug("current_temperature called.")

        return self._data.get('in house temp', None)

    @property
    def current_operation(self):
        if self._data.get('user mode') == "manual":
            return STATE_MANUAL
        elif self._data.get('user mode') == "clock":
            return STATE_AUTO
        else:
            return None

    @property
    def target_temperature(self):
        return self._data.get('temp setpoint', None)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("set_temperature called (temperature={}).".format(temperature))
        if temperature is None:
            return None

        self._client.set_temperature(temperature)

    @property
    def boiler_indicator(self):
        _LOGGER.debug("boiler_indicator called.")
        return self._data.get('boiler indicator', None)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        _LOGGER.debug("set_operation_mode called mode={}.".format(operation_mode))
        if operation_mode == "manual":
            self._client.put('/heatingCircuits/hc1/usermode', {'value': 'manual'})
        else:
            self._client.put('/heatingCircuits/hc1/usermode', {'value': 'clock'})

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        dev_specific = {
            "boiler_indicator": self._data.get("boiler indicator"),
            "control": self._data.get("control"),
        }
        if self._year_total:
            dev_specific["year_total"] = self._year_total.get("value")
            dev_specific["year_total_unit_of_measure"] = self._year_total.get("unitOfMeasure")

        return dev_specific

    def _shutdown(self, event):
        _LOGGER.debug("shutdown")
        self._client.disconnect()
