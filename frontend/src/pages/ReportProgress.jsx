import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  Check,
  CheckCircle2,
  Circle,
  Clock,
  Download,
  FileText,
  Layout,
  Loader2,
  Search,
  Zap,
} from 'lucide-react';

const ReportProgress = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [timeLeft, setTimeLeft] = useState(null);
  const pollRef = useRef(null);

  const clearPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    return () => clearPolling();
  }, []);

  const refreshStatus = async () => {
    try {
      const response = await axios.get(`/api/report-status/${jobId}`);
      const payload = response.data;
      setStatus(payload);
      setLoading(false);

      if (payload.status === 'completed' || payload.status === 'failed') {
        clearPolling();
        setTimeLeft(0);
      } else if (payload.start_time && payload.estimated_seconds) {
        const start = new Date(payload.start_time).getTime();
        const now = new Date().getTime();
        const elapsed = (now - start) / 1000;
        const remaining = Math.max(5, Math.round(payload.estimated_seconds - elapsed));
        setTimeLeft(remaining);
      }
    } catch (error) {
      console.error('Failed to poll status:', error);
    }
  };

  useEffect(() => {
    const start = async () => {
      try {
        await refreshStatus();
      } catch (error) {
        setLoading(false);
        toast.error('Failed to load report progress');
      }
    };

    start();
    clearPolling();
    pollRef.current = setInterval(refreshStatus, 1500);
  }, [jobId]);

  // High-level phases driven by overall progress percentage. Each phase owns
  // a [progressMin, progressMax) window. This keeps the UI monotonic and
  // immune to out-of-order events from parallel chapter generation.
  const phases = useMemo(() => {
    const hasZip = !!status?.has_zip;
    const list = [];

    if (hasZip) {
      list.push(
        { key: 'preparing', title: 'Preparing Report', progressMin: 0, progressMax: 10, icon: Zap },
        { key: 'analyzing_zip', title: 'Analyzing Project ZIP', progressMin: 10, progressMax: 30, icon: Search },
        { key: 'planning', title: 'Locking Report Structure', progressMin: 30, progressMax: 40, icon: Layout },
      );
    } else {
      list.push(
        { key: 'preparing', title: 'Preparing Report', progressMin: 0, progressMax: 25, icon: Zap },
        { key: 'planning', title: 'Locking Report Structure', progressMin: 25, progressMax: 40, icon: Layout },
      );
    }

    list.push(
      { key: 'chapters', title: 'Generating Chapters', progressMin: 40, progressMax: 85, icon: BookOpen, showChapters: true },
      { key: 'bundling', title: 'Bundling PDF', progressMin: 85, progressMax: 95, icon: FileText },
      { key: 'finalizing', title: 'Finalizing Report', progressMin: 95, progressMax: 100, icon: CheckCircle2 },
      { key: 'ready', title: 'Ready to Download', progressMin: 100, progressMax: 100, icon: Download, terminal: true },
    );

    return list;
  }, [status?.has_zip]);

  const getPhaseState = (phase) => {
    if (!status) return 'pending';
    if (status.status === 'failed') return 'pending';
    const progress = status.progress || 0;
    const isCompleted = status.status === 'completed';

    // The terminal "Ready" phase only flips to done when the job is completed.
    if (phase.terminal) {
      return isCompleted ? 'done' : 'pending';
    }

    // Once the job is completed, every non-terminal phase is done.
    if (isCompleted) return 'done';

    if (progress >= phase.progressMax) return 'done';
    if (progress >= phase.progressMin) return 'active';
    return 'pending';
  };

  const handleDownload = async () => {
    if (!status?.report_id) return;
    setDownloadLoading(true);
    try {
      const response = await axios.get(`/api/download/${status.report_id}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `report_${status.report_id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Report downloaded successfully!');
    } catch {
      toast.error('Failed to download report');
    } finally {
      setDownloadLoading(false);
    }
  };

  const completedCount = phases.filter((phase) => getPhaseState(phase) === 'done').length;
  const activePhase = phases.find((phase) => getPhaseState(phase) === 'active');

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_right,#dbeafe_0%,#eff6ff_32%,#f8fafc_70%,#ffffff_100%)] p-4">
        <div className="relative w-full max-w-md rounded-3xl border border-white/80 bg-white/85 p-10 text-center shadow-[0_24px_80px_rgba(30,64,175,0.15)] backdrop-blur-xl">
          <div className="mx-auto mb-6 grid h-20 w-20 place-items-center rounded-full bg-blue-600 shadow-[0_14px_40px_rgba(37,99,235,0.35)]">
            <Loader2 className="h-8 w-8 animate-spin text-white" />
          </div>
          <p className="text-xl font-bold text-slate-900">Initializing Generator</p>
          <p className="mt-2 text-sm font-medium text-slate-500">Preparing your report pipeline and loading phase data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,#e0f2fe_0%,#f0f9ff_38%,#f8fafc_70%,#ffffff_100%)] py-10 px-4 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute -left-24 top-16 h-56 w-56 rounded-full bg-sky-300/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-16 bottom-24 h-60 w-60 rounded-full bg-emerald-300/20 blur-3xl" />

      <div className="relative mx-auto max-w-6xl">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <button
            onClick={() => navigate('/generate')}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/90 px-4 py-2.5 text-sm font-semibold text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </button>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-bold uppercase tracking-[0.2em] text-sky-700">
              <Clock className="h-3.5 w-3.5" />
              {timeLeft !== null && timeLeft > 0
                ? `ETA ${timeLeft}s`
                : status?.status === 'completed'
                  ? 'Finished'
                  : 'Estimating'}
            </div>
            <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-600">
              <Search className="h-3.5 w-3.5" />
              Job {jobId?.substring(0, 8)}...
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-[2rem] border border-slate-200/80 bg-white/85 shadow-[0_20px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl">
          <div className="border-b border-slate-100 bg-[linear-gradient(120deg,rgba(14,116,144,0.08)_0%,rgba(37,99,235,0.1)_55%,rgba(255,255,255,0.5)_100%)] px-6 py-7 sm:px-8">
            <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.22em] text-slate-500">Report Generation</p>
                <h1 className="mt-2 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">
                  {status?.title || 'Your Project Analysis'}
                </h1>
                <p className="mt-2 text-sm font-medium text-slate-600">
                  We are building your report phase by phase with live updates.
                </p>
              </div>
              <div className="rounded-2xl border border-blue-200 bg-white/80 px-4 py-3 text-right shadow-sm">
                <p className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-slate-500">Overall Progress</p>
                <p className="mt-1 text-4xl font-black tabular-nums text-blue-700">
                  {status?.progress || 0}
                  <span className="align-top text-xl text-blue-500">%</span>
                </p>
              </div>
            </div>

            <div className="relative h-3.5 w-full overflow-hidden rounded-full bg-slate-200/70">
              <div
                className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-cyan-500 via-blue-600 to-blue-500 transition-all duration-1000 ease-out"
                style={{ width: `${status?.progress || 0}%` }}
              />
              <div className="absolute inset-0 bg-[linear-gradient(45deg,rgba(255,255,255,0.2)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.2)_50%,rgba(255,255,255,0.2)_75%,transparent_75%,transparent)] bg-[length:20px_20px] animate-[progress-stripe_1s_linear_infinite]" />
            </div>
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="h-[520px] overflow-y-auto px-6 py-6 scrollbar-hide sm:px-8">
              <div className="space-y-3">
                {phases.map((phase, index) => {
                  const state = getPhaseState(phase);
                  const isActive = state === 'active';
                  const isDone = state === 'done';
                  const Icon = phase.icon;
                  const showChapterDetails =
                    phase.showChapters && isActive && status?.chapter_details?.length > 0;

                  return (
                    <div
                      key={phase.key}
                      className={`group relative rounded-2xl border px-4 py-4 transition ${
                        isActive
                          ? 'border-blue-200 bg-blue-50/70 shadow-[0_8px_24px_rgba(37,99,235,0.12)]'
                          : isDone
                            ? 'border-emerald-100 bg-emerald-50/40'
                            : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      {index < phases.length - 1 && (
                        <div className="pointer-events-none absolute left-7 top-11 h-[calc(100%+0.75rem)] w-px bg-slate-200" />
                      )}

                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full">
                          {isDone ? (
                            <div className="grid h-7 w-7 place-items-center rounded-full bg-emerald-500 shadow-[0_6px_18px_rgba(16,185,129,0.4)]">
                              <Check className="h-4 w-4 text-white" />
                            </div>
                          ) : isActive ? (
                            <div className="grid h-7 w-7 place-items-center rounded-full bg-blue-600 shadow-[0_8px_20px_rgba(37,99,235,0.35)]">
                              <Loader2 className="h-4 w-4 animate-spin text-white" />
                            </div>
                          ) : (
                            <div className="grid h-7 w-7 place-items-center rounded-full border-2 border-slate-300 bg-white">
                              <Circle className="h-2.5 w-2.5 fill-current text-slate-300" />
                            </div>
                          )}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <Icon className={`h-4 w-4 ${isDone ? 'text-emerald-600' : isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                              <p className={`text-sm font-bold sm:text-base ${isDone ? 'text-slate-600' : isActive ? 'text-blue-800' : 'text-slate-500'}`}>
                                {phase.title}
                              </p>
                            </div>
                            {isActive && (
                              <span className="rounded-lg bg-blue-100 px-2 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-blue-700">
                                Active
                              </span>
                            )}
                          </div>

                          {showChapterDetails && (
                            <div className="mt-3 space-y-1.5">
                              {status.chapter_details.map((chapter) => {
                                const chapterDone =
                                  chapter.status === 'completed' || chapter.status === 'fallback';
                                const chapterActive =
                                  chapter.status === 'running' || chapter.status === 'retrying';
                                return (
                                  <div
                                    key={chapter.chapter_number}
                                    className="flex items-start gap-2 rounded-lg border border-slate-100 bg-white/70 px-3 py-2 text-sm"
                                  >
                                    <div className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center">
                                      {chapterDone ? (
                                        <Check className="h-4 w-4 text-emerald-600" />
                                      ) : chapterActive ? (
                                        <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                                      ) : (
                                        <Circle className="h-2.5 w-2.5 fill-current text-slate-300" />
                                      )}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <p
                                        className={`truncate font-semibold ${
                                          chapterDone
                                            ? 'text-slate-500'
                                            : chapterActive
                                              ? 'text-blue-800'
                                              : 'text-slate-500'
                                        }`}
                                      >
                                        {chapter.title}
                                      </p>
                                      {chapterActive && chapter.detail && (
                                        <p className="truncate text-xs font-medium text-slate-500">
                                          {chapter.detail}
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {isActive && !phase.showChapters && status?.sub_steps?.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {status.sub_steps.map((step, idx) => (
                                <div
                                  key={idx}
                                  className="animate-in fade-in slide-in-from-left-3 flex items-start gap-2 text-sm font-medium text-slate-600"
                                  style={{ animationDelay: `${idx * 120}ms` }}
                                >
                                  <span className="mt-[2px] text-xs font-black uppercase tracking-widest text-blue-500">-&gt;</span>
                                  <span>{step}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <aside className="border-t border-slate-100 bg-slate-50/80 p-6 lg:border-l lg:border-t-0">
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">Live Snapshot</p>

              <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Current Phase</p>
                <p className="mt-2 text-sm font-bold text-slate-800">{activePhase?.title || (status?.status === 'completed' ? 'Completed' : 'Waiting')}</p>
              </div>

              <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Checklist</p>
                <p className="mt-2 text-2xl font-black tabular-nums text-slate-900">{completedCount}/{phases.length}</p>
                <p className="text-xs font-semibold text-slate-500">phases complete</p>
              </div>

              <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">Requested Pages</p>
                <p className="mt-2 text-2xl font-black tabular-nums text-slate-900">{status?.pages || 0}</p>
              </div>

              <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4 text-xs font-semibold text-slate-500">
                Report ID: {status?.report_id || 'Not assigned yet'}
              </div>
            </aside>
          </div>

          {status?.status === 'completed' && (
            <div className="border-t border-slate-200 bg-[linear-gradient(90deg,rgba(240,253,250,1)_0%,rgba(239,246,255,1)_100%)] p-6 sm:p-8">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-xl font-black text-slate-900">Report is ready to download</h3>
                  <p className="mt-1 text-sm font-medium text-slate-600">
                    Generation finished successfully. You can download the PDF now.
                  </p>
                </div>
                <button
                  onClick={handleDownload}
                  disabled={downloadLoading}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-3 text-sm font-bold text-white shadow-[0_12px_30px_rgba(37,99,235,0.35)] transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  {downloadLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Download className="h-5 w-5" />}
                  Download Report
                </button>
              </div>
            </div>
          )}

          {status?.status === 'failed' && (
            <div className="border-t border-red-200 bg-red-50 p-6 sm:p-8">
              <div className="flex items-start gap-4">
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-red-100 text-red-600">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-red-900">Generation Failed</h3>
                  <p className="mt-1 text-sm font-medium text-red-700">
                    {status.error || 'Check the details below for more information.'}
                  </p>
                  <button
                    onClick={() => navigate('/generate')}
                    className="mt-4 rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-800 transition hover:bg-red-100"
                  >
                    Try Again
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes progress-stripe {
          from { background-position: 0 0; }
          to { background-position: 20px 0; }
        }
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      ` }} />
    </div>
  );
};

export default ReportProgress;
