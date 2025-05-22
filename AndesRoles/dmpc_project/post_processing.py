import matplotlib.pyplot as plt
import pyomo.environ as pyo

def plot_error_trajectories(error_save):
    iterations = list(range(len(error_save)))
    plt.figure()
    plt.plot(iterations, error_save, 'bo-')
    plt.ylabel(r"Error")
    plt.xlabel(r"Iteration")
    plt.title("Error Convergence")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_frequency_trajectories(agent1, agent2):
    plt.figure()
    time = list(range(agent1.T))
    plt.plot(time, [pyo.value(agent1.model.freq[t]) for t in time], 'b-', label=r"$\omega_\mathrm{COI, 1}$")
    plt.plot(time, [pyo.value(agent2.model.freq[t]) for t in time], 'r-', label=r"$\omega_\mathrm{COI, 2}$")
    plt.xlabel(r"Time Step")
    plt.ylabel(r"$\omega_\mathrm{COI}$")
    plt.xlim(0, agent1.T)
    plt.ylim(0.98, 1.02)
    plt.title("Frequency Trajectories")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_theta_trajectories(agent1, agent2):
    plt.figure()
    time = list(range(agent1.T))
    plt.plot(time, [pyo.value(agent1.model.theta[t]) for t in time], 'b-', label=r'$\theta_\mathrm{COI,1}$')
    plt.plot(time, [pyo.value(agent2.model.theta[t]) for t in time], 'r-', label=r'$\theta_\mathrm{COI,2}$')
    plt.xlabel(r"Time Step")
    plt.ylabel(r"$\theta_\mathrm{COI}$")
    plt.xlim(0, agent1.T)
    # plt.ylim(0)
    plt.title("Theta Trajectories")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_primal_copy_trajectories(agent1, agent2):
    plt.figure()
    time = list(range(agent1.T))
    plt.plot(time, [pyo.value(agent1.model.freq[t]) for t in time], 'b-', label=r"$\theta_\mathrm{original}$")
    plt.plot(time, [pyo.value(agent2.model.theta_areas[1, t]) for t in time], 'r-', label=r"$\theta_\mathrm{copy}$")
    plt.xlabel(r"Time Step")
    plt.ylabel(r"$\theta_\mathrm{COI}$")
    plt.xlim(0, agent1.T)
    # plt.ylim(0.98, 1.02)
    plt.title("Theta Original-Copy Trajectories")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()