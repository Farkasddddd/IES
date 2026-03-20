# Economic Parameter Source

This note was transcribed from:

`C:\Users\27878\Desktop\IES\economic.docx`

## Extracted Contents

### CAPEX assumptions

| Item | Variable | Unit cost | Note |
| :--- | :--- | :--- | :--- |
| PV | scalar | 2700 yuan / kW | Based on 1 MW PV capacity |
| DAC cluster | x(1) | 8000 yuan / unit | Varies with DAC count |
| PEM electrolyzer | x(2) | 5000 yuan / kW | Varies with PEM power |
| Battery | x(3) | 1500 yuan / kWh | Varies with battery capacity |
| CO2 tank | x(4) | 0.1 yuan / mol | Confirmed by user |
| H2 tank | x(5) | 8.0 yuan / mol | Confirmed by user |

### Finance assumptions

- discount rate: 5%
- project lifetime: 20 years
- annualization method: Capital Recovery Factor (CRF)

CRF formula:

`CRF = r(1+r)^n / ((1+r)^n - 1)`

### OPEX assumptions

- grid electricity purchase price: 0.65 yuan / kWh

### Confirmed parameter table from user

| Parameter | Value | Unit |
| :--- | :--- | :--- |
| PV capital cost | 2700 | yuan / kW |
| DAC capital cost | 8000 | yuan / unit |
| PEM capital cost | 5000 | yuan / kW |
| Battery capital cost | 1500 | yuan / kWh |
| CO2 tank capital cost | 0.1 | yuan / mol |
| H2 tank capital cost | 8.0 | yuan / mol |
| Grid electricity price | 0.65 | yuan / kWh |
| Project lifetime | 20 | years |
| Discount rate | 5% | - |

### Scope note

The current economic model still does not yet include:

- fixed O&M
- labor
- water consumption
- catalyst replacement
- other non-electric variable costs

## Editable Parameter Entry

The editable parameter entry point for future use is:

`RL_capacity_optimization/config/economic_params.py`
