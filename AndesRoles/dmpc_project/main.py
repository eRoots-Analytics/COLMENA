from andes_interface import AndesInterface
from coordinator import Coordinator
from mpc_agent import MPCAgent
from config import Config
from post_processing import (
    plot_error_trajectories,
    plot_frequency_trajectories
)

andes = AndesInterface(Config.andes_url)

agent1 = MPCAgent(1, andes)
agent2 = MPCAgent(2, andes)

coordinator = Coordinator([agent1, agent2], andes)

andes.start_simulation()
converged, role_changes, problem_state = coordinator.run()

plot_error_trajectories(coordinator.error_save)
plot_frequency_trajectories(agent1, agent2)