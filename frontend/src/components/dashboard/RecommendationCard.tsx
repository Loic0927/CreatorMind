type RecommendationCardProps = {
  title: string;
  items: string[];
};

export default function RecommendationCard({
  title,
  items
}: RecommendationCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <div
            key={`${title}-${index}`}
            className="rounded-xl bg-gray-50 px-3 py-3 text-sm leading-6 text-gray-700"
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
