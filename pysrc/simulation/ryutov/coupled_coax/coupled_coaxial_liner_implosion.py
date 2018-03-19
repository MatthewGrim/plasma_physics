"""
Author: Rohan Ramasamy
Date: 04/06/2017

This script builds on the coaxial liner model to incorporate a simple circuit model driving the implosion
"""

import numpy as np


class CoupledCoaxialLinerImplosion(object):

    def __init__(self, circuit_model, liner_model, **kwargs):
        """
        Constructor for the overall simulation class. The simulation class contains a coaxial liner module and a
        circuit model that are coupled together

        :return:
        """
        # Get times array
        time_resolution = kwargs.get("time_resolution", 10000)
        final_time = kwargs.get("final_time", 1e-4)
        self._times = np.linspace(0.0, final_time, time_resolution)

        # Initialise circuit model
        self.circuit_model = circuit_model(self._times, **kwargs)

        # Initialise liner model
        self.liner_model = liner_model(self._times, **kwargs)

    @property
    def times(self):
        return self._times

    def run_simulation(self, decoupled=False):
        """
        Main function to run the simulation

        :return:
        """
        R = 0.0
        L = 0.0
        L_dot = 0.0
        for ts, t in enumerate(self._times):
            if decoupled:
                R = 0.0
                L = 0.0
                L_dot = 0.0

            # Run circuit model to get input current
            I = self.circuit_model.evolve_timestep(ts, t, R, L, L_dot)

            # Run liner implosion to get feedback resistance, inductance and change in inductance
            R, L, L_dot, implosion_complete = self.liner_model.evolve_timestep(ts, I)

            # If liner inner radius is within the convergence ratio specified - break
            if implosion_complete:
                break

        return self.circuit_model, self.liner_model