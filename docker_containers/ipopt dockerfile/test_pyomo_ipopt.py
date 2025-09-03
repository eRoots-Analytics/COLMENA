
from pyomo.environ import ConcreteModel, Var, Objective, SolverFactory, TerminationCondition, value
import sys # For exiting with an error code

print('--- Pyomo-Ipopt Test Script ---')

# 1. Create a concrete Pyomo model
model = ConcreteModel(name='Simple NLP Test')

# 2. Define variables with bounds and initial values
#    Initial values can help the solver.
model.x = Var(bounds=(1.0, 5.0), initialize=2.0)
model.y = Var(bounds=(1.0, 5.0), initialize=2.0)

# 3. Define the objective function to minimize
#    Objective: (x - 3.5)^2 + (y - 2.5)^2
#    The unconstrained minimum is at x=3.5, y=2.5.
#    With the given bounds [1,5] for x and y, this point is feasible.
#    The optimal objective value should be 0.
model.obj = Objective(expr=(model.x - 3.5)**2 + (model.y - 2.5)**2)

# 4. Create a solver instance for Ipopt
#    Pyomo should find 'ipopt' if it's in the PATH (installed by coinor-ipopt package).
print('Creating Ipopt solver instance...')
try:
    solver = SolverFactory('ipopt')
except Exception as e:
    print(f'Error creating SolverFactory for Ipopt: {e}')
    print('This might indicate a problem with Pyomo or the environment.')
    sys.exit(1)


# 5. Check if the solver is available/functional
#    solver.available(exception_flag=False) returns False if not found/executable,
#    instead of raising an exception immediately.
print('Checking Ipopt availability through Pyomo...')
if not solver.available(exception_flag=False):
    print('Ipopt is NOT available to Pyomo according to solver.available().')
    try:
        exe_path = solver.executable()
        print(f'Pyomo\'s expected executable path for Ipopt: {exe_path if exe_path else "Not found or not set"}')
    except Exception as e_path:
        print(f'Error obtaining executable path from Pyomo: {e_path}')
    print('Ensure Ipopt is installed correctly and in the system PATH.')
    sys.exit(1)

print(f'Ipopt found by Pyomo. Executable: {solver.executable()}')
print(f'Ipopt version (if available through solver): {solver.version()}')

# 6. Solve the model
print('Attempting to solve the NLP problem with Ipopt...')
try:
    # tee=True will show Ipopt's console output during the solve process.
    results = solver.solve(model, tee=True)
except Exception as e:
    print(f'An error occurred during solver.solve(): {e}')
    print('This could be an issue with the model, solver, or their interaction.')
    sys.exit(1)

# 7. Check solver results
print('Solver finished.')
print(f'Solver Status: {results.solver.status}')
print(f'Termination Condition: {results.solver.termination_condition}')

if results.solver.termination_condition == TerminationCondition.optimal or \
   results.solver.termination_condition == TerminationCondition.locallyOptimal or \
   results.solver.termination_condition == TerminationCondition.globallyOptimal: # Ipopt usually finds local optima for NLPs
    print('Ipopt solved the problem to an optimal or locally optimal solution!')
    obj_val = value(model.obj)
    x_val = value(model.x)
    y_val = value(model.y)
    print(f'Objective value: {obj_val:.6f}')
    print(f'Optimal x: {x_val:.6f}')
    print(f'Optimal y: {y_val:.6f}')

    # Verify solution (approximate due to solver tolerances)
    # Expected objective value is 0.0
    if abs(obj_val - 0.0) < 0.001 and \
       abs(x_val - 3.5) < 0.01 and \
       abs(y_val - 2.5) < 0.01:
        print('Solution is correct and matches expected values.')
    else:
        print('Warning: Solution values are different from expected. Check solver log and tolerances.')
        # Not exiting with error, as Ipopt might find a valid local optimum slightly off due to settings/numerics.
        # But it's a good indicator to check.
else:
    print(f'Ipopt did not find an optimal solution. Status: {results.solver.termination_condition}')
    print('Solver messages (if any):')
    if hasattr(results.solver, 'message') and results.solver.message:
        print(results.solver.message)
    elif hasattr(results.Problem, 'description') and results.Problem.description:
         print(f'Problem Description: {results.Problem.description}')
    # You can inspect results.Problem and results.Solution for more details
    sys.exit(1) # Exit with error if not optimal

print('--- Pyomo-Ipopt Test Script completed successfully ---')