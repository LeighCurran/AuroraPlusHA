[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20us%20a%20coffee-green.svg?style=for-the-badge)](https://www.buymeacoffee.com/leighcurran)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
![Maintenance](https://img.shields.io/maintenance/yes/2025.svg?style=for-the-badge)

# Aurora+ for Home Assistant

The Aurora+ integration adds support for retrieving data from the Aurora+ API such as:

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
also use to obtain the ID token.

The easiest way to get a fresh token is to use [this
page](https://shtrom.github.io/AuroraPlus/)). Follow the instructions to login
to AuroraPlus and provide the URL of the error page to obtain an `id_token`
suitable to bootstrap authentication in HA.

If you'd prefer not to trust a random page on the web with your AuroraPlus
credentials, you can also obtain the token locally.  On any machine able to run
Python (not necessarily your Home Assistant server), install the AuroraPlus
Python module from the URL above. You can then follow the instructions at
https://github.com/shtrom/AuroraPlus/tree/oauth-mfa-token?tab=readme-ov-file#obtain-a-token.

Essentially, just run

   aurora_get_token

and follow the instructions (open link, enter MFA, copy URL of error page back).

## CAVEATs

1. Upon adding the integration, only sensors with readings on the previous
   week will be available to add to the energy dashboard. This could be
   an issue if the plan was just changed. Sensors for the new tariffs won't
   show up. Simply restart Home Assistant the next week for new sensors to
   be created.

2. Upon reauthenticating, a bunch of SQLAlchemyError will prop up in the logs.
   They are currently believed to be harmless, and stop happening after a
   restart.

3. Support for multiple services is not complete, and would rely on matching
   functionality not available in the Python library yet.
