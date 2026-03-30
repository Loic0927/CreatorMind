type MetricCardProps = {
  label: string;
  value: string;
  tone?: "primary" | "secondary" | "tertiary";
};

const toneClasses = {
  primary: "bg-[#e3dfff] text-[#100069]",
  secondary: "bg-[#b7eaff] text-[#001f28]",
  tertiary: "bg-[#eaddff] text-[#25005a]"
};

export default function MetricCard({
  label,
  value,
  tone = "primary"
}: MetricCardProps) {
  return (
    <div className="rounded-[1.5rem] bg-white p-6 shadow-sm ring-1 ring-[#e2e7ff]">
      <div
        className={`inline-flex rounded-xl px-3 py-2 text-xs font-bold ${toneClasses[tone]}`}
      >
        {label}
      </div>
      <div className="mt-4 text-4xl font-extrabold tracking-tight text-[#131b2e]">
        {value}
      </div>
    </div>
  );
}
