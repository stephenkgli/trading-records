import { useState, useRef, useEffect, useCallback } from "react";

type DropdownPortalResult = {
  open: boolean;
  setOpen: (value: boolean) => void;
  toggle: () => void;
  close: () => void;
  triggerRef: React.RefObject<HTMLButtonElement>;
  dropdownRef: React.RefObject<HTMLDivElement>;
  dropdownStyle: React.CSSProperties;
};

/**
 * Shared hook for portal-based dropdown menus.
 * Handles open/close state, positioning below the trigger button,
 * closing on outside click, and Escape key.
 */
export function useDropdownPortal(): DropdownPortalResult {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  // Position dropdown below trigger when opened, clamped to viewport.
  // Re-position on scroll/resize so the dropdown stays anchored.
  useEffect(() => {
    if (!open || !triggerRef.current) return;

    const position = () => {
      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      let top = rect.bottom + 4;
      let left = rect.left;

      // Clamp to viewport using dropdown's actual dimensions if available
      const dd = dropdownRef.current;
      if (dd) {
        const ddRect = dd.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // Clamp right edge
        if (left + ddRect.width > vw - 8) {
          left = vw - ddRect.width - 8;
        }
        // Clamp left edge
        if (left < 8) left = 8;
        // If dropdown would overflow bottom, show above trigger
        if (top + ddRect.height > vh - 8) {
          top = rect.top - ddRect.height - 4;
        }
      }

      setDropdownStyle({ top, left });
    };

    // Position immediately, then re-position once dropdown is rendered
    position();
    requestAnimationFrame(position);

    window.addEventListener("scroll", position, true);
    window.addEventListener("resize", position);
    return () => {
      window.removeEventListener("scroll", position, true);
      window.removeEventListener("resize", position);
    };
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent): void {
      const target = e.target as Node;
      if (
        triggerRef.current && !triggerRef.current.contains(target) &&
        dropdownRef.current && !dropdownRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  const toggle = useCallback(() => setOpen((prev) => !prev), []);
  const close = useCallback(() => setOpen(false), []);

  return { open, setOpen, toggle, close, triggerRef, dropdownRef, dropdownStyle };
}
