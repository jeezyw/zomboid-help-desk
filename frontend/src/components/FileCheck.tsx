export function FileCheck({ label, found, path }: { label: string; found: boolean; path: string | null }) {
  return (
    <div className={found ? "file-check ok" : "file-check missing"}>
      <span className="dot" />
      <div>
        <div>{label}</div>
        <small>{path || "not found"}</small>
      </div>
    </div>
  );
}
