import type { TimeSavings as Metrics } from '../types';

export default function TimeSavings({ metrics: m }: { metrics?: Metrics }) {
  return (
    <details className="drawer time-savings" open>
      <summary><span>Time saved vs normal pace</span></summary>
      <div className="feature-body">
        {!m ? <p>Timing metrics have not been supplied by the backend.</p> : <>
          <p><strong>{m.completedJobs ? `${Math.abs(m.netMinutesSaved).toFixed(1)} min ${m.netMinutesSaved < 0 ? 'over baseline' : 'saved'}` : 'No completed timed jobs yet'}</strong></p>
          <p>{m.completedJobs} completed timed jobs. Average cycle: {m.averageJobMinutes === null ? 'Not available' : `${m.averageJobMinutes.toFixed(1)} min`}.</p>
          <p>Active jobs: {m.activeJobs} · Combined elapsed job time: {m.activeJobMinutes.toFixed(1)} min.</p>
          <p>Normal pace: 8 min to pickup + {m.serviceMinutes.loading} min loading + 15 min to destination + {m.serviceMinutes.handoff} min handoff/paperwork + {m.serviceMinutes.reset} min reset = {m.baselineMinutesPerJob} min.</p>
          <p>Counts simulated time from job departure until the unit is available again. Idle time between jobs is excluded. In-progress jobs do not add savings yet. Trips without a recorded start are excluded.</p>
          <p>Road movement uses OSRM travel estimates, not verified posted speed limits. This is a comparison with your supplied baseline, not measured real-world savings.</p>
        </>}
      </div>
    </details>
  );
}
