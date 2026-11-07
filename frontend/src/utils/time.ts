// Minutes relative to the simulated 09:00 shift start.
export const clock=(minute:number)=>{const n=9*60+Math.ceil(minute-1e-7);return `${String(Math.floor(n/60)%24).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;};

// Current simulated shift time, down to the second for the live dashboard.
// Keep `clock`'s ceiling-to-minute behavior for scheduled ETA labels.
export const clockWithSeconds = (minute: number) => {
  const seconds = 9 * 3600 + Math.floor(minute * 60 + 1e-7);
  const hours = Math.floor(seconds / 3600) % 24;
  const minutes = Math.floor(seconds / 60) % 60;
  const remainingSeconds = seconds % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
};
