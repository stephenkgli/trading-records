import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAvailableAssetClasses } from "../api/client";

function loadSavedSelection(storageKey: string): string[] | null {
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    return null;
  } catch {
    return null;
  }
}

function saveSelection(storageKey: string, assetClasses: string[]): void {
  try {
    localStorage.setItem(storageKey, JSON.stringify(assetClasses));
  } catch {
    // ignore quota errors
  }
}

interface UseAssetClassFilterResult {
  availableAssetClasses: string[];
  selectedAssetClasses: string[] | null;
  setSelectedAssetClasses: (acs: string[]) => void;
  assetClassesParam: string[] | undefined;
  isInitialized: boolean;
}

export function useAssetClassFilter(storageKey: string): UseAssetClassFilterResult {
  const [selectedAssetClasses, setSelectedAssetClassesRaw] = useState<string[] | null>(null);
  const initializedRef = useRef(false);

  const { data: availableAssetClasses = [], isFetched: isAssetClassesFetched } = useQuery({
    queryKey: ["availableAssetClasses"],
    queryFn: fetchAvailableAssetClasses,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!isAssetClassesFetched || initializedRef.current) return;
    initializedRef.current = true;

    const saved = loadSavedSelection(storageKey);
    if (saved === null) {
      setSelectedAssetClassesRaw([...availableAssetClasses]);
    } else {
      const validSet = new Set(availableAssetClasses);
      const restored = saved.filter((ac) => validSet.has(ac));
      setSelectedAssetClassesRaw(restored);
    }
  }, [availableAssetClasses, isAssetClassesFetched, storageKey]);

  useEffect(() => {
    if (selectedAssetClasses === null) return;
    saveSelection(storageKey, selectedAssetClasses);
  }, [selectedAssetClasses, storageKey]);

  const setSelectedAssetClasses = useCallback((acs: string[]) => {
    setSelectedAssetClassesRaw(acs);
  }, []);

  const assetClassesParam =
    selectedAssetClasses === null ? undefined : selectedAssetClasses;

  return {
    availableAssetClasses,
    selectedAssetClasses,
    setSelectedAssetClasses,
    assetClassesParam,
    isInitialized: selectedAssetClasses !== null,
  };
}
