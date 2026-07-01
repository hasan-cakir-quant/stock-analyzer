/**
 * JobsPanel — the four background-job triggers with live status.
 *
 * Each job runs server-side; this panel just starts them and polls status.
 * When a job finishes, the portfolio / data-availability / stocks caches are
 * invalidated so freshly computed results show up wherever they're displayed.
 */

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Play, XCircle } from "lucide-react";
import { useEffect, useRef } from "react";

import { dataAvailabilityKey } from "@/lib/dataAvailability";
import { type JobRun, type JobType, useJobs, useRunJob } from "@/lib/jobs";
import { PORTFOLIO_QUERY_KEY } from "@/lib/portfolio";
import { stocksKey } from "@/lib/stocks";
import { useToast } from "@/stores/toast";
import { cn } from "@/lib/utils";

interface JobMeta {
  type: JobType;
  label: string;
  desc: string;
}

const JOBS: JobMeta[] = [
  { type: "financials", label: "Fetch financials", desc: "New quarters + historical closes" },
  { type: "prices", label: "Fetch price & beta", desc: "Current price + beta" },
  { type: "fair_values", label: "Compute fair values", desc: "All scenarios" },
  { type: "grades", label: "Compute grades", desc: "All sub-grades + general" },
];

export function JobsPanel() {
  const jobsQuery = useJobs();
  const runJob = useRunJob();
  const toast = useToast();
  const queryClient = useQueryClient();

  const byType = new Map((jobsQuery.data ?? []).map((j) => [j.job_type, j]));

  // When any job transitions running → finished, refresh the views that read
  // its results.
  const prevRunning = useRef<Record<string, boolean>>({});
  useEffect(() => {
    let anyFinished = false;
    for (const job of jobsQuery.data ?? []) {
      const wasRunning = prevRunning.current[job.job_type] ?? false;
      const isRunning = job.status === "running";
      if (wasRunning && !isRunning) anyFinished = true;
      prevRunning.current[job.job_type] = isRunning;
    }
    if (anyFinished) {
      queryClient.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: dataAvailabilityKey });
      queryClient.invalidateQueries({ queryKey: stocksKey });
    }
  }, [jobsQuery.data, queryClient]);

  async function handleRun(type: JobType, label: string) {
    try {
      await runJob.mutateAsync(type);
      toast.show(`${label} started.`, { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `${label}: ${err.message}` : `${label} failed to start.`,
        { tone: "error" },
      );
    }
  }

  return (
    <div className="rounded-md border border-border bg-card">
      <header className="border-b border-border px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        Background jobs
      </header>
      <div className="grid gap-1.5 p-1.5 sm:grid-cols-2 lg:grid-cols-4">
        {JOBS.map((job) => (
          <JobCard
            key={job.type}
            meta={job}
            run={byType.get(job.type)}
            onRun={() => void handleRun(job.type, job.label)}
          />
        ))}
      </div>
    </div>
  );
}

function JobCard({
  meta,
  run,
  onRun,
}: {
  meta: JobMeta;
  run: JobRun | undefined;
  onRun: () => void;
}) {
  const running = run?.status === "running";
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-background px-2 py-1.5">
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0">
          <div className="truncate text-[11px] font-medium">{meta.label}</div>
          <div className="truncate text-[9px] text-muted-foreground">{meta.desc}</div>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          title={running ? "Running…" : "Run now"}
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {running ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Play className="h-3 w-3" />
          )}
          {running ? "Running" : "Run"}
        </button>
      </div>
      <JobStatusLine run={run} />
    </div>
  );
}

function JobStatusLine({ run }: { run: JobRun | undefined }) {
  if (!run) {
    return <div className="text-[9px] text-muted-foreground">Never run.</div>;
  }
  if (run.status === "running") {
    const pct = run.total > 0 ? Math.round((run.processed / run.total) * 100) : 0;
    return (
      <div className="text-[9px] text-muted-foreground">
        <div className="mb-0.5 flex justify-between tabular-nums">
          <span>
            {run.processed}/{run.total}
          </span>
          <span>{pct}%</span>
        </div>
        <div className="h-1 overflow-hidden rounded bg-muted">
          <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }
  const finished = run.finished_at ? new Date(run.finished_at).toLocaleString() : "";
  return (
    <div
      className={cn(
        "flex items-center gap-1 text-[9px]",
        run.status === "failed" ? "text-destructive" : "text-muted-foreground",
      )}
      title={run.message ?? undefined}
    >
      {run.status === "success" ? (
        <CheckCircle2 className="h-3 w-3 text-success" />
      ) : (
        <XCircle className="h-3 w-3 text-destructive" />
      )}
      <span className="truncate tabular-nums">
        {run.succeeded} ok{run.failed ? `, ${run.failed} failed` : ""} · {finished}
      </span>
    </div>
  );
}
