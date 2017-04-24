# ha-nefit
Home Assistant Nefit climate component

## Installation
Install the nefit library into your virtual python environment:
```
(venv) $ pip install git+https://github.com/marconfus/nefit-client-python.git
```
Create ```custom_components/climate/``` in your homeassistant config directory and copy the file ```nefit.py``` into it.

## Configuration

```
climate:
  platform: nefit
  name: Heating
  serial: XXXXXXXXX
  accesskey: xxxxxxxxx
  password: xxxxxxxxx
```
