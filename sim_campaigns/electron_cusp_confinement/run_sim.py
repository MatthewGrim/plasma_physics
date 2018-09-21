"""
Author: Rohan Ramasamy
Date: 08/08/2018

This script contains the main function to run single particle simulations using the non-relativistic boris solver in
this simulation campaign
"""

import os
import numpy as np
from matplotlib import pyplot as plt


from plasma_physics.pysrc.simulation.pic.algo.fields.magnetic_fields.generic_b_fields import InterpolatedBField
from plasma_physics.pysrc.simulation.pic.algo.particle_pusher.boris_solver import boris_solver
from plasma_physics.pysrc.simulation.pic.data.particles.charged_particle import PICParticle
from plasma_physics.pysrc.utils.physical_constants import PhysicalConstants


def run_simulation(params):
    b_field, particle, radius, domain_size, I, dI_dt = params
    print_output = False
    plot_sim = False

    # There is no E field in the simulations
    def e_field(x):
        B = b_field.b_field(x)
        dB_dt = B / I * dI_dt
        return -dB_dt

    X = particle.position
    V = particle.velocity
    Q = np.asarray([particle.charge])
    M = np.asarray([particle.mass])

    # Set timestep according to Gummersall approximation
    dt = 1e-9 * radius
    final_time = 1e5 * dt

    num_steps = int(final_time / dt)
    times = np.linspace(0.0, final_time, num_steps)
    positions = np.zeros((times.shape[0], X.shape[0], X.shape[1]))
    velocities = np.zeros((times.shape[0], X.shape[0], X.shape[1]))
    for i, t in enumerate(times):
        if print_output:
            print(t / final_time)
        if i == 0:
            positions[i, :, :] = X
            velocities[i, :, :] = V
            continue

        dt = times[i] - times[i - 1]

        x, v = boris_solver(e_field, b_field.b_field, X, V, Q, M, dt)

        if np.any(x[0, :] < -domain_size) or np.any(x[0, :] > domain_size):
            if print_output:
                print("PARTICLE ESCAPED! - {}, {}, {}".format(i, times[i], X[0]))

            x = positions[:, :, 0].flatten()
            y = positions[:, :, 1].flatten()
            z = positions[:, :, 2].flatten()
            v_x = velocities[:, :, 0].flatten()
            v_y = velocities[:, :, 1].flatten()
            v_z = velocities[:, :, 2].flatten()

            if plot_sim:
                # Plot 3D motion
                fig = plt.figure(figsize=(20, 10))
                ax = fig.add_subplot('111', projection='3d')
                ax.plot(x[:i-1], y[:i-1], z[:i-1], label='numerical')
                ax.set_xlim([-1.25 * radius, 1.25 * radius])
                ax.set_ylim([-1.25 * radius, 1.25 * radius])
                ax.set_zlim([-1.25 * radius, 1.25 * radius])
                ax.set_xlabel('X')
                ax.set_ylabel('Y')
                ax.set_zlabel('Z')
                ax.legend(loc='best')
                ax.set_title("Analytic and Numerical Particle Motion")
                plt.show()

            return times, x, y, z, v_x, v_y, v_z, i - 1

        positions[i, :, :] = x
        velocities[i, :, :] = v
        X = x
        V = v

    # Convert points to x, y and z locations
    x = positions[:, :, 0].flatten()
    y = positions[:, :, 1].flatten()
    z = positions[:, :, 2].flatten()
    v_x = velocities[:, :, 0].flatten()
    v_y = velocities[:, :, 1].flatten()
    v_z = velocities[:, :, 2].flatten()

    if plot_sim:
        # Plot 3D motion
        fig = plt.figure(figsize=(20, 10))
        ax = fig.add_subplot('111', projection='3d')
        ax.plot(x, y, z, label='numerical')
        ax.set_xlim([-1.25 * radius, 1.25 * radius])
        ax.set_ylim([-1.25 * radius, 1.25 * radius])
        ax.set_zlim([-1.25 * radius, 1.25 * radius])
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.legend(loc='best')
        ax.set_title("Analytic and Numerical Particle Motion")
        plt.show()

    return times, x, y, z, v_x, v_y, v_z, None


