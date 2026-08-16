export function Metric({ title, value, sub, icon }: any) {
  return (
    <div className="metric">
      <div className="metric-top"><span>{title}</span>{icon}</div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}
