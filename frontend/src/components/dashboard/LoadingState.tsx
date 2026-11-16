const loadingFrames = Array.from({ length: 10 }, (_, index) => index + 1);

type LoadingStateProps = {
  label: string;
  description?: string;
};

export function LoadingState({ label, description }: LoadingStateProps) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-3xl border border-[#e7e0f0] bg-white p-6 text-center shadow-sm">
      <div className="relative h-28 w-28" aria-hidden="true">
        {loadingFrames.map((frame) => (
          <img
            key={frame}
            src={`/loading/fps${frame}.png`}
            alt=""
            className="loading-frame absolute inset-0 h-full w-full object-contain"
            style={{ "--loading-frame": frame - 1 } as React.CSSProperties}
          />
        ))}
      </div>
      <p className="mt-3 text-sm font-black lowercase tracking-wide text-[#5b21b6]">{label}</p>
      {description ? <p className="mt-2 max-w-sm text-sm text-[#80778b]">{description}</p> : null}
    </div>
  );
}
