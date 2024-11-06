import numpy as np
from copy import deepcopy

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