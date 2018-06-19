"""
Author: Rohan Ramasamy
Date: 06/06/2018

This file contains the model for coulomb collisions outlined in:

"Theory of cumulative small-anle collisions in plasmas" - K. Nanbu
"""

import numpy as np
import math
from scipy.interpolate import interp1d as interp1d
import os
import sys

from plasma_physics.pysrc.theory.coulomb_collisions.coulomb_collision import ChargedParticle
from plasma_physics.pysrc.simulation.pic.algo.geometry import vector_ops
from plasma_physics.pysrc.utils.physical_constants import PhysicalConstants

class NanbuCollisionModel(object):
    def __init__(self, number_densities, particles, particle_weightings, coulomb_logarithm=None, freeze_species_2=False):
        """
        Initialiser for Nanbu simulation class

        number_densities: array or integer of number densities of different species
        particles: array or ChargedParticle of different species
        particle_weightings: array or integer of particle weights
        """
        # Carry out defensive checks
        if isinstance(number_densities, np.ndarray):
            assert isinstance(particles, np.ndarray)
            assert isinstance(particle_weightings, np.ndarray)
            assert number_densities.shape == particles.shape == particle_weightings.shape
            assert len(number_densities.shape) == 1
            for i, n in enumerate(number_densities):
                assert n == number_densities[0]

            # Set particle variables
            self.__num_species = number_densities.shape[0]
            self.__particles = particles
            self.__particle_weights = particle_weightings
            self.__number_densities = number_densities
        elif isinstance(number_densities, int):
            assert isinstance(particles, ChargedParticle)
            assert isinstance(particle_weightings, int)
            
            # Set particle variables
            self.__num_species = 1
            self.__particles = [particles]
            self.__particle_weights = [particle_weightings]
            self.__number_densities = [number_densities]
        else:
            raise RuntimeError("number_densities must be either a float or numpy array")

        # Prevent multi-component simulations
        if self.__num_species > 2:
            raise RuntimeError("Multicomponent species are currently not handled")

        # Define temperatures of plasma - this will be set at the beginning of the simulation
        self.temperature = None

        # Generator interpolator for A
        data_file = os.path.join("/home/rohan/Code/plasma_physics/pysrc/simulation/coulomb_collisions/collision_models", "data", "A_interpolation_values.txt")
        self.__A_data = np.loadtxt(data_file)
        s_data = self.__A_data[0, :]
        A_data = self.__A_data[1, :]
        A_interpolator = interp1d(s_data, A_data)
        self._A_interpolator = A_interpolator

        # Set max s value to 6.0 as in Nanbu
        self.__max_s = 6.0

        # Set coulomb logarithm to a fixed value if it is specified
        self.__coulomb_logarithm = coulomb_logarithm

        # Set boolean for freezing species 2
        self.__freeze_species_2 = freeze_species_2

    def __calculate_s(self, g_mag, dt):
        if self.__num_species == 1:
            n = self.__number_densities[0] / 2
        else:
            # Assume number density is equal for all species
            n = self.__number_densities[0]

        # Calculate b_90 for collisions
        q_A = self.__particles[0].q
        m_A = self.__particles[0].m
        if self.__num_species == 1:
            q_B = self.__particles[0].q
            m_B = self.__particles[0].m
        else:
            q_B = self.__particles[1].q
            m_B = self.__particles[1].m
        m_eff = m_A * m_B / (m_A + m_B)
        b_90 = q_A * q_B / (2 * np.pi * PhysicalConstants.epsilon_0 * m_eff * g_mag ** 2)

        # Calculate coulomb logarithm
        if self.__coulomb_logarithm is None:
            T_background = self.temperature
            debye_length = PhysicalConstants.epsilon_0 * T_background
            debye_length /= n * PhysicalConstants.electron_charge ** 2
            debye_length = np.sqrt(debye_length)
            b_90 = q_A * q_B / (2 * np.pi * PhysicalConstants.epsilon_0 * m_eff * g_mag ** 2)

            coulomb_logarithm = np.log(debye_length / b_90)
        else:
            coulomb_logarithm = self.__coulomb_logarithm

        # Calculate s
        s = n * g_mag * np.pi * b_90 ** 2 * 10.0 * dt

        return s

    def __calculate_A(self, s):
        # Interpolate from pre-calculated values
        A = np.zeros(s.shape)
        for i, s_val in enumerate(s):
            try:
                A_val = self._A_interpolator(s_val)
            except ValueError:
                if s_val < self.__A_data[0, 0]:
                    A_val = 1.0 / s_val
                elif s_val > self.__max_s:
                    A_val = 3.0 * np.exp(-self.__max_s)
                elif self.__A_data[0, -1] < s_val:
                    A_val = 3.0 * np.exp(-s_val)
                else:
                    raise ValueError("Unexpected behaviour!")
            assert A_val != 0, "{}, {}".format(s_val, A_val)

            A[i] = A_val

        return A

    def __calculate_cos_chi(self, A, s):
        assert not np.any(A == 0)

        cos_chi = np.zeros(s.shape)
        U = np.random.uniform(0, 1, s.shape)
        for i, s_val in enumerate(s):
            U_val = U[i]
            A_val = A[i]
            if s_val > self.__max_s:
                # Assume isotropic
                cos_chi_val = 2 * U_val - 1
            else:
                cos_chi_val = 1 / A_val * np.log(np.exp(-A_val) + 2 * U_val * np.sinh(A_val))

            # Correct overflow in simulations
            if np.isinf(cos_chi_val):
                cos_chi_val = 1 + s_val * np.log(U_val)

            cos_chi[i] = cos_chi_val
    
        for cos_chi_val in cos_chi:
            assert -1.0 <= cos_chi_val <= 1.0, cos_chi_val

        return cos_chi

    def __calculate_post_collision_velocities(self, vel_A, vel_B, g_comp, g_mag, cos_chi, epsilon):
        # Calculate mass factors
        m_A = self.__particles[0].m
        m_B = self.__particles[0].m if self.__num_species==1 else self.__particles[1].m
        A_factor = (m_B / (m_A + m_B))
        B_factor = (m_A / (m_A + m_B))

        # Calculate h vectors
        g_perp = np.sqrt(g_comp[:, 1] ** 2 + g_comp[:, 2] ** 2)
        cos_e = np.cos(epsilon)
        sin_e = np.sin(epsilon)
        h_vec = np.zeros(g_comp.shape)
        h_vec[:, 0] = g_perp * cos_e
        h_vec[:, 1] = -(g_comp[:, 1] * g_comp[:, 0] * cos_e + g_mag * g_comp[:, 2] * sin_e) / g_perp
        h_vec[:, 2] = -(g_comp[:, 2] * g_comp[:, 0] * cos_e + g_mag * g_comp[:, 1] * sin_e) / g_perp

        # Give chi a new axis to allow matrix multiplication
        cos_chi = cos_chi[:, np.newaxis]
        sin_chi = np.sqrt(1.0 - cos_chi ** 2)
        deflection_vec = (g_comp * (1.0 - cos_chi) + h_vec * sin_chi) 
        vel_A -= A_factor * deflection_vec
        if not self.__freeze_species_2:
            vel_B += B_factor * deflection_vec

    def single_time_step(self, velocities, dt):
        # Assume number density is equal for all species
        if self.__num_species == 1:
            n = self.__number_densities[0] / 2
        else:
            n = self.__number_densities[0]

        # Randomise velocities
        current_state = np.random.get_state()
        indices = np.asarray(range(velocities.shape[0]))
        velocities_A = velocities[:n, :]
        velocities_B = velocities[n:, :]
        np.random.shuffle(velocities_A)
        np.random.shuffle(velocities_B)
        np.random.set_state(current_state)
        np.random.shuffle(indices[:n])
        np.random.shuffle(indices[n:])

        # Calculate relative velocities of species pair
        g_components = velocities_A - velocities_B
        g_mag = np.sqrt(g_components[:, 0] ** 2 + g_components[:, 1] ** 2 + g_components[:, 2] ** 2)

        # Calculate parameter s
        s = self.__calculate_s(g_mag, dt)

        # Calculate parameter A
        A = self.__calculate_A(s)

        # Calculate scattering angle chi
        cos_chi = self.__calculate_cos_chi(A, s)
        epsilon = np.random.uniform(0, 2 * np.pi, g_mag.shape)

        # Calculate post collisional velocities
        self.__calculate_post_collision_velocities(velocities_A, velocities_B, g_components, g_mag, cos_chi, epsilon)

        # Unshuffle velocities
        velocities[:n, :] = velocities_A
        velocities[n:, :] = velocities_B
        new_vel = velocities[indices.argsort(), :]

        # Set new temperature
        vel_mag = np.sqrt(new_vel[:, 0] ** 2 + new_vel[:, 1] ** 2 + new_vel[:, 2] ** 2)
        self.temperature = np.std(vel_mag) ** 2 * self.__particles[0].m / (3.0 * PhysicalConstants.boltzmann_constant)

        return new_vel
        

    def run_sim(self, velocities, dt, final_time):
        """
        Run simulation

        velocities: Nx3 array of velocities for particles, the velocities
             contain the particles of each species sequentially, N = n_1 + n_2
        dt: time step to be used in simulation
        final_time: time of simulation
        """
        assert velocities.shape[0] == np.sum(self.__number_densities)
        assert velocities.shape[1] == 3

        # # Set seed before simulation
        np.random.seed(1)

        # Set temperature
        vel_mag = np.sqrt(velocities[:, 0] ** 2 + velocities[:, 1] ** 2 + velocities[:, 2] ** 2)
        self.temperature = np.std(vel_mag) ** 2 * self.__particles[0].m / (3.0 * PhysicalConstants.boltzmann_constant)

        num_steps = int(math.ceil(final_time / dt) + 1)
        vel_results = np.zeros((velocities.shape[0], velocities.shape[1], num_steps))
        vel_results[:, :, 0] = velocities
        times = np.zeros((num_steps,))
        idx = 1
        t = 0.0
        times[0] = t
        print("Starting simulation...")
        while idx < num_steps:
            t += dt
            print("Timestep {}: t = {}".format(idx, t))

            velocities = self.single_time_step(velocities, dt)

            vel_results[:, :, idx] = velocities
            times[idx] = t

            idx += 1
        print("Simulation Complete!")

        return times, vel_results


if __name__ == '__main__':
    pass

