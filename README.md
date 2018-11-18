# ha-nefit
Home Assistant Nefit climate component

## Installation
Install the nefit library into your virtual python environment:
```
(venv) $ pip install nefit-client
```
Create ```custom_components/climate/``` in your homeassistant config directory and copy the file ```nefit.py``` into it.

## Configuration

```
climate:
  platform: nefit
  name: Heating
  serial: 'XXXXXXXXX'
  accesskey: 'xxxxxxxxx'
  password: 'xxxxxxxxx'
  holiday_temp: 7
  holiday_duration: 31
```

If any of your secrets in the configuration is numbers only, make sure to put it between quotes (`'`) to have homeassistant parse them correctly.
