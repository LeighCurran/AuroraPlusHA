[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20us%20a%20coffee-green.svg?style=for-the-badge)](https://www.buymeacoffee.com/leighcurran)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
![Maintenance](https://img.shields.io/maintenance/yes/2022.svg?style=for-the-badge)

# Aurora+ for Home Assistant

The Aurora+ integration adds support for retriving data from the Aurora+ API such as:

- EstimatedBalance - This is shown in the Aurora+ app as 'Balance'
- UsageDaysRemaining - This is shown in the Aurora+ app as 'Days Prepaid'
- AverageDailyUsage
- AmountOwed
- ActualBalance
- UnbilledAmount
- BillTotalAmount
- NumberOfUnpaidBills
- BillOverDueAmount

It also uses https://github.com/ldotlopez/ha-historical-sensor/ to fetch hourly
usage from the previous day, and make it available for the Energy dashboard:

- Dollar Value Usage (Total and per-Tariff)
- Kilowatt Hour Usage (Total and per-Tariff)

Note: To use the Aurora+ integration you need a valid account with Aurora.

## Configuration

This integration uses Home Assistant's config flow. Simply go to `Settings` /
`Devices & Services`, choose `Add Integration`, and search for `Aurora+`.

In the configuration dialog, you need to input an OAuth access key, which allows
access to your account's data without MFA. Authentication and API access is done
via https://github.com/shtrom/AuroraPlus/tree/oauth-mfa-token, which you can
also use to obtain the access token.

On any machine able to run Python (not necessarily your Home Assistant server),
install the AuroraPlus Python module from the URL above. You can then follow the
instructions at
https://github.com/shtrom/AuroraPlus/tree/oauth-mfa-token?tab=readme-ov-file#obtain-a-token.

Essentially, just run

   aurora_get_token

and follow the instructions (open link, enter MFA, copy URL of error page back).

## CAVEATs

1. The access_token seems to expire every 29 days. You'll have to redo this dance
   every month to keep being able to access the data. A notification will be
   issued when this is needed.

2. Upon adding the integration, only sensors with readings on the previous day
   will be available to add to the energy dashboard. This could be a problem if
   the previous day was a full-day off-peak day, as the peak tariff won't show
   up. Simply restart Home Assistant on a day after the missing tariff was used
   for a sensor to be created.

3. Upon reauthenticating, a bunch of SQLAlchemyError will prop up in the logs.
   They are currently believed to be harmless, and stop happening after a
   restart.

4. While this should support multiple services at once, this hasn't been tested.
