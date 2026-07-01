/**
 * Background jobs — trigger + status polling.
 *
 * Jobs run server-side, so they keep going regardless of which page is open.
 * `useJobs` polls the latest run per job type (every 1.5s while any is running);
 * `useRunJob` kicks one off.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type JobType = "fair_values" | "financials" | "prices" | "grades";

export type JobStatus = "running" | "success" | "failed";

export interface JobRun {
  id: string;
  job_type: JobType;
  status: JobStatus;
  total: number;
  processed: number;
  succeeded: number;
  failed: number;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export const jobsKey = ["jobs"] as const;

export function useJobs() {
  return useQuery({
    queryKey: jobsKey,
    queryFn: () => api<JobRun[]>("/api/jobs"),
    refetchInterval: (query) => {
      const data = query.state.data as JobRun[] | undefined;
      return data?.some((j) => j.status === "running") ? 1500 : false;
    },
  });
}

export function useRunJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobType: JobType) =>
      api<JobRun>(`/api/jobs/${jobType}/run`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: jobsKey });
    },
  });
}
