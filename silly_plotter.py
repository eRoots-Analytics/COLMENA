import matplotlib.pyplot as plt
from datetime import datetime
import re

log = """
2025/08/11 12:31:04 HTTP server listening on port: 5555
2025/08/11 12:33:23 Received service description for service:  AgentControl
2025/08/11 12:33:23 RoleId: Distributed_MPC matches hardware AREA
2025/08/11 12:33:23 RoleId: MonitoringRole matches hardware AREA
2025/08/11 12:33:23 Parsed kpis: [{abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001 0 0.001 < Distributed_MPC }]
2025/08/11 12:33:23 Parsed roles: [{Distributed_MPC xaviercasasbsc/distributed_mpc:latest [AREA] [{abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001 }]} {MonitoringRole xaviercasasbsc/monitoringrole:latest [AREA] []}]
2025/08/11 12:33:23 isRunning for role MonitoringRole to true
2025/08/11 12:33:23 Decided to run role: MonitoringRole, serviceId: AgentControl
2025/08/11 12:33:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown
2025/08/11 12:33:35 Failed to unmarshal JSON: json: cannot unmarshal object into Go struct field KPIQuery.KPIs.value of type float64
2025/08/11 12:34:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:34:05 Received alert for service:  AgentControl
2025/08/11 12:34:05 KPI query: [abs(avg(avg_over_time(agentcontrol_frequency#LABELS#[1m])) - 1)] < 0.001, associated role: AgentControl-8NTUDwFbvEYYnZuRYdsQah, level: Broken
2025/08/11 12:34:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Broken
2025/08/11 12:34:34 Decided to run role: Distributed_MPC, serviceId: AgentControl
2025/08/11 12:34:35 Received alert for service:  AgentControl
2025/08/11 12:34:35 KPI query: [abs(avg(avg_over_time(agentcontrol_frequency#LABELS#[1m])) - 1)] < 0.001, associated role: AgentControl-8NTUDwFbvEYYnZuRYdsQah, level: Critical
2025/08/11 12:35:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Critical
2025/08/11 12:35:05 Received alert for service:  AgentControl
2025/08/11 12:35:05 KPI query: [abs(avg(avg_over_time(agentcontrol_frequency#LABELS#[1m])) - 1)] < 0.001, associated role: AgentControl-8NTUDwFbvEYYnZuRYdsQah, level: Critical
2025/08/11 12:35:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Critical
2025/08/11 12:35:35 Received alert for service:  AgentControl
2025/08/11 12:35:35 KPI query: [abs(avg(avg_over_time(agentcontrol_frequency#LABELS#[1m])) - 1)] < 0.001, associated role: AgentControl-8NTUDwFbvEYYnZuRYdsQah, level: Critical
2025/08/11 12:36:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Critical
2025/08/11 12:36:05 Received alert for service:  AgentControl
2025/08/11 12:36:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:36:34 Decided to stop role: Distributed_MPC, serviceId: AgentControl
2025/08/11 12:36:35 Received alert for service:  AgentControl
2025/08/11 12:37:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:37:05 Received alert for service:  AgentControl
2025/08/11 12:37:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:37:35 Received alert for service:  AgentControl
2025/08/11 12:38:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:38:05 Received alert for service:  AgentControl
2025/08/11 12:38:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:38:35 Received alert for service:  AgentControl
2025/08/11 12:39:04 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:39:05 Received alert for service:  AgentControl
2025/08/11 12:39:34 KPI query: abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001, associated role: Distributed_MPC, level: Unknown_NoResults
2025/08/11 12:39:35 Received alert for service:  AgentControl
"""

pattern = re.compile(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) Decided to (run|stop) role: (\w+),')

events = []
for line in log.splitlines():
    match = pattern.search(line)
    if match:
        timestamp_str, action, role = match.groups()
        timestamp = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
        events.append((timestamp, action, role))

# Get the start time from the first event
start_time = events[0][0]

# Get the last line timestamp (last line in log with timestamp)
last_line = log.strip().splitlines()[-1]
last_ts_str = re.match(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})', last_line).group(1)
end_time = datetime.strptime(last_ts_str, "%Y/%m/%d %H:%M:%S")

# Convert to seconds relative to start_time
intervals = {}
for timestamp, action, role in events:
    elapsed_sec = (timestamp - start_time).total_seconds()
    if action == 'run':
        if role not in intervals:
            intervals[role] = []
        intervals[role].append([elapsed_sec, None])
    elif action == 'stop':
        if role in intervals:
            for interval in reversed(intervals[role]):
                if interval[1] is None:
                    interval[1] = elapsed_sec
                    break

# Close any open intervals at end_time
end_sec = (end_time - start_time).total_seconds()
for role, ivals in intervals.items():
    for interval in ivals:
        if interval[1] is None:
            interval[1] = end_sec

# Plotting
fig, ax = plt.subplots(figsize=(10, 3))
colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
role_colors = {role: colors[i % len(colors)] for i, role in enumerate(intervals)}

yticks = []
yticklabels = []

for i, (role, ivals) in enumerate(intervals.items()):
    for start, end in ivals:
        ax.barh(i, end - start, left=start, height=0.4, color=role_colors[role])
    yticks.append(i)
    yticklabels.append(role)

ax.set_yticks(yticks)
ax.set_yticklabels(yticklabels)
ax.set_xlabel('Seconds since start')
ax.set_title('Role Running Timeline (start = 0 seconds)')
plt.tight_layout()
plt.show()
