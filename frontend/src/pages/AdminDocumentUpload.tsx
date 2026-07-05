import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Upload,
  FileText,
  X,
  CloudUpload,
  Loader2,
  Clock,
  ArrowLeft,
  HelpCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Trash2,
  AlertTriangle,
  Layers,
  FolderOpen,
  Files,
} from 'lucide-react';
import { OnboardingCard } from '../components/onboarding/OnboardingCard';
import { Button, Callout } from '../components/ui';
import {
  UploadResponse,
  BatchUploadResponse,
  JobStatus,
  JobsListResponse,
  isAllowedFileType,
  getAllowedExtensionsDisplay,
} from '../types/ingest';
import { adminFetch, isAdminAuthenticated } from '../utils/adminApi';

type UploadQueueItem = {
  id: string;
  file: File;
  displayName: string;
  relativePath: string;
  status: 'ready' | 'invalid' | 'duplicate';
  reason?: string;
};

type FileWithPath = File & { webkitRelativePath?: string };
type JobsListItem = JobsListResponse['jobs'][number];

const fileRelativePath = (file: File) =>
  (file as FileWithPath).webkitRelativePath || '';

const RECENT_DOCUMENTS_INITIAL_LIMIT = 10;
const RECENT_DOCUMENTS_BATCH_SIZE = 10;
const JOB_STATUS_FETCH_TIMEOUT_MS = 5000;
const ACTIVE_JOB_STATUSES = new Set<JobStatus['status']>([
  'pending',
  'processing',
  'chunked',
]);

const shouldHydrateJobStatus = (job: JobsListItem | JobStatus) =>
  ACTIVE_JOB_STATUSES.has(job.status as JobStatus['status']);

const buildFallbackJobStatus = (job: JobsListItem): JobStatus => {
  const status = job.status as JobStatus['status'];
  const isComplete = status === 'completed';

  return {
    job_id: job.job_id,
    filename: job.filename,
    status,
    created_at: job.created_at,
    updated_at: job.created_at,
    total_chunks: job.total_chunks,
    processed_chunks: isComplete ? job.total_chunks : 0,
    canonical_name: job.canonical_name,
    replacement_for_job_id: job.replacement_for_job_id,
    replacement_for_filename: job.replacement_for_filename,
    replaced_by_job_id: job.replaced_by_job_id,
    is_current: job.is_current,
  };
};

const fetchDetailedJobStatus = async (
  job: JobsListItem | JobStatus
): Promise<JobStatus> => {
  const statusController = new AbortController();
  const statusTimeout = setTimeout(
    () => statusController.abort(),
    JOB_STATUS_FETCH_TIMEOUT_MS
  );
  const fallbackStatus =
    'processed_chunks' in job ? job : buildFallbackJobStatus(job);

  try {
    const statusResponse = await adminFetch(`/ingest/status/${job.job_id}`, {
      signal: statusController.signal,
    });
    if (!statusResponse.ok) return fallbackStatus;
    return statusResponse.json() as Promise<JobStatus>;
  } catch {
    return fallbackStatus;
  } finally {
    clearTimeout(statusTimeout);
  }
};

