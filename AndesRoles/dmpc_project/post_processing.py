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
    plt.plot(time, [pyo.value(agent1.model.freq[t]) for t in time], 'bo', label='Area 1')
    plt.plot(time, [pyo.value(agent1.model.freq[t]) for t in time], 'ro', label='Area 2')
    plt.xlabel(r"Time Step")
    plt.ylabel(r"$\omega_\mathrm{COI}$")
    plt.title("Frequency Trajectories")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()