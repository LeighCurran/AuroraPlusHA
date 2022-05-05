[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20us%20a%20coffee-green.svg?style=for-the-badge)](https://www.buymeacoffee.com/leighcurran)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
![Maintenance](https://img.shields.io/maintenance/yes/2022.svg?style=for-the-badge)

# Aurora+ for Home Assistant

The Aurora+ integration adds support for retriving data from the Aurora+ API such as:

- Estimated Balance - This is shown in the Aurora+ app as 'Balance'
- Usage Days Remaining - This is shown in the Aurora+ app as 'Days Prepaid'
- Average Daily Usage
- Amount Owed
- Actual Balance
- Unbilled Amount
- BillTotal Amount
- Number Of Unpaid Bills
- Bill Over Due Amount
- Kilowatt Hour Usage
- Tarrifs

Note: To use the Aurora+ integration you need a valid account with Aurora.

## Configuration
Using *YAML*: add `auroraplus` platform to your sensor configuration in `configuration.yaml`. Example:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: auroraplus
    name: "Power Sensor"
    username: username@email.com
    password: Password
    scan_interval:
      hours: 2
    monitored_conditions: 
      - 'T31'
      - 'T41'
      - 'EstimatedBalance'
      - 'DollarValueUsage'
      - 'KilowattHourUsage'
```
Note: Name, scan_interval and monitored_conditions are optional. If scan_interval is not set a default value of 1 hours will be used. If monitored_conditions is not setall sensors will be added to Home Assistant. Most Aurora+ data is updated daily.
