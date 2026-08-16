export function Health({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="health">
      <span className={ok ? "dot online" : "dot"} />
      <span>{label}</span>
      <span className="health-right">{ok ? "OK" : "CHECK"}</span>
    </div>
  );
}
