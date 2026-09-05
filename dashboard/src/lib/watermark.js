// Free-plan watermark notice dismissal, persisted for good.
// Lives here (not next to the modal) so files only export components.
const DISMISS_KEY = 'os_watermark_notice_dismissed';

export function watermarkNoticeDismissed() {
  try { return localStorage.getItem(DISMISS_KEY) === '1'; } catch { return false; }
}

export function dismissWatermarkNotice() {
  try { localStorage.setItem(DISMISS_KEY, '1'); } catch { /* ignore */ }
}