export function AdminDocumentUpload({
  embedded = false,
}: {
  embedded?: boolean;
} = {}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // State
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<UploadQueueItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<{
    label: string;
    count: number;
    rejected: number;
  } | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobStatus[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [isLoadingMoreDocuments, setIsLoadingMoreDocuments] = useState(false);
  const [isRefreshingJobs, setIsRefreshingJobs] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [jobsErrorTitle, setJobsErrorTitle] = useState<string | null>(null);
  const [jobsWarning, setJobsWarning] = useState<string | null>(null);
  const [recentDocumentsVisibleLimit, setRecentDocumentsVisibleLimit] =
    useState(RECENT_DOCUMENTS_INITIAL_LIMIT);

  // Pipeline help modal state
  const [showPipelineHelpModal, setShowPipelineHelpModal] = useState(false);
  const [pipelineHelpPage, setPipelineHelpPage] = useState(0);
  const pipelineHelpModalRef = useRef<HTMLDivElement>(null);

  // Delete confirmation modal state
  const [deleteJobId, setDeleteJobId] = useState<string | null>(null);
  const [deleteJobFilename, setDeleteJobFilename] = useState<string>('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteModalRef = useRef<HTMLDivElement>(null);

  // Timeout ref for cleanup
  const successTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentUploadPageUrlRef = useRef(
    `${location.pathname}${location.search}${location.hash}`
  );
  const isFetchingJobsRef = useRef(false);
  const isLoadingMoreDocumentsRef = useRef(false);
  const recentJobsRef = useRef<JobStatus[]>([]);
  const recentDocumentsVisibleLimitRef = useRef(RECENT_DOCUMENTS_INITIAL_LIMIT);

  const JOBS_FETCH_TIMEOUT_MS = 30000;
  const validSelectedFiles = selectedFiles.filter(
    (item) => item.status === 'ready'
  );
  const rejectedSelectedFiles = selectedFiles.filter(
    (item) => item.status !== 'ready'
  );
  const fixedT = i18n.getFixedT(i18n.language);
  const uploadNavigationWarning = t(
    'upload.navigationWarning',
    'Your document is still being transferred. Leave only after processing has started, or the upload may not be saved.'
  );
  const translateErrorMessage = (message: string) =>
    message.startsWith('errors.') && i18n.exists(message)
      ? fixedT(message)
      : message;
  const updateRecentDocumentsVisibleLimit = useCallback(
    (nextLimit: number | ((currentLimit: number) => number)) => {
      const resolvedLimit =
        typeof nextLimit === 'function'
          ? nextLimit(recentDocumentsVisibleLimitRef.current)
          : nextLimit;
      recentDocumentsVisibleLimitRef.current = resolvedLimit;
      setRecentDocumentsVisibleLimit(resolvedLimit);
    },
    []
  );

  useEffect(() => {
    currentUploadPageUrlRef.current = `${location.pathname}${location.search}${location.hash}`;
  }, [location]);

  useEffect(() => {
    folderInputRef.current?.setAttribute('webkitdirectory', '');
    folderInputRef.current?.setAttribute('directory', '');
  }, []);

  useEffect(() => {
    if (!isUploading) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = uploadNavigationWarning;
    };

    const handleDocumentClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.altKey ||
        event.ctrlKey ||
        event.shiftKey
      ) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) return;

      const anchor = target.closest('a[href]');
      if (!(anchor instanceof HTMLAnchorElement)) return;

      const destination = new URL(anchor.href, window.location.href);
      const destinationUrl = `${destination.pathname}${destination.search}${destination.hash}`;
      if (destinationUrl === currentUploadPageUrlRef.current) return;

      if (!window.confirm(uploadNavigationWarning)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    const handlePopState = () => {
      if (!isUploading) return;

      if (!window.confirm(uploadNavigationWarning)) {
        window.history.pushState(null, '', currentUploadPageUrlRef.current);
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('click', handleDocumentClick, true);
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('click', handleDocumentClick, true);
      window.removeEventListener('popstate', handlePopState);
    };
  }, [isUploading, uploadNavigationWarning]);

  // Cleanup success timeout on unmount
  useEffect(() => {
    return () => {
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current);
      }
    };
  }, []);

  // Check if admin is logged in
  useEffect(() => {
    if (!isAdminAuthenticated()) {
      navigate('/admin');
    }
  }, [navigate]);

  // Fetch recent jobs with timeout
  const fetchJobs = useCallback(
    async (options: { showLoading?: boolean; showErrors?: boolean } = {}) => {
      const { showLoading = false, showErrors = false } = options;
      if (isFetchingJobsRef.current) return;
      isFetchingJobsRef.current = true;

      if (showErrors) {
        setJobsError(null);
        setJobsErrorTitle(null);
        setJobsWarning(null);
      }
      if (showLoading) {
        setIsLoadingJobs(true);
      }
      setIsRefreshingJobs(true);

      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(
        () => controller.abort(),
        JOBS_FETCH_TIMEOUT_MS
      );

      try {
        const response = await adminFetch('/ingest/jobs', {
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(t('errors.failedToFetchJobs'));
        const data: JobsListResponse = await response.json();

        const previousJobCount = recentJobsRef.current.length;
        const hydrationLimit = Math.max(
          RECENT_DOCUMENTS_INITIAL_LIMIT,
          Math.min(recentDocumentsVisibleLimitRef.current, data.jobs.length)
        );
        const previousById = new Map(
          recentJobsRef.current.map((job) => [job.job_id, job])
        );
        const fallbackJobStatuses = data.jobs.map(buildFallbackJobStatus);
        const visibleJobStatuses = await Promise.all(
          fallbackJobStatuses.slice(0, hydrationLimit).map((job) => {
            if (!showLoading && !shouldHydrateJobStatus(job)) {
              return Promise.resolve(previousById.get(job.job_id) ?? job);
            }
            return fetchDetailedJobStatus(job);
          })
        );
        const deferredJobStatuses = data.jobs
          .slice(hydrationLimit)
          .map(buildFallbackJobStatus);
        const jobStatuses = visibleJobStatuses.concat(deferredJobStatuses);

        setRecentJobs(jobStatuses);
        recentJobsRef.current = jobStatuses;
        updateRecentDocumentsVisibleLimit((currentLimit) => {
          if (jobStatuses.length <= RECENT_DOCUMENTS_INITIAL_LIMIT) {
            return RECENT_DOCUMENTS_INITIAL_LIMIT;
          }
          if (previousJobCount > 0 && jobStatuses.length < previousJobCount) {
            return RECENT_DOCUMENTS_INITIAL_LIMIT;
          }
          if (currentLimit > jobStatuses.length) {
            return RECENT_DOCUMENTS_INITIAL_LIMIT;
          }
          return Math.max(currentLimit, RECENT_DOCUMENTS_INITIAL_LIMIT);
        });
        setJobsError(null);
        setJobsErrorTitle(null);
        setJobsWarning(null);
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          if (showErrors) {
            const message = t(
              'upload.jobsTimeout',
              'Server is busy processing documents. Try refreshing in a moment.'
            );
            if (recentJobsRef.current.length > 0) {
              setJobsWarning(message);
            } else {
              setJobsErrorTitle(t('upload.serverBusy', 'Server is busy'));
              setJobsError(message);
            }
          }
        } else {
          console.error(t('errors.errorFetchingJobs'), error);
          if (showErrors) {
            if (error instanceof Error && error.message.startsWith('errors.')) {
              const errorMessage = translateErrorMessage(error.message);
              if (recentJobsRef.current.length > 0) {
                setJobsWarning(errorMessage);
              } else {
                setJobsErrorTitle(t('errors.failedToFetchJobs'));
                setJobsError(errorMessage);
              }
            } else {
              const errorMessage = t('errors.failedToFetchJobs');
              if (recentJobsRef.current.length > 0) {
                setJobsWarning(errorMessage);
              } else {
                setJobsErrorTitle(errorMessage);
                setJobsError(errorMessage);
              }
            }
          }
        }
      } finally {
        clearTimeout(timeoutId);
        setIsLoadingJobs(false);
        setIsRefreshingJobs(false);
        isFetchingJobsRef.current = false;
      }
    },
    [t, updateRecentDocumentsVisibleLimit]
  );

  useEffect(() => {
    fetchJobs({ showLoading: true, showErrors: true });
  }, [fetchJobs]);

  // Handle document deletion
  const handleDeleteJob = async (jobId: string) => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const response = await adminFetch(`/ingest/jobs/${jobId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || t('upload.deleteFailed'));
      }

      // Close modal and refresh jobs
      setDeleteJobId(null);
      setDeleteJobFilename('');
      await fetchJobs({ showLoading: true, showErrors: true });
    } catch (error) {
      console.error('Delete error:', error);
      if (error instanceof Error && error.message.startsWith('errors.')) {
        setDeleteError(translateErrorMessage(error.message));
      } else {
        setDeleteError(
          error instanceof Error ? error.message : t('upload.deleteFailed')
        );
      }
    } finally {
      setIsDeleting(false);
    }
  };

  // Open delete confirmation modal
  const openDeleteModal = (jobId: string, filename: string) => {
    setDeleteJobId(jobId);
    setDeleteJobFilename(filename);
    setDeleteError(null);
  };

  // Close delete confirmation modal
  const closeDeleteModal = () => {
    if (!isDeleting) {
      setDeleteJobId(null);
      setDeleteJobFilename('');
      setDeleteError(null);
    }
  };

  // Focus trap for delete modal
  useEffect(() => {
    if (deleteJobId && deleteModalRef.current) {
      deleteModalRef.current.focus();
    }
  }, [deleteJobId]);

  // Poll for job status updates
  // TODO: Consider WebSocket or SSE for real-time job status updates
  useEffect(() => {
    const hasActiveJobs = recentJobs.some(shouldHydrateJobStatus);

    if (hasActiveJobs) {
      const interval = setInterval(
        () => fetchJobs({ showLoading: false, showErrors: false }),
        3000
      );
      return () => clearInterval(interval);
    }
  }, [recentJobs, fetchJobs]);

  const buildQueueItems = (files: File[]) => {
    const seen = new Set<string>();
    return files.map((file, index): UploadQueueItem => {
      const relativePath = fileRelativePath(file);
      const displayName = relativePath || file.name;
      const id = `${displayName}:${file.size}:${file.lastModified}:${index}`;

      if (!isAllowedFileType(displayName)) {
        return {
          id,
          file,
          displayName,
          relativePath,
          status: 'invalid',
          reason: t('upload.invalidFileType', {
            extensions: getAllowedExtensionsDisplay(),
          }),
        };
      }

      if (seen.has(displayName)) {
        return {
          id,
          file,
          displayName,
          relativePath,
          status: 'duplicate',
          reason: t(
            'upload.duplicateInBatch',
            'Duplicate document name in this batch'
          ),
        };
      }

      seen.add(displayName);
      return {
        id,
        file,
        displayName,
        relativePath,
        status: 'ready',
      };
    });
  };

  // Handle file selection
  const handleFilesSelect = (files: File[]) => {
    setUploadError(null);
    setUploadSuccess(null);

    if (files.length === 0) {
      return;
    }

    setSelectedFiles(buildQueueItems(files));
  };

  // Handle drag events
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    handleFilesSelect(Array.from(e.dataTransfer.files));
  };

  // Handle file input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFilesSelect(Array.from(e.target.files || []));
  };

  // Handle upload
  const handleUpload = async () => {
    if (validSelectedFiles.length === 0) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const uploadLabel =
      validSelectedFiles.length === 1
        ? validSelectedFiles[0].displayName
        : t('upload.documentsSelected', '{{count}} documents', {
            count: validSelectedFiles.length,
          });

    try {
      const formData = new FormData();
      const useBatchEndpoint =
        validSelectedFiles.length > 1 ||
        validSelectedFiles.some((item) => item.relativePath);
      let response: Response;

      if (useBatchEndpoint) {
        validSelectedFiles.forEach((item) => {
          formData.append('files', item.file);
          formData.append('relative_paths', item.relativePath);
        });
        response = await adminFetch('/ingest/upload/batch', {
          method: 'POST',
          body: formData,
        });
      } else {
        formData.append('file', validSelectedFiles[0].file);
        response = await adminFetch('/ingest/upload', {
          method: 'POST',
          body: formData,
        });
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data: UploadResponse | BatchUploadResponse = await response.json();
      console.log('Upload successful:', data);

      // Once the backend returns a job_id, ingestion is durable and navigation is safe.
      setIsUploading(false);

      // Show success state
      const acceptedCount = 'accepted' in data ? data.accepted.length : 1;
      const rejectedCount =
        ('rejected' in data ? data.rejected.length : 0) +
        rejectedSelectedFiles.length;
      setUploadSuccess({
        label: uploadLabel,
        count: acceptedCount,
        rejected: rejectedCount,
      });

      // Clear selected files
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
      }

      // Refresh job list
      await fetchJobs({ showLoading: true, showErrors: true });

      // Clear success message after 4 seconds
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current);
      }
      successTimeoutRef.current = setTimeout(
        () => setUploadSuccess(null),
        4000
      );
    } catch (error) {
      console.error('Upload error:', error);
      if (error instanceof Error && error.message.startsWith('errors.')) {
        setUploadError(translateErrorMessage(error.message));
      } else {
        setUploadError(
          error instanceof Error ? error.message : 'Upload failed'
        );
      }
    } finally {
      setIsUploading(false);
    }
  };

  // Cancel file selection
  const handleCancelFile = () => {
    setSelectedFiles([]);
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (folderInputRef.current) {
      folderInputRef.current.value = '';
    }
  };

  const removeQueuedFile = (id: string) => {
    setSelectedFiles((current) =>
      buildQueueItems(
        current.filter((item) => item.id !== id).map((item) => item.file)
      )
    );
  };

  // Get status display info
  const getStatusDisplay = (status: JobStatus['status']) => {
    switch (status) {
      case 'pending':
        return {
          label: t('upload.status.queued'),
          color: 'text-text-muted',
          icon: <Clock className="w-3.5 h-3.5" />,
        };
      case 'processing':
        return {
          label: t('upload.status.processing'),
          color: 'text-warning',
          icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
        };
      case 'chunked':
        return {
          label: t('upload.status.chunked'),
          color: 'text-info',
          icon: <Layers className="w-3.5 h-3.5" />,
        };
      case 'completed':
        return {
          label: t('upload.status.complete'),
          color: 'text-success',
          icon: <CheckCircle2 className="w-3.5 h-3.5" />,
        };
      case 'completed_with_errors':
        return {
          label: t(
            'upload.status.completedWithErrors',
            'Completed with errors'
          ),
          color: 'text-warning',
          icon: <AlertTriangle className="w-3.5 h-3.5" />,
        };
      case 'failed':
        return {
          label: t('upload.status.failed'),
          color: 'text-error',
          icon: <AlertTriangle className="w-3.5 h-3.5" />,
        };
      default:
        return {
          label: status,
          color: 'text-text-muted',
          icon: <HelpCircle className="w-3.5 h-3.5" />,
        };
    }
  };

  const visibleRecentDocuments = recentJobs.slice(
    0,
    recentDocumentsVisibleLimit
  );
  const hasMoreRecentDocuments =
    visibleRecentDocuments.length < recentJobs.length;
  const shouldShowRecentDocumentsCount =
    recentJobs.length > RECENT_DOCUMENTS_INITIAL_LIMIT;
  const handleShowMoreRecentDocuments = async () => {
    if (isLoadingMoreDocumentsRef.current) return;

    const startIndex = recentDocumentsVisibleLimit;
    const nextLimit = Math.min(
      recentDocumentsVisibleLimit + RECENT_DOCUMENTS_BATCH_SIZE,
      recentJobs.length
    );
    if (nextLimit <= startIndex) return;

    isLoadingMoreDocumentsRef.current = true;
    setIsLoadingMoreDocuments(true);
    try {
      updateRecentDocumentsVisibleLimit(nextLimit);

      const documentsToHydrate = recentJobsRef.current.slice(
        startIndex,
        nextLimit
      );
      if (documentsToHydrate.length === 0) return;

      const hydratedDocuments = await Promise.all(
        documentsToHydrate.map(fetchDetailedJobStatus)
      );
      const hydratedById = new Map(
        hydratedDocuments.map((job) => [job.job_id, job])
      );
      const updatedJobs = recentJobsRef.current.map(
        (job) => hydratedById.get(job.job_id) ?? job
      );
      recentJobsRef.current = updatedJobs;
      setRecentJobs(updatedJobs);
    } finally {
      isLoadingMoreDocumentsRef.current = false;
      setIsLoadingMoreDocuments(false);
    }
  };

  // Close pipeline help modal
  const handleClosePipelineHelpModal = () => {
    setShowPipelineHelpModal(false);
    setPipelineHelpPage(0);
  };

  // Focus trap for pipeline help modal
  useEffect(() => {
    if (showPipelineHelpModal && pipelineHelpModalRef.current) {
      pipelineHelpModalRef.current.focus();
    }
  }, [showPipelineHelpModal]);

  // Pipeline help pages data
  const PIPELINE_HELP_PAGES = [
    {
      title: t('upload.pipelineHelp.formatsTitle', 'Supported Formats'),
      content: 'formats',
    },
    {
      title: t('upload.pipelineHelp.pipelineTitle', 'Processing Pipeline'),
      content: 'pipeline',
    },
    {
      title: t('upload.pipelineHelp.troubleshootingTitle', 'Troubleshooting'),
      content: 'troubleshooting',
    },
    {
      title: t('upload.pipelineHelp.tipsTitle', 'Best Practices'),
      content: 'tips',
    },
  ];

  const footer = (
    <Link to="/" className="text-text-muted hover:text-text transition-colors">
      {t('upload.backToDashboard')}
    </Link>
  );

  const content = (
    <div className="space-y-6">
      {/* File Upload Zone */}
      <div className="bg-surface-overlay border border-border rounded-xl p-5">
        <h3 className="text-sm font-semibold text-text mb-4 flex items-center gap-2">
          <Upload className="w-4 h-4 text-text-muted" />
          {t('upload.uploadFile')}
        </h3>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          onChange={handleInputChange}
          className="hidden"
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          onChange={handleInputChange}
          className="hidden"
        />

        {/* Drop zone, selected files, or success state */}
        {selectedFiles.length > 0 ? (
          <div className="border border-border bg-surface rounded-xl p-4 animate-fade-in">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                    isUploading ? 'bg-accent/10' : 'bg-surface-overlay'
                  }`}
                >
                  {isUploading ? (
                    <Loader2 className="w-5 h-5 text-accent animate-spin" />
                  ) : (
                    <FileText className="w-5 h-5 text-text-muted" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text truncate">
                    {t(
                      'upload.documentsSelected',
                      '{{count}} documents selected',
                      { count: selectedFiles.length }
                    )}
                  </p>
                  <p className="text-xs text-text-muted">
                    {isUploading
                      ? t('upload.uploadingStatus', 'Uploading to server...')
                      : t(
                          'upload.queueSummary',
                          '{{valid}} ready, {{rejected}} skipped',
                          {
                            valid: validSelectedFiles.length,
                            rejected: rejectedSelectedFiles.length,
                          }
                        )}
                  </p>
                </div>
              </div>

              {!isUploading && (
                <button
                  onClick={handleCancelFile}
                  className="p-1.5 text-text-muted hover:text-error transition-colors shrink-0"
                  title={t('upload.removeFile')}
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <div className="mt-4 max-h-56 overflow-y-auto space-y-2 pr-1">
              {selectedFiles.map((item) => {
                const isReady = item.status === 'ready';
                const isDuplicate = item.status === 'duplicate';
                return (
                  <div
                    key={item.id}
                    className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 ${
                      isReady ? 'bg-surface-overlay' : 'bg-warning/10'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText
                        className={`w-4 h-4 shrink-0 ${
                          isReady ? 'text-text-muted' : 'text-warning'
                        }`}
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-text truncate">
                          {item.displayName}
                        </p>
                        <p
                          className={`text-[11px] truncate ${
                            isReady ? 'text-text-muted' : 'text-warning'
                          }`}
                        >
                          {isReady
                            ? `${(item.file.size / 1024).toFixed(1)} KB`
                            : item.reason ||
                              (isDuplicate
                                ? t(
                                    'upload.duplicateInBatch',
                                    'Duplicate document name in this batch'
                                  )
                                : t('upload.skipped', 'Skipped'))}
                        </p>
                      </div>
                    </div>
                    {!isUploading && (
                      <button
                        onClick={() => removeQueuedFile(item.id)}
                        className="min-w-10 min-h-10 inline-flex items-center justify-center rounded-lg text-text-muted hover:text-error hover:bg-error/10 transition-colors"
                        title={t('upload.removeFile')}
                        aria-label={t('upload.removeFile')}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Upload progress indicator */}
            {isUploading && (
              <div className="mt-3 pt-3 border-t border-border">
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <div className="flex-1 h-1.5 bg-surface-overlay rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full animate-pulse"
                      style={{ width: '60%' }}
                    />
                  </div>
                  <span>{t('upload.uploading')}</span>
                </div>
              </div>
            )}
          </div>
        ) : uploadSuccess ? (
          <div className="border border-success/30 bg-success/5 rounded-xl p-4 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-5 h-5 text-success" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text truncate">
                  {uploadSuccess.label}
                </p>
                <p className="text-xs text-success">
                  {uploadSuccess.rejected > 0
                    ? t(
                        'upload.uploadedPartialSuccess',
                        '{{count}} queued, {{rejected}} skipped',
                        {
                          count: uploadSuccess.count,
                          rejected: uploadSuccess.rejected,
                        }
                      )
                    : t(
                        'upload.uploadedSuccess',
                        'Uploaded successfully — processing started'
                      )}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`
                border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
                ${
                  isDragging
                    ? 'border-accent bg-accent-subtle'
                    : 'border-border hover:border-accent/50 hover:bg-surface'
                }
              `}
          >
            <CloudUpload
              className={`w-10 h-10 mx-auto mb-3 transition-colors ${
                isDragging ? 'text-accent' : 'text-text-muted'
              }`}
              strokeWidth={1.5}
            />
            <p className="text-sm font-medium text-text mb-1">
              {isDragging ? t('upload.dropFileHere') : t('upload.dropOrBrowse')}
            </p>
            <p className="text-xs text-text-muted">
              {t('upload.supported', {
                extensions: getAllowedExtensionsDisplay(),
              })}
            </p>
            <div className="mt-4 flex flex-col sm:flex-row items-center justify-center gap-2">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  fileInputRef.current?.click();
                }}
                className="min-h-10 inline-flex items-center gap-2 rounded-lg bg-accent text-accent-text px-3 py-2 text-xs font-medium hover:bg-accent-hover active-press transition-colors"
              >
                <Files className="w-4 h-4" />
                {t('upload.chooseFiles', 'Choose files')}
              </button>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  folderInputRef.current?.click();
                }}
                className="min-h-10 inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-text hover:border-accent/50 active-press transition-colors"
              >
                <FolderOpen className="w-4 h-4" />
                {t('upload.chooseFolder', 'Choose folder')}
              </button>
            </div>
          </div>
        )}

        {/* Error message */}
        {uploadError && (
          <div className="mt-3 p-3 bg-error/10 border border-error/20 rounded-lg animate-fade-in">
            <p className="text-sm text-error">{uploadError}</p>
          </div>
        )}

        {/* Upload button */}
        {selectedFiles.length > 0 && (
          <button
            onClick={handleUpload}
            disabled={isUploading || validSelectedFiles.length === 0}
            className="w-full mt-4 bg-accent text-accent-text rounded-xl px-6 py-3 font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all active-press flex items-center justify-center gap-2"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('upload.uploading')}
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                {validSelectedFiles.length > 1
                  ? t('upload.uploadDocuments', 'Upload documents')
                  : t('upload.uploadDocument')}
              </>
            )}
          </button>
        )}
      </div>

      {/* Recent Uploads */}
      <div className="bg-surface-overlay border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <Clock className="w-4 h-4 text-text-muted" />
            {t('upload.recentUploads')}
            <button
              onClick={() => setShowPipelineHelpModal(true)}
              className="ml-1 text-text-muted hover:text-accent transition-colors"
              aria-label={t(
                'upload.pipelineHelp.ariaLabel',
                'Document processing help'
              )}
            >
              <HelpCircle className="w-5 h-5" />
            </button>
          </h3>
          <button
            onClick={() => {
              fetchJobs({ showLoading: true, showErrors: true });
            }}
            disabled={isLoadingJobs || isRefreshingJobs}
            aria-label={t('upload.refresh', 'Refresh')}
            className="text-xs text-text-muted hover:text-accent transition-colors disabled:opacity-50 flex items-center gap-1"
          >
            {isLoadingJobs || isRefreshingJobs ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <span>↻</span>
            )}
            {t('upload.refresh', 'Refresh')}
          </button>
        </div>

        {isLoadingJobs ? (
          <div className="text-center py-6">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-text-muted">{t('common.loading')}</p>
          </div>
        ) : jobsError ? (
          <div className="text-center py-6 bg-surface border border-border rounded-lg">
            <Clock
              className="w-8 h-8 text-text-muted mx-auto mb-2"
              strokeWidth={1.5}
            />
            <p className="text-sm text-text-secondary mb-1">
              {jobsErrorTitle || t('upload.serverBusy', 'Server is busy')}
            </p>
            <p className="text-xs text-text-muted mb-3">{jobsError}</p>
            <button
              onClick={() => {
                fetchJobs({ showLoading: true, showErrors: true });
              }}
              className="text-xs text-accent hover:text-accent-hover transition-colors"
            >
              {t('upload.tryRefresh', 'Try again')}
            </button>
          </div>
        ) : recentJobs.length > 0 ? (
          <div className="space-y-2">
            {jobsWarning && (
              <div className="px-3 py-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs">
                {jobsWarning}
              </div>
            )}
            {visibleRecentDocuments.map((job) => {
              const statusInfo = getStatusDisplay(job.status);
              const canDelete =
                job.status !== 'pending' && job.status !== 'processing';
              return (
                <div
                  key={job.job_id}
                  className="bg-surface border border-border rounded-lg p-3 animate-fade-in"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text truncate">
                        {job.filename}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span
                          className={`text-xs ${statusInfo.color} inline-flex items-center gap-1`}
                        >
                          {statusInfo.icon}
                          <span>{statusInfo.label}</span>
                        </span>
                        {job.replacement_for_filename && (
                          <span className="text-xs text-warning truncate">
                            {t(
                              'upload.replacingDocument',
                              'Replacing {{filename}}',
                              { filename: job.replacement_for_filename }
                            )}
                          </span>
                        )}
                        {job.total_chunks > 0 && (
                          <span className="text-xs text-text-muted">
                            {t('upload.chunks', {
                              processed: job.processed_chunks,
                              total: job.total_chunks,
                            })}
                          </span>
                        )}
                      </div>
                      {job.error && (
                        <p className="text-xs text-error mt-1 truncate">
                          {job.error}
                        </p>
                      )}
                    </div>
                    {/* Delete button */}
                    <button
                      onClick={() => openDeleteModal(job.job_id, job.filename)}
                      disabled={!canDelete}
                      className={`p-1.5 rounded-lg transition-colors shrink-0 ${
                        canDelete
                          ? 'text-text-muted hover:text-error hover:bg-error/10'
                          : 'text-text-muted/30 cursor-not-allowed'
                      }`}
                      title={
                        canDelete
                          ? t('upload.deleteDocument')
                          : t('upload.status.processing')
                      }
                      aria-label={
                        canDelete
                          ? t('upload.deleteDocument')
                          : t('upload.status.processing')
                      }
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
            {shouldShowRecentDocumentsCount && (
              <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-text-muted">
                  {t(
                    'upload.recentDocumentsShowing',
                    'Showing {{shown}} of {{total}} documents',
                    {
                      shown: visibleRecentDocuments.length,
                      total: recentJobs.length,
                    }
                  )}
                </p>
                {hasMoreRecentDocuments && (
                  <button
                    type="button"
                    onClick={handleShowMoreRecentDocuments}
                    disabled={isLoadingMoreDocuments}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-text transition-colors hover:border-accent/50 hover:text-accent active-press disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isLoadingMoreDocuments ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                    {t('upload.showMore', 'Show more')}
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-6 bg-surface border border-border border-dashed rounded-lg">
            <FileText
              className="w-8 h-8 text-text-muted mx-auto mb-2"
              strokeWidth={1.5}
            />
            <p className="text-xs text-text-muted">{t('upload.noUploads')}</p>
          </div>
        )}

        {/* TODO: Add UI for manual LLM extraction workflow (copy prompt, paste results) */}
        {/* The backend supports a manual extraction flow where users copy prompts to their LLM */}
        {/* and paste back the extracted entities/relationships. This UI is not yet implemented. */}
      </div>

      {/* Navigation */}
      {!embedded && (
        <div className="flex gap-3">
          <Link
            to="/admin/setup"
            className="flex-1 flex items-center justify-center gap-2 border border-border hover:border-accent/50 text-text rounded-xl px-4 py-3 text-sm font-medium transition-all hover:bg-surface"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('upload.backToSetup')}
          </Link>
        </div>
      )}

      {/* Pipeline Help Modal */}
      {showPipelineHelpModal && (
        <div
          ref={pipelineHelpModalRef}
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pipeline-help-modal-title"
          onKeyDown={(e) =>
            e.key === 'Escape' && handleClosePipelineHelpModal()
          }
          tabIndex={-1}
        >
          <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-lg mx-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3
                id="pipeline-help-modal-title"
                className="text-lg font-semibold text-text flex items-center gap-2"
              >
                <HelpCircle className="w-5 h-5" />
                {PIPELINE_HELP_PAGES[pipelineHelpPage].title}
              </h3>
              <button
                onClick={handleClosePipelineHelpModal}
                className="text-text-muted hover:text-text transition-colors"
                aria-label={t('common.close', 'Close')}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="min-h-[280px]">
              {PIPELINE_HELP_PAGES[pipelineHelpPage].content === 'formats' ? (
                <div className="space-y-3">
                  <p className="text-sm text-text-muted mb-4">
                    {t(
                      'upload.pipelineHelp.formatsDesc',
                      'Currently supported document formats for upload:'
                    )}
                  </p>
                  <div className="space-y-2">
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">.pdf</p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.pdfDesc',
                          'PDF documents. Text is extracted; images and scanned PDFs are not yet supported.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">.txt</p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.txtDesc',
                          'Plain text files. Best for simple, unformatted content.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">.md</p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.mdDesc',
                          'Markdown files. Formatting is preserved as plain text.'
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="bg-warning/10 border border-warning/20 rounded-lg p-3 mt-4">
                    <p className="text-xs text-warning">
                      {t(
                        'upload.pipelineHelp.notSupported',
                        'Not yet supported: .docx, .xlsx, images, scanned PDFs. Convert these to text or PDF first.'
                      )}
                    </p>
                  </div>
                </div>
              ) : PIPELINE_HELP_PAGES[pipelineHelpPage].content ===
                'pipeline' ? (
                <div className="space-y-3">
                  <p className="text-sm text-text-muted mb-4">
                    {t(
                      'upload.pipelineHelp.pipelineDesc',
                      'Documents go through these stages after upload:'
                    )}
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-start gap-3 bg-surface-overlay border border-border rounded-lg p-3">
                      <span className="text-text-muted">○</span>
                      <div>
                        <p className="text-sm font-medium text-text">
                          {t('upload.pipelineHelp.pending', 'Pending')}
                        </p>
                        <p className="text-xs text-text-muted mt-1">
                          {t(
                            'upload.pipelineHelp.pendingDesc',
                            'File uploaded, waiting in queue for processing.'
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 bg-surface-overlay border border-border rounded-lg p-3">
                      <span className="text-warning">◐</span>
                      <div>
                        <p className="text-sm font-medium text-text">
                          {t('upload.pipelineHelp.processing', 'Processing')}
                        </p>
                        <p className="text-xs text-text-muted mt-1">
                          {t(
                            'upload.pipelineHelp.processingDesc',
                            'Text is being extracted from the document.'
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 bg-surface-overlay border border-border rounded-lg p-3">
                      <span className="text-info">◑</span>
                      <div>
                        <p className="text-sm font-medium text-text">
                          {t('upload.pipelineHelp.chunked', 'Chunked')}
                        </p>
                        <p className="text-xs text-text-muted mt-1">
                          {t(
                            'upload.pipelineHelp.chunkedDesc',
                            'Document split into searchable chunks. Embeddings being generated.'
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 bg-surface-overlay border border-border rounded-lg p-3">
                      <span className="text-success">●</span>
                      <div>
                        <p className="text-sm font-medium text-text">
                          {t('upload.pipelineHelp.completed', 'Completed')}
                        </p>
                        <p className="text-xs text-text-muted mt-1">
                          {t(
                            'upload.pipelineHelp.completedDesc',
                            'Document is now searchable and available to the AI.'
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : PIPELINE_HELP_PAGES[pipelineHelpPage].content ===
                'troubleshooting' ? (
                <div className="space-y-3">
                  <p className="text-sm text-text-muted mb-4">
                    {t(
                      'upload.pipelineHelp.troubleshootingDesc',
                      'Common issues and how to resolve them:'
                    )}
                  </p>
                  <div className="space-y-2">
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-error">
                        {t(
                          'upload.pipelineHelp.stuckPending',
                          'Stuck on "Pending"'
                        )}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.stuckPendingFix',
                          'The processing queue may be full. Wait a few minutes or check if the backend service is running.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-error">
                        {t(
                          'upload.pipelineHelp.failedProcessing',
                          'Failed during processing'
                        )}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.failedProcessingFix',
                          'The document may be corrupted or password-protected. Try re-saving it or converting to a different format.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-error">
                        {t(
                          'upload.pipelineHelp.noChunks',
                          'Completed but no chunks'
                        )}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.noChunksFix',
                          'Document may be empty or contain only images. Ensure it has extractable text content.'
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-text-muted mb-4">
                    {t(
                      'upload.pipelineHelp.tipsDesc',
                      'For best results with your knowledge base:'
                    )}
                  </p>
                  <div className="space-y-2">
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">
                        {t('upload.pipelineHelp.tipLength', 'Document Length')}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.tipLengthDesc',
                          'Moderate-length documents (5-50 pages) work best. Very long documents may need to be split.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">
                        {t('upload.pipelineHelp.tipQuality', 'Content Quality')}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.tipQualityDesc',
                          'Well-structured documents with clear headings and paragraphs produce better search results.'
                        )}
                      </p>
                    </div>
                    <div className="bg-surface-overlay border border-border rounded-lg p-3">
                      <p className="text-sm font-medium text-text">
                        {t('upload.pipelineHelp.tipNaming', 'File Naming')}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {t(
                          'upload.pipelineHelp.tipNamingDesc',
                          'Use descriptive file names. They help identify documents in the admin interface.'
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <button
                onClick={() =>
                  setPipelineHelpPage((prev) => Math.max(0, prev - 1))
                }
                disabled={pipelineHelpPage === 0}
                className="flex items-center gap-1 text-sm text-text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                {t('common.previous', 'Previous')}
              </button>

              {/* Page indicators */}
              <div className="flex items-center gap-1.5">
                {PIPELINE_HELP_PAGES.map((_, index) => (
                  <button
                    key={index}
                    onClick={() => setPipelineHelpPage(index)}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      index === pipelineHelpPage
                        ? 'bg-accent'
                        : 'bg-border hover:bg-text-muted'
                    }`}
                    aria-label={`${t('common.goToPage', 'Go to page')} ${index + 1}`}
                  />
                ))}
              </div>

              <button
                onClick={() =>
                  setPipelineHelpPage((prev) =>
                    Math.min(PIPELINE_HELP_PAGES.length - 1, prev + 1)
                  )
                }
                disabled={pipelineHelpPage === PIPELINE_HELP_PAGES.length - 1}
                className="flex items-center gap-1 text-sm text-text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                {t('common.next', 'Next')}
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteJobId && (
        <div
          ref={deleteModalRef}
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
          onKeyDown={(e) => e.key === 'Escape' && closeDeleteModal()}
          tabIndex={-1}
        >
          <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-md mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-error/10 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-error" />
              </div>
              <div>
                <h3
                  id="delete-modal-title"
                  className="text-lg font-semibold text-text"
                >
                  {t('upload.confirmDelete')}
                </h3>
              </div>
            </div>

            <p className="text-sm text-text-muted mb-2">
              {t('upload.confirmDeleteDesc')}
            </p>

            <div className="bg-surface-overlay border border-border rounded-lg p-3 mb-4">
              <p className="text-sm font-medium text-text truncate">
                {deleteJobFilename}
              </p>
            </div>

            {/* Error message */}
            {deleteError && (
              <Callout
                label={t(
                  'upload.documentDeletionError',
                  'Document deletion error'
                )}
                tone="error"
                className="mb-4"
              >
                <p className="text-sm text-error">{deleteError}</p>
              </Callout>
            )}

            {/* Action buttons */}
            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={closeDeleteModal}
                disabled={isDeleting}
                className="flex-1"
              >
                {t('common.cancel')}
              </Button>
              <Button
                variant="danger"
                onClick={() => handleDeleteJob(deleteJobId)}
                disabled={isDeleting}
                className="flex-1"
                leadingIcon={
                  isDeleting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )
                }
              >
                {isDeleting ? t('upload.deleting') : t('common.delete')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <OnboardingCard
      size="xl"
      title={t('upload.title')}
      subtitle={t('upload.subtitle')}
      footer={footer}
    >
      {content}
    </OnboardingCard>
  );
}
