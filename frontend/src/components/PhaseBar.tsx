interface Props {
  currentPhase: string;
  onChange: (command: string) => void;
}

const PHASES: { command: string; label: string; phase: string }[] = [
  { command: "/plan", label: "План", phase: "PLAN" },
  { command: "/execute", label: "Исполнение", phase: "EXECUTE" },
  { command: "/validate", label: "Тест", phase: "VALIDATE" },
  { command: "/report", label: "Отчёт", phase: "REPORT" },
];

export default function PhaseBar({ currentPhase, onChange }: Props) {
  return (
    <div className="phase-bar">
      {PHASES.map((item) => (
        <button
          key={item.command}
          className={
            "phase-button" + (item.phase === currentPhase ? " active" : "")
          }
          onClick={() => onChange(item.command)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
