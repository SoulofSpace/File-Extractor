import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
    showDetails: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[FILE XTRACTOR ErrorBoundary] Uncaught render error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, showDetails: false });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 m-4 rounded-2xl bg-[#14151b] border border-red-500/20 text-center max-w-xl mx-auto shadow-2xl backdrop-blur-xl">
          <div className="p-3 rounded-2xl bg-red-500/10 border border-red-500/25 mb-4 text-red-400">
            <AlertTriangle className="w-8 h-8" />
          </div>

          <h3 className="text-base font-bold text-white mb-2">
            {this.props.fallbackTitle || 'Rendering Error Occurred'}
          </h3>

          <p className="text-xs text-zinc-400 mb-5 leading-relaxed">
            A component encountered an unexpected error while rendering. The application recovered safely.
          </p>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-colors shadow-lg"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Try Again</span>
            </button>

            <button
              type="button"
              onClick={() => this.setState((prev) => ({ showDetails: !prev.showDetails }))}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.05] border border-white/[0.08] text-xs text-zinc-300 hover:text-white hover:bg-white/10 transition-colors"
            >
              <span>Error Details</span>
              {this.state.showDetails ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
          </div>

          {this.state.showDetails && (
            <div className="w-full mt-4 p-4 rounded-xl bg-black/60 border border-white/10 text-left font-mono text-[11px] text-red-300 max-h-48 overflow-y-auto whitespace-pre-wrap select-text">
              <div className="font-bold text-red-400 mb-1">{this.state.error?.toString()}</div>
              <div className="text-zinc-500">{this.state.errorInfo?.componentStack}</div>
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
