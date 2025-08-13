import matplotlib.pyplot as plt
from datetime import datetime
import re

log = """
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
