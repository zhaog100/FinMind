import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { type SupportedLocale, detectUserLocale, setLocale as persistLocale } from '../lib/locale';

type LocaleContextType = {
  locale: SupportedLocale;
  setLocale: (l: SupportedLocale) => void;
};

const LocaleCtx = createContext<LocaleContextType>({ locale: 'en-IN', setLocale: () => {} });

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<SupportedLocale>('en-IN');

  useEffect(() => {
    setLocaleState(detectUserLocale());
  }, []);

  const setLocale = (l: SupportedLocale) => {
    setLocaleState(l);
    persistLocale(l);
  };

  return <LocaleCtx.Provider value={{ locale, setLocale }}>{children}</LocaleCtx.Provider>;
}

export function useLocale() {
  return useContext(LocaleCtx);
}
