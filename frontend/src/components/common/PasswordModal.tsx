import React, { useState } from 'react';
import { FigmaIcon } from './FigmaIcon';
import { apiClient } from '../../api/client';

interface PasswordModalProps {
  isOpen: boolean;
  mode?: 'verify' | 'setup' | 'recover';
  onClose: () => void;
  onSuccess: (token: string) => void;
  title?: string;
  subtitle?: string;
}

export const PasswordModal: React.FC<PasswordModalProps> = ({
  isOpen,
  mode = 'verify',
  onClose,
  onSuccess,
  title,
  subtitle,
}) => {
  const [currentMode, setCurrentMode] = useState<'verify' | 'setup' | 'recover'>(mode);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [generatedKey, setGeneratedKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (currentMode === 'setup') {
        if (password.length < 4) {
          setError('Password must be at least 4 characters long.');
          setLoading(false);
          return;
        }
        if (password !== confirmPassword) {
          setError('Passwords do not match.');
          setLoading(false);
          return;
        }
        const res = await apiClient.setupPrivacy(password);
        setGeneratedKey(res.recovery_key);
        onSuccess(res.token);
      } else if (currentMode === 'recover') {
        if (!recoveryKey.trim()) {
          setError('Please enter your recovery key.');
          setLoading(false);
          return;
        }
        if (password.length < 4) {
          setError('New password must be at least 4 characters long.');
          setLoading(false);
          return;
        }
        const res = await apiClient.recoverPrivacy(recoveryKey, password);
        onSuccess(res.token);
        onClose();
      } else {
        // verify mode
        const res = await apiClient.verifyPrivacy(password);
        onSuccess(res.token);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl p-6 relative overflow-hidden">
        {/* Glow accent */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-1 bg-gradient-to-r from-transparent via-emerald-500 to-transparent" />

        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <FigmaIcon name="lock" size={20} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                {title || (currentMode === 'setup' ? 'Set Privacy Password' : currentMode === 'recover' ? 'Reset Password' : 'Enter Privacy Password')}
              </h3>
              <p className="text-xs text-zinc-400">
                {subtitle || (currentMode === 'setup' ? 'Create a master password for protected files' : currentMode === 'recover' ? 'Use your emergency recovery key' : 'Unlock protected files and private mode')}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-500 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
          >
            <FigmaIcon name="close" size={16} />
          </button>
        </div>

        {generatedKey ? (
          <div className="py-3 space-y-4">
            <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
              <p className="text-xs font-medium text-emerald-300 mb-1">Save Your Recovery Key</p>
              <p className="text-[11px] text-zinc-300 mb-2">
                If you ever forget your password, this recovery key is the ONLY way to regain access. Write it down or save it securely.
              </p>
              <div className="p-2.5 bg-black/50 border border-emerald-500/30 rounded-lg text-center font-mono text-sm font-bold tracking-wider text-emerald-400 select-all">
                {generatedKey}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="w-full py-2.5 bg-white text-zinc-950 font-medium text-xs rounded-xl hover:bg-zinc-200 transition-colors"
            >
              I Have Saved My Recovery Key
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-400 flex items-center gap-2">
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            {currentMode === 'recover' && (
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Emergency Recovery Key</label>
                <input
                  type="text"
                  value={recoveryKey}
                  onChange={(e) => setRecoveryKey(e.target.value)}
                  placeholder="XXXX-XXXX-XXXX-XXXX"
                  className="w-full px-3.5 py-2.5 bg-black/40 border border-white/10 rounded-xl text-white placeholder-zinc-600 font-mono text-xs focus:outline-none focus:border-emerald-500 transition-colors uppercase"
                  autoFocus
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                {currentMode === 'recover' ? 'New Password' : 'Password'}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password..."
                className="w-full px-3.5 py-2.5 bg-black/40 border border-white/10 rounded-xl text-white placeholder-zinc-600 text-xs focus:outline-none focus:border-emerald-500 transition-colors"
                autoFocus={currentMode !== 'recover'}
              />
            </div>

            {currentMode === 'setup' && (
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat password..."
                  className="w-full px-3.5 py-2.5 bg-black/40 border border-white/10 rounded-xl text-white placeholder-zinc-600 text-xs focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              {currentMode === 'verify' ? (
                <button
                  type="button"
                  onClick={() => {
                    setCurrentMode('recover');
                    setError('');
                  }}
                  className="text-[11px] text-zinc-500 hover:text-emerald-400 transition-colors"
                >
                  Forgot password?
                </button>
              ) : currentMode === 'recover' ? (
                <button
                  type="button"
                  onClick={() => {
                    setCurrentMode('verify');
                    setError('');
                  }}
                  className="text-[11px] text-zinc-500 hover:text-white transition-colors"
                >
                  Back to login
                </button>
              ) : (
                <div />
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 text-xs font-medium text-zinc-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-xl shadow-lg shadow-emerald-950/40 transition-all disabled:opacity-50"
                >
                  {loading ? 'Processing...' : currentMode === 'setup' ? 'Set Password' : currentMode === 'recover' ? 'Reset Password' : 'Unlock'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
