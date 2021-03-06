"""
Author: Rohan Ramasamy
Date: 18/10/2018

This script contains code to compare the IEC electron cusp losses to the fusion power produced
"""

import numpy as np
import matplotlib.pyplot as plt

from plasma_physics.pysrc.theory.reactivities.fusion_reactivities import BoschHaleReactivityFit, DDReaction, DTReaction
from plasma_physics.pysrc.utils.physical_constants import PhysicalConstants
from plasma_physics.pysrc.theory.reactivities.fusion_reaction_rates import ReactionRatesCalculator


def get_power_balance(use_gummersall, include_ions):
    """
    Function to get a parameter scan of the power balance for different fusion
    reactions
    """
    current = 1e5
    radius = 10.0
    # keV and cm-3
    well_depth = np.logspace(-1, 2, 200)
    n = np.logspace(11, 19, 250)
    WELL_DEPTH, N = np.meshgrid(well_depth, n, indexing='ij')

    # Generate calculators
    dd_reaction_rate_calculator = BoschHaleReactivityFit(DDReaction())
    dt_reaction_rate_calculator = BoschHaleReactivityFit(DTReaction())

    # Calculate reaction rates - we are using Bosch Hale reactivities which Nevins original work stated were not far from beam
    # reactivities
    dd_reactivity = dd_reaction_rate_calculator.get_reactivity(WELL_DEPTH)
    dt_reactivity = dt_reaction_rate_calculator.get_reactivity(WELL_DEPTH)

    # Calculate power produced per metre cubed
    m3_conversion = 1e6
    MW_conversion = 1e-6
    N_dd = (N / 2) ** 2 / 2
    N_dt = (N / 2) ** 2
    dd_energy_released = 7.3e6 * PhysicalConstants.electron_charge
    dt_energy_released = 17.59e6 * PhysicalConstants.electron_charge
    P_dd = dd_reactivity * N_dd * dd_energy_released * m3_conversion * MW_conversion
    P_dt = dd_reactivity * N_dt * dt_energy_released * m3_conversion * MW_conversion

    # Get necessary well depth - assuming uniform charge. The electrons are assumed to have the well depth energy. This is 
    # the energy they are being accelerated to. The deuterium density is assumed to be superposed on top of this electron cloud
    # and the charges to cancel out
    WELL_DEPTH *= 1e3
    n_electrons = 2 * PhysicalConstants.epsilon_0 * WELL_DEPTH / (radius ** 2 * PhysicalConstants.electron_charge)
    n_electron_dd = N + n_electrons if include_ions else n_electrons
    n_electron_dt = N + n_electrons if include_ions else n_electrons

    # Calculate power losses - according to Gummersall thesis values
    if use_gummersall:
        P_cusp_dd = n_electron_dd * 4.3e-13 * WELL_DEPTH ** 1.75 / np.sqrt(current * radius ** 3) * MW_conversion
        P_cusp_dt = n_electron_dt * 4.3e-13 * WELL_DEPTH ** 1.75 / np.sqrt(current * radius ** 3) * MW_conversion
    else:
        P_cusp_dd = n_electron_dd * 2.43e-13 * WELL_DEPTH ** 1.72 / (current ** 0.594 * radius) * MW_conversion
        P_cusp_dt = n_electron_dt * 2.43e-13 * WELL_DEPTH ** 1.72 / (current ** 0.594 * radius) * MW_conversion

    # Get power balances - set power to be 1 if it is negative. We do not care about these points 
    power_threshold = 1.0
    dd_balance = P_dd - P_cusp_dd
    dd_balance[dd_balance < power_threshold] = power_threshold
    dt_balance = P_dt - P_cusp_dt
    dt_balance[dt_balance < power_threshold] = power_threshold

    # Plot power balance results
    fig, ax = plt.subplots(2, sharey='row', sharex='col', figsize=(12, 7))      

    # Plot Power Production
    N *= m3_conversion
    im = ax[0].contourf(np.log10(WELL_DEPTH), np.log10(N), np.log10(dd_balance), 100)
    fig.colorbar(im, ax=ax[0])
    ax[0].set_title("DD Power Balance [$MWm-3$]")
    ax[0].set_ylabel("Number density [$m^{-3}$]")
    im = ax[1].contourf(np.log10(WELL_DEPTH), np.log10(N), np.log10(dt_balance), 100)
    fig.colorbar(im, ax=ax[1])
    ax[1].set_title("DT Power Balance [$MWm-3$]")
    ax[1].set_ylabel("Number density [$m^{-3}$]")
    ax[1].set_xlabel("Well Depth [$eV$]")

    fig.suptitle("Polywell power balance for a {}m device with {}kA".format(radius, current * 1e-3))
    plt.show()


if __name__ == "__main__":
    include_ions = True
    use_gummersall = False
    get_power_balance(use_gummersall, include_ions)

