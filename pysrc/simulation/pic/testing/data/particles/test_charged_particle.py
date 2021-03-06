"""
Author: Rohan
Date: 27/03/17

Tests for the ideal mhd fluid solver
"""

import unittest
import numpy as np

from plasma_physics.pysrc.simulation.pic.data.particles.charged_particle import ChargedParticle


class ChargedParticleTest(unittest.TestCase):
    def test_constructor(self):
        particle = ChargedParticle(1.0, 2.0, np.linspace(1.0, 2.0, 3), np.linspace(1.0, 2.0, 3))

        self.assertAlmostEqual(particle.mass, 1.0)
        self.assertAlmostEqual(particle.charge, 2.0)
        self.assertAlmostEqual(particle.velocity[0, 0], 1.0)
        self.assertAlmostEqual(particle.velocity[0, 1], 1.5)
        self.assertAlmostEqual(particle.velocity[0, 2], 2.0)


if __name__ == '__main__':
    unittest.main()