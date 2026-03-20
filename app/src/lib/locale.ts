export type SupportedLocale = 'en-IN' | 'en-US' | 'en-GB' | 'ja-JP' | 'zh-CN' | 'de-DE' | 'fr-FR' | 'es-ES' | 'pt-BR';

export const SUPPORTED_LOCALES: { code: SupportedLocale; label: string; example: string }[] = [
  { code: 'en-IN', label: 'English (India)', example: '₹1,23,456.78 — 20-03-2026' },
  { code: 'en-US', label: 'English (US)', example: '$1,234,567.89 — 03/20/2026' },
  { code: 'en-GB', label: 'English (UK)', example: '£1,234,567.89 — 20/03/2026' },
  { code: 'ja-JP', label: 'Japanese', example: '¥1,234,568 — 2026/03/20' },
  { code: 'zh-CN', label: 'Chinese', example: '¥1,234,567.89 — 2026-03-20' },
  { code: 'de-DE', label: 'German', example: '1.234.567,89 € — 20.03.2026' },
  { code: 'fr-FR', label: 'French', example: '1 234 567,89 € — 20/03/2026' },
  { code: 'es-ES', label: 'Spanish', example: '€1.234.567,89 — 20/03/2026' },
  { code: 'pt-BR', label: 'Portuguese (BR)', example: 'R$1.234.567,89 — 20/03/2026' },
];

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥', CNY: '¥', BRL: 'R$', AUD: 'A$', CAD: 'C$',
};

export function formatLocaleDate(dateStr: string, locale: SupportedLocale = 'en-IN'): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    const fmt = locale.startsWith('ja') || locale.startsWith('zh') ? 'Asia/Tokyo' : undefined;
    return new Intl.DateTimeFormat(locale, { timeZone: fmt, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatLocaleCurrency(amount: number, currency: string = 'INR', locale: SupportedLocale = 'en-IN'): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency', currency,
      minimumFractionDigits: ['JPY'].includes(currency) ? 0 : 2,
    }).format(amount);
  } catch {
    return `${CURRENCY_SYMBOLS[currency] || currency}${amount.toFixed(2)}`;
  }
}

export function formatLocaleNumber(num: number, locale: SupportedLocale = 'en-IN', decimals: number = 2): string {
  return new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(num);
}

export function detectUserLocale(): SupportedLocale {
  const stored = localStorage.getItem('finmind-locale');
  if (stored && SUPPORTED_LOCALES.some(l => l.code === stored)) return stored as SupportedLocale;
  const nav = navigator.language;
  const match = SUPPORTED_LOCALES.find(l => nav.startsWith(l.split('-')[0]));
  return match?.code || 'en-IN';
}

export function setLocale(locale: SupportedLocale): void {
  localStorage.setItem('finmind-locale', locale);
}
