import { ReactNode } from "react";

type DashboardShellProps = {
  form: ReactNode;
  results: ReactNode;
};

export default function DashboardShell({
  form,
  results
}: DashboardShellProps) {
  return (
    <main className="min-h-screen bg-gray-100 px-4 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8">
          <p className="text-sm font-medium text-blue-600">CreatorMind AI</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-gray-900">
            Content Performance Dashboard
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-gray-600">
            Predict post performance and get practical recommendations to improve
            reach, engagement, and viral potential.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
          <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            {form}
          </section>
          <div>{results}</div>
        </div>
      </div>
    </main>
  );
}
