type InsightSectionCardProps = {
  title: string;
  items: string[];
  accentClass: string;
};

export default function InsightSectionCard({
  title,
  items,
  accentClass
}: InsightSectionCardProps) {
  return (
    <div className="rounded-[1.75rem] bg-white p-6 shadow-sm ring-1 ring-[#e2e7ff]">
      <h3 className={`text-lg font-extrabold ${accentClass}`}>{title}</h3>
      <div className="mt-5 space-y-3">
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="rounded-2xl bg-[#f2f3ff] p-4 text-sm leading-6 text-[#464555]">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