def run_parallel_sims(params):
    radius, electron_energy, I, batch_num, get_final_state, get_histograms = params
    assert get_final_state or get_histograms
    dI_dt = 0.0
    to_kA = 1e-3
    use_cartesian_reference_frame = False

    # Get output directory
    res_dir = "results_small_initialisation"
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)
    output_dir = os.path.join(res_dir, "radius-{}m".format(radius))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_dir = os.path.join(output_dir, "current-{}kA".format(I * to_kA))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get process name
    process_name = "radius-{}m-energy-{}eV-current-{}kA-batch-{}".format(radius, electron_energy, I * to_kA, batch_num)
    print("Starting process: {}".format(process_name))

    # Generate Polywell field
    loop_pts = 200
    domain_pts = 130
    loop_offset = 1.25
    dom_size = 1.1 * loop_offset * radius
    file_name = "b_field_{}_{}_{}_{}_{}_{}".format(I * to_kA, radius, loop_offset, domain_pts, loop_pts, dom_size)
    file_path = os.path.join("..", "mesh_generation", "data", "radius-{}m".format(radius),
                             "current-{}kA".format(I * to_kA), "domres-{}".format(domain_pts), file_name)
    b_field = InterpolatedBField(file_path, dom_pts_idx=6, dom_size_idx=8)

    seed = batch_num
    np.random.seed(seed)

    # Run simulations
    num_radial_bins = 200
    num_velocity_bins = 250
    total_particle_position_count = np.zeros((num_radial_bins,))
    total_particle_velocity_count_x = np.zeros((num_radial_bins, num_velocity_bins - 1))
    total_particle_velocity_count_y = np.zeros((num_radial_bins, num_velocity_bins - 1))
    total_particle_velocity_count_z = np.zeros((num_radial_bins, num_velocity_bins - 1))
    radial_bins = np.linspace(0.0, np.sqrt(3) * loop_offset * radius, num_radial_bins)
    vel = np.sqrt(2.0 * electron_energy * PhysicalConstants.electron_charge / PhysicalConstants.electron_mass)
    velocity_bins = np.linspace(-vel, vel, num_velocity_bins)
    num_sims = 420
    final_positions = []
    for i in range(num_sims):
        # Define particle velocity
        z_unit = np.random.uniform(-1.0, 1.0)
        xy_plane = np.sqrt(1 - z_unit ** 2)
        phi = np.random.uniform(0.0, 2 * np.pi)
        velocity = np.asarray([xy_plane * np.cos(phi), xy_plane * np.sin(phi), z_unit]) * vel

        # Generate particle position
        z_unit = np.random.uniform(-1.0, 1.0)
        xy_plane = np.sqrt(1 - z_unit ** 2)
        phi = np.random.uniform(0.0, 2 * np.pi)
        position = np.asarray([xy_plane * np.cos(phi), xy_plane * np.sin(phi), z_unit]) * np.random.uniform(0.0, 3.0 * radius / 16.0)

        # Generate particle
        particle = PICParticle(9.1e-31, 1.6e-19, position, velocity)

        t, x, y, z, v_x, v_y, v_z, final_idx = run_simulation((b_field, particle, radius, loop_offset * radius, I, dI_dt))

        # Add results to list
        escaped = False if final_idx is None else True
        final_idx = final_idx if escaped else -1

        # Save final position output
        if get_final_state:
            final_positions.append([t[final_idx], x[final_idx], y[final_idx], z[final_idx], escaped])

        # Change coordinate system
        if get_histograms:
            radial_position = np.sqrt(x[:final_idx] ** 2 + y[:final_idx] ** 2 + z[:final_idx] ** 2)
            if use_cartesian_reference_frame:
                particle_position_count, particle_velocity_count = get_particle_count(radial_bins, velocity_bins, radial_position, v_x, v_y, v_z)
            else:
                r_unit = np.zeros((3, x[:final_idx].shape[0]))
                r_unit[0, :] = x[:final_idx]
                r_unit[1, :] = y[:final_idx]
                r_unit[2, :] = z[:final_idx]
                r_unit /= np.sqrt(x[:final_idx] ** 2 + y[:final_idx] ** 2 + z[:final_idx] ** 2)

                xy_unit = np.zeros((3, x[:final_idx].shape[0]))
                xy_unit[0, :] = x[:final_idx]
                xy_unit[1, :] = y[:final_idx]
                xy_unit /= np.sqrt(np.sum(xy_unit ** 2, axis=0))

                latitude_unit = np.zeros(xy_unit.shape)
                latitude_unit[0] = xy_unit[1, :]
                latitude_unit[1] = -xy_unit[0, :]
                latitude_unit[2] = 0.0

                longitude_unit = np.zeros((3, x[:final_idx].shape[0]))
                longitude_unit[0, :] = r_unit[1, :] * latitude_unit[2, :] - r_unit[2] * latitude_unit[1]
                longitude_unit[1, :] = r_unit[2, :] * latitude_unit[0, :] - r_unit[0] * latitude_unit[2]
                longitude_unit[2, :] = r_unit[0, :] * latitude_unit[1, :] - r_unit[1] * latitude_unit[0]

                v_r = v_x[:final_idx] * r_unit[0, :] + v_y[:final_idx] * r_unit[1, :] + v_z[:final_idx] * r_unit[2, :]
                v_lat = v_x[:final_idx] * latitude_unit[0, :] + v_y[:final_idx] * latitude_unit[1, :] + v_z[:final_idx] * latitude_unit[2, :]
                v_long = v_x[:final_idx] * longitude_unit[0, :] + v_y[:final_idx] * longitude_unit[1, :] + v_z[:final_idx] * longitude_unit[2, :]

                particle_position_count, particle_velocity_count = get_particle_count(radial_bins, velocity_bins, radial_position, v_r, v_lat, v_long)

            # Get probability of electron in radial spacings in sim
            total_particle_position_count += particle_position_count
            total_particle_velocity_count_x += particle_velocity_count[0, :, :]
            total_particle_velocity_count_y += particle_velocity_count[1, :, :]
            total_particle_velocity_count_z += particle_velocity_count[2, :, :]

    # Save results to file
    if get_histograms:
        position_output_path = os.path.join(output_dir, "radial_distribution-current-{}-radius-{}-energy-{}-batch-{}.txt".format(I, radius, electron_energy, batch_num))
        velocity_output_path = os.path.join(output_dir, "velocity_distribution-current-{}-radius-{}-energy-{}-batch-{}".format(I, radius, electron_energy, batch_num))
        np.savetxt(position_output_path, np.stack((radial_bins, total_particle_position_count)))
        np.savetxt("{}_x.txt".format(velocity_output_path), total_particle_velocity_count_x)
        np.savetxt("{}_y.txt".format(velocity_output_path), total_particle_velocity_count_y)
        np.savetxt("{}_z.txt".format(velocity_output_path), total_particle_velocity_count_z)
    if get_final_state:
        final_state_output_path = os.path.join(output_dir, "final_state-current-{}-radius-{}-energy-{}-batch-{}.txt".format(I, radius, electron_energy, batch_num))
        np.savetxt(final_state_output_path,  np.asarray(final_positions))

    print("Finished process: {}".format(process_name))


