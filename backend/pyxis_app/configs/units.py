"""
This module provides a unit registry and conversion functions for the oil and gas industry.
It includes definitions for common units such as barrels, cubic feet, and metric units,
as well as conversions between these units.

The unit registry is created using the pint library, which provides a powerful
and flexible unit system for Python.

The unit registry is defined as a singleton in the settings module.

```python
>>> from units import Q_

>>> # Example usage:
>>> oil_volume = Q_(100, "bbl")
>>> gas_volume = Q_(5, "MMscf")

>>> # Convert barrels to cubic meters
>>> oil_volume_m3 = oil_volume.to("m^3")
```
"""

import pint

# Create a unit registry
ureg = pint.UnitRegistry()

# Define custom units relevant to oil and gas industry and carbon emissions
# Note: Many common units are already defined in Pint

# Oil volume units
ureg.define(
    "barrel_oil = 42 * gallon = bbl_oil = bbl_water = bbl_steam = bbl_liquid = bbl"
)  # Standard oil barrel
ureg.define("mmbbl = 1e6 * bbl")  # Million barrels
ureg.define("mbbl = 1e3 * bbl")  # Thousand barrels

# Gas volume units
ureg.define("standard_cubic_foot = ft**3 = scf")  # Standard cubic foot
ureg.define("million_standard_cubic_feet = 1e6 * scf = MMscf")
ureg.define("billion_standard_cubic_feet = 1e9 * scf = Bscf")
ureg.define("trillion_standard_cubic_feet = 1e12 * scf = Tscf")
ureg.define("thousand_standard_cubic_meters = 1e3 * m**3 = ksm3")
ureg.define("million_standard_cubic_meters = 1e6 * m**3 = MSm3")

# Flow rate units
ureg.define("barrels_per_day = bbl/day = bpd")
ureg.define("thousand_barrels_per_day = 1e3 * bbl/day = kbpd")
ureg.define("million_cubic_feet_per_day = 1e6 * ft**3/day = MMcfd")
ureg.define("standard_cubic_feet_per_day = ft**3/day = scfd")

# Pressure units (most already in Pint, just adding common oil & gas notation)
ureg.define("pounds_per_square_inch = psi = psia")
ureg.define("kilopascal = kPa")
ureg.define("megapascal = MPa")
ureg.define("bar = 100000 * pascal")

# Emissions units
ureg.define("tonnes_CO2_equivalent = t_CO2e")
ureg.define("kilotonnes_CO2_equivalent = 1e3 * t_CO2e = kt_CO2e")
ureg.define("megatonnes_CO2_equivalent = 1e6 * t_CO2e = Mt_CO2e")
ureg.define("gigatonnes_CO2_equivalent = 1e9 * t_CO2e = Gt_CO2e")
ureg.define("pounds_CO2_equivalent = lb_CO2e")

# Energy units (BTU is important in oil & gas)
ureg.define("british_thermal_unit = 1055.06 * joule = BTU = Btu")
ureg.define("million_british_thermal_units = 1e6 * BTU = MMBTU")
ureg.define("thousand_british_thermal_units = 1e3 * BTU = kBTU")

# Production units
ureg.define("barrels_oil_equivalent = 5.8e6 * BTU = boe")
ureg.define("thousand_barrels_oil_equivalent = 1e3 * boe = kboe")
ureg.define("million_barrels_oil_equivalent = 1e6 * boe = MMboe")
ureg.define("tonnes_oil_equivalent = 41.868e9 * joule = toe")
ureg.define("thousand_tonnes_oil_equivalent = 1e3 * toe = ktoe")
ureg.define("million_tonnes_oil_equivalent = 1e6 * toe = Mtoe")

# Register the Quantity object for easier access
Q_ = ureg.Quantity
