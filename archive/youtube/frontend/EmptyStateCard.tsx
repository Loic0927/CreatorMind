type EmptyStateCardProps = {
  eyebrow?: string;
  title: string;
  description: string;
};

export default function EmptyStateCard({
  eyebrow,
  title,
  description
}: EmptyStateCardProps) {
  return (
    <div className="rounded-[2rem] bg-white p-8 shadow-sm ring-1 ring-[#e2e7ff]">
      {eyebrow ? (
        <p className="text-xs font-black uppercase tracking-[0.2em] text-[#392cc1]">
          {eyebrow}
        </p>
      ) : null}
      <h3 className="mt-2 text-2xl font-extrabold tracking-tight text-[#131b2e]">
        {title}
      </h3>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-[#464555]">
        {description}
      </p>
    </div>
  );
}
