"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

type DemoState = { demo: boolean | null; setDemo: (value: boolean) => Promise<void>; error: string | null };

const DemoContext = createContext<DemoState>({ demo: null, setDemo: async () => {}, error: null });

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [demo, setValue] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ demo_mode: boolean }>("/settings")
      .then((s) => setValue(s.demo_mode))
      .catch((e) => setError(e.message));
  }, []);

  const setDemo = useCallback(async (next: boolean) => {
    try {
      const s = await api<{ demo_mode: boolean }>("/settings", {
        method: "PUT",
        body: JSON.stringify({ demo_mode: next }),
      });
      setValue(s.demo_mode);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  return <DemoContext.Provider value={{ demo, setDemo, error }}>{children}</DemoContext.Provider>;
}

export const useDemo = () => useContext(DemoContext);