def get_particle_count(radial_bins, velocity_bins, radial_positions, v_x, v_y, v_z):
    """
    This function counts the particles in each radial bin for location and velocity.
    """
    position_count = np.zeros(radial_bins.shape)
    velocity_count = np.zeros((3, radial_bins.shape[0], velocity_bins.shape[0] - 1))
    for i, bin_max in enumerate(radial_bins):
        if i == 0.0:
            continue

        bin_min = radial_bins[i - 1]
        points_in_range = np.where(np.logical_and(radial_positions >= bin_min, radial_positions < bin_max))
        position_count[i - 1] = points_in_range[0].shape[0]

        x_values = v_x[points_in_range]
        y_values = v_y[points_in_range]
        z_values = v_z[points_in_range]
        for j, v_bin_max in enumerate(velocity_bins):
            if j == 0.0:
                continue

            v_bin_min = velocity_bins[j - 1]
            x_points_in_range = np.where(np.logical_and(x_values >= v_bin_min, x_values < v_bin_max))
            y_points_in_range = np.where(np.logical_and(y_values >= v_bin_min, y_values < v_bin_max))
            z_points_in_range = np.where(np.logical_and(z_values >= v_bin_min, z_values < v_bin_max))

            velocity_count[0, i, j - 1] = x_points_in_range[0].shape[0]
            velocity_count[1, i, j - 1] = y_points_in_range[0].shape[0]
            velocity_count[2, i, j - 1] = z_points_in_range[0].shape[0]

    return position_count, velocity_count