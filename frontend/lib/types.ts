export type ProcessingStatus = {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number; // 0.0 - 1.0
  sections_completed: number;
  sections_total: number;
  current_step?: string;
  error?: string;
};

export type Paper = {
  paper_id: string; // arXiv ID or DOI
  source?: string;  // "arxiv" | "biorxiv" | "medrxiv"
  title: string;
  authors: string[];
  abstract: string;
  pdf_url: string;
  html_url?: string;
  sections: Section[];
};

export type Section = {
  id: string;
  title: string;
  content: string;
  summary?: string;
  level: number;
  order_index: number;
  equations: string[];
  figures?: FigureReference[];
  tables?: TableReference[];
  video_url?: string;
};

export type FigureReference = {
  id?: string;
  caption?: string;
  page?: number | null;
};

export type TableReference = {
  id?: string;
  caption?: string;
  headers?: string[];
  rows?: string[][];
};

