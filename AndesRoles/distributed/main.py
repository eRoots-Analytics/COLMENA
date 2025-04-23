from agent import Agent
from coordinator import Coordinator
from simulator import Simulator
import logging

logging.basicConfig(level=logging.INFO)

NUM_AGENTS = 2
MAX_ITER = 50
TOL = 1e-3

def main():
    sim = Simulator("http://localhost:5000")
    agents = [Agent(id=i, sim_interface=sim) for i in range(NUM_AGENTS)]
    coordinator = Coordinator(agents=agents, rho=1.0, max_iter=MAX_ITER, tol=TOL)

    for t in range(10):
        logging.info(f"\n========= Time step {t} =========")
        sim.get_states()
        coordinator.run_admm_step()
        for agent in agents:
            sim.write_inputs(agent.agent_id, agent.get_control())

if __name__ == "__main__":
    main()
