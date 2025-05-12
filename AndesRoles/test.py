import numpy as np
from copy import deepcopy


if alternative_update:
    if residual_norm > residual_improvement_norm:
        mpc_problem.alpha = mpc_problem.alpha*1.1
    elif residual_improvement_norm >= residual_norm:
        mpc_problem.alpha = mpc_problem.alpha*0.7
        if not hasattr(mpc_problem, 'integrator'):
            mpc_problem.integrator =  {k: 0 for k in mpc_problem.dual_vars}
    else:
        mpc_problem.alpha = mpc_problem.alpha     
    mpc_problem.residual_save = deepcopy(mpc_problem.delta_dual_vars) 
    for agent in agents:
        agent.model.rho.value = mpc_problem.alpha    
    if hasattr(mpc_problem, 'integrator') and False:
        for t in range(mpc_problem.T+1):
            for agent in mpc_problem.agents.values():
                for neighbor_area in agent.model.other_areas:
                    neighbor_agent = mpc_problem.agents[neighbor_area]
                    mpc_problem.delta_dual_vars[agent.area, neighbor_area , t] = sign*(agent.model.delta[t].value - neighbor_agent.model.delta_areas[agent.area, t].value)
                    mpc_problem.integrator[agent.area, neighbor_area , t] += mpc_problem.delta_dual_vars[agent.area, neighbor_area , t] 
                    mpc_problem.dual_vars[agent.area, neighbor_area , t] -= mpc_problem.alpha*mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                    mpc_problem.dual_vars[agent.area, neighbor_area , t] += mpc_problem.alpha0*mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                    mpc_problem.dual_vars[agent.area, neighbor_area , t] += mpc_problem.Kd*residual_improvement[agent.area, neighbor_area , t]
                    mpc_problem.dual_vars[agent.area, neighbor_area , t] += mpc_problem.Ki*mpc_problem.integrator[agent.area, neighbor_area , t]
else:
    error_save =  mpc_problem.error_save[-2][0] if len(mpc_problem.error_save) >= 2 else 0
    if error > error_save:
        _ = 0
        for agent in agents:
            _ = 0
            #agent.model.rho.value = max(0.0001,agent.model.rho.value*0.1)
    else:
        _ = 0    
        mpc_problem.alpha = 0.0
error = max(abs(v) for v in mpc_problem.delta_dual_vars.values())
real_error = max(v for v in mpc_problem.delta_dual_vars.values())
mpc_problem.error_save.append([error, mpc_problem.alpha, real_error]
error_save =  mpc_problem.error_save[-2][0] if len(mpc_problem.error_save) >= 2 else 0
real_error_save =  mpc_problem.error_save[-2][2] if len(mpc_problem.error_save) >= 2 else 0


class State:
    def __init__(self):
        self.P0 = np.ones(2)
        self.P1 = np.ones(2)
        self.toplay = 0
        self.history = []
    def coordinates(self):
        P0 = self.P0
        P1 = self.P1
        res = np.array([P0[0], P0[1], P1[0], P1[1], self.toplay])
        return res

def possible_moves(state):
    moves = []
    if state.toplay == 0:
        player_playing = state.P0
        player_waiting = state.P1
    else:
        player_playing = state.P1
        player_waiting = state.P0
        
    for i,hand in enumerate(player_playing):
        if hand == 0:
            continue
        else:
            play1 = np.array([hand,0, (state.toplay+1)%2])
            play2 = np.array([0,hand, (state.toplay+1)%2])
            moves.append(play1)
            moves.append(play2)
        for i in range(1, int(hand)+1):
            play = np.array([-i, i , state.toplay])
            new_state = state_update(deepcopy(state), play)
            if np.all(new_state.P0 != player_playing) and state.toplay==0:
                moves.append(play)
            elif np.all(new_state.P1 != player_playing) and state.toplay==1:
                moves.append(play)
    res = [np.array(move) for move in set(tuple(move) for move in moves)]
    return res

def state_update(state, move):
    if state.toplay == 1:
        state.P0 += move[:2]
    else:
        state.P1 += move[:2]
    state.P0 = np.array([x%5 for x in state.P0])
    state.P1 = np.array([x%5 for x in state.P1])
    state.toplay +=1
    state.toplay= state.toplay%2
    state.history.append(np.concatenate((state.P0, state.P1)))
    return state

Result = -np.ones((5,5,5,5,2))
#Result[0,0,:,:,0] = 0*Result[0,0,:,:,0]

def solve(state):
    print("P0", state.P0)
    print("P1", state.P1)
    state_coord = state.coordinates()
    state_coord = [int(round(c)) for c in state_coord]
    if Result[tuple(state_coord)] != -1:
        return Result[tuple(state_coord)]
    if np.all(state.P0 == np.zeros(2)) and state.toplay == 0:
        return 1
    elif np.all(state.P1 == np.zeros(2)) and state.toplay == 1:
        return 0
    moves = possible_moves(state)
    moves_value = []
    for move in moves:
        new_state = state_update(deepcopy(state), move)
        concatenated_array = np.concatenate((new_state.P0, new_state.P1)) 
        if any(np.array_equal(concatenated_array, hist) for hist in state.history):
            continue
        coord = new_state.coordinates()
        coord = [int(round(c)) for c in coord]
        if Result[tuple(coord)]!=-1:
            to_append = Result[tuple(coord)]
            moves_value.append(to_append)
        else:
            to_append = solve(new_state)
            moves_value.append(to_append)
        if state.toplay == 0:
            if np.min(moves_value) == 0:
                res = 1
            else:
                res = 0
        else:
            if np.min(moves_value) == 0:
                res = 0
            else:
                res = 1 
    Result[tuple(coord)] = res
    return res  
  
initial_state = State()
solve(initial_state)
print(Result)