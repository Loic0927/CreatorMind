type KpiCardProps = {
  label: string;
  value: string | number;
};

export default function KpiCard({ label, value }: KpiCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-gray-900">
        {value}
      </p>
    </div>
  );
}
