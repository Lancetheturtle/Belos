import { useEffect, useState } from 'react';

type Props = {
  speed: number;
  disabled: boolean;
  onChange: (speed: number) => void;
};

export default function SpeedControl({ speed, disabled, onChange }: Props) {
  const [draft, setDraft] = useState(speed);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    if (!dragging) setDraft(speed);
  }, [speed, dragging]);

  function commit(value: number) {
    setDragging(false);
    if (value !== speed) onChange(value);
  }

  return (
    <div className="simulation-speed">
      <label htmlFor="simulation-speed">
        Simulation speed <strong>{draft}×</strong>
      </label>
      <input
        id="simulation-speed"
        type="range"
        min="1"
        max="60"
        step="1"
        value={draft}
        disabled={disabled}
        aria-valuetext={`${draft} times normal speed`}
        onPointerDown={() => setDragging(true)}
        onChange={(event) => setDraft(Number(event.target.value))}
        onPointerUp={(event) => commit(Number(event.currentTarget.value))}
        onPointerCancel={() => {
          setDragging(false);
          setDraft(speed);
        }}
        onKeyUp={(event) => commit(Number(event.currentTarget.value))}
        onBlur={(event) => commit(Number(event.currentTarget.value))}
      />
      <div className="speed-presets">
        {[1, 15, 30, 60].map((value) => (
          <button
            key={value}
            disabled={disabled}
            aria-pressed={speed === value}
            onClick={() => {
              setDraft(value);
              commit(value);
            }}
          >
            {value}×
          </button>
        ))}
      </div>
      <p>
        1 real second = {draft} simulated seconds. Applies to driving and all
        service stages.
      </p>
    </div>
  );
}
