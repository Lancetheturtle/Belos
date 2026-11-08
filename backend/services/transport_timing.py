"""User-supplied comparison assumptions, in simulated minutes."""
LOAD_MINUTES = 15.0
HANDOFF_MINUTES = 32.0
RESET_MINUTES = 5.0
BASELINE_MINUTES = 75.0


def metrics(plan_rows, minute):
    completed = []
    active = []
    for row in plan_rows.values():
        body = row['body']
        start = body.get('jobStarted')
        if start is None: continue  # Imported/partial trips have no measured start.
        end = body.get('jobEnded')
        if body.get('stage') == 'complete' and end is not None:
            completed.append(max(0, end-start))
        elif body.get('stage') not in ('complete','queued'):
            active.append(max(0, minute-start))
    actual = sum(completed)
    baseline = BASELINE_MINUTES * len(completed)
    return {'baselineMinutesPerJob': BASELINE_MINUTES, 'completedJobs': len(completed),
            'completedJobMinutes': actual, 'baselineTotalMinutes': baseline,
            'netMinutesSaved': baseline-actual,
            'averageJobMinutes': actual/len(completed) if completed else None,
            'activeJobMinutes': sum(active), 'activeJobs': len(active),
            'serviceMinutes': {'loading': LOAD_MINUTES, 'handoff': HANDOFF_MINUTES, 'reset': RESET_MINUTES}}
