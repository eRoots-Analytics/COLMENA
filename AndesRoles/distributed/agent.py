import pyomo.environ as pyo
from mpc import MPC

class Agent:
    def __init__(self, id, andes_url, sim_interface):
        self.id = id
        self.andes_url = andes_url
        self.sim_interface = sim_interface
        self.shared_vars = {}
        self.dual_vars = {}
        self.solution = {}
        self.prev_solution = {}
        self.first = True

        self.mpc = MPC(id, self.andes_url)
        self.model = self.mpc.build(self)

    def update_shared_vars(self, shared_vars):
        self.shared_vars = shared_vars
        if self.model is not None:
            for k, v in shared_vars.items():
                if hasattr(self.model, k):
                    getattr(self.model, k).value = v

    def update_dual_vars(self, dual_vars):
        self.dual_vars = dual_vars

    def get_shared_vars(self):
        # Return shared variable values for coordinator
        return {k: self.solution.get(f"{k}[0]", 0.0) for k in self.shared_vars}

    def _apply_admm_modifications(self):
        # Modify objective with dual + penalty terms for ADMM
        rho = 1.0
        additional_expr = 0
        for k, val in self.shared_vars.items():
            primal = getattr(self.model, k)[0]
            dual = self.dual_vars.get(k, 0.0)
            additional_expr += dual * (primal - val) + (rho / 2.0) * (primal - val) ** 2

        self.model.obj.expr += additional_expr

    def extract_solution(self):
        # Extract optimal values from self.model
        self.solution = {
            var.name: pyo.value(var)
            for var in self.model.component_objects(pyo.Var, active=True)
            for idx in var
        }

    def get_control(self):
        return self.solution.get("u[0]", 0.0)
    
    def solve(self):
        # Add dual penalty to objective
        if not self.first:
            self._apply_admm_modifications()
        solver = pyo.SolverFactory("ipopt")
        solver.solve(self.model, tee=False)
        self.extract_solution()
        self.first = False
    
    
