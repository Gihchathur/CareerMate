import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";

export type FloatingSelectOption = { value: string; label: string; description?: string; disabled?: boolean };

type Props = {
  value: string;
  options: FloatingSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
  searchable?: boolean;
};

type Geometry = { top: number; left: number; width: number; maxHeight: number; placement: "top" | "bottom" };

/** A searchable, keyboard-operable select whose menu is portalled to document.body.
 *  This keeps option lists clear of page overflow, drawers and the hover navigation rail. */
export function FloatingSelect({
  value,
  options,
  onChange,
  placeholder = "Choose an option…",
  ariaLabel,
  disabled = false,
  className = "",
  searchable,
}: Props) {
  const generatedId = useId();
  const listboxId = `cm-select-${generatedId.replace(/:/g, "")}`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [geometry, setGeometry] = useState<Geometry | null>(null);

  const selected = options.find((option) => option.value === value);
  const useSearch = searchable ?? options.length > 9;
  const filteredOptions = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return normalized
      ? options.filter((option) => `${option.label} ${option.description ?? ""}`.toLocaleLowerCase().includes(normalized))
      : options;
  }, [options, query]);

  const updateGeometry = () => {
    const anchor = triggerRef.current;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    const viewport = window.visualViewport;
    const viewportTop = viewport?.offsetTop ?? 0;
    const viewportLeft = viewport?.offsetLeft ?? 0;
    const viewportHeight = viewport?.height ?? window.innerHeight;
    const viewportWidth = viewport?.width ?? window.innerWidth;
    const viewportPadding = 12;
    const viewportBottom = viewportTop + viewportHeight - viewportPadding;
    const viewportRight = viewportLeft + viewportWidth - viewportPadding;
    const width = Math.min(Math.max(rect.width, 260), Math.min(560, viewportWidth - viewportPadding * 2));
    const left = Math.max(viewportLeft + viewportPadding, Math.min(rect.left, viewportRight - width));
    const desiredHeight = Math.min(360, 24 + filteredOptions.length * 44 + (useSearch ? 62 : 0));
    const below = Math.max(0, viewportBottom - rect.bottom - 8);
    const above = Math.max(0, rect.top - viewportTop - viewportPadding - 8);
    const preferredPlacement: Geometry["placement"] = below >= Math.min(desiredHeight, 230) || below >= above ? "bottom" : "top";
    const available = preferredPlacement === "bottom" ? below : above;
    const usableViewportHeight = Math.max(80, viewportHeight - viewportPadding * 2);
    const minimumMenuHeight = Math.min(120, usableViewportHeight);
    let placement = preferredPlacement;
    let maxHeight = Math.min(desiredHeight, Math.max(minimumMenuHeight, available));
    let top: number;

    // If neither side has enough room, float the menu within the visual viewport
    // and let its options scroll rather than allowing the menu to escape the screen.
    if (available < minimumMenuHeight) {
      placement = below >= above ? "bottom" : "top";
      maxHeight = Math.min(desiredHeight, usableViewportHeight);
      const preferredTop = placement === "bottom" ? rect.bottom + 8 : rect.top - maxHeight - 8;
      top = Math.max(viewportTop + viewportPadding, Math.min(preferredTop, viewportBottom - maxHeight));
    } else {
      top = placement === "bottom"
        ? rect.bottom + 8
        : rect.top - maxHeight - 8;
      top = Math.max(viewportTop + viewportPadding, Math.min(top, viewportBottom - maxHeight));
    }
    setGeometry({ top, left, width, maxHeight, placement });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updateGeometry();
    const onViewportChange = () => updateGeometry();
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    window.visualViewport?.addEventListener("resize", onViewportChange);
    window.visualViewport?.addEventListener("scroll", onViewportChange);
    const observer = typeof ResizeObserver !== "undefined" && triggerRef.current
      ? new ResizeObserver(onViewportChange)
      : null;
    if (observer && triggerRef.current) observer.observe(triggerRef.current);

    // The workspace rail animates its width on hover. Re-measure during that
    // short transition so the fixed menu follows its trigger instead of clipping.
    let animationFrame = 0;
    const started = performance.now();
    const trackTransition = () => {
      updateGeometry();
      if (performance.now() - started < 420) animationFrame = window.requestAnimationFrame(trackTransition);
    };
    animationFrame = window.requestAnimationFrame(trackTransition);

    return () => {
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
      window.visualViewport?.removeEventListener("resize", onViewportChange);
      window.visualViewport?.removeEventListener("scroll", onViewportChange);
      observer?.disconnect();
      window.cancelAnimationFrame(animationFrame);
    };
  }, [open, filteredOptions.length, useSearch]);

  useEffect(() => {
    if (!open) return;
    const selectedIndex = filteredOptions.findIndex((option) => option.value === value && !option.disabled);
    const firstEnabledIndex = filteredOptions.findIndex((option) => !option.disabled);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : Math.max(0, firstEnabledIndex));
  }, [open, value, filteredOptions]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) return;
      setOpen(false);
      setQuery("");
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        setQuery("");
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open || !searchRef.current) return;
    if (useSearch) searchRef.current.focus({ preventScroll: true });
  }, [open, useSearch]);

  useEffect(() => {
    if (!open) return;
    optionRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  const openMenu = (initialDirection: "first" | "last" = "first") => {
    if (disabled) return;
    setQuery("");
    const selectedIndex = options.findIndex((option) => option.value === value && !option.disabled);
    const enabledIndices = options.map((option, index) => option.disabled ? -1 : index).filter((index) => index >= 0);
    const fallbackIndex = initialDirection === "last" ? enabledIndices.at(-1) : enabledIndices[0];
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : fallbackIndex ?? 0);
    setOpen(true);
  };

  const choose = (option: FloatingSelectOption) => {
    if (option.disabled) return;
    onChange(option.value);
    setOpen(false);
    setQuery("");
    triggerRef.current?.focus();
  };

  const moveActive = (direction: 1 | -1) => {
    if (!filteredOptions.length) return;
    let index = activeIndex;
    for (let attempt = 0; attempt < filteredOptions.length; attempt += 1) {
      index = (index + direction + filteredOptions.length) % filteredOptions.length;
      if (!filteredOptions[index].disabled) break;
    }
    setActiveIndex(index);
  };

  const firstEnabledIndex = (items: FloatingSelectOption[]) => items.findIndex((option) => !option.disabled);
  const lastEnabledIndex = (items: FloatingSelectOption[]) => items.findLastIndex((option) => !option.disabled);

  const handleTriggerKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown") { event.preventDefault(); if (!open) openMenu("first"); else moveActive(1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); if (!open) openMenu("last"); else moveActive(-1); }
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!open) openMenu("first");
      else { const active = filteredOptions[activeIndex]; if (active) choose(active); else setOpen(false); }
    }
    else if (event.key === "Home" && open) { event.preventDefault(); setActiveIndex(Math.max(0, firstEnabledIndex(filteredOptions))); }
    else if (event.key === "End" && open) { event.preventDefault(); setActiveIndex(Math.max(0, lastEnabledIndex(filteredOptions))); }
  };

  const handlePopoverKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") { event.preventDefault(); moveActive(1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); moveActive(-1); }
    else if (event.key === "Home") { event.preventDefault(); setActiveIndex(Math.max(0, firstEnabledIndex(filteredOptions))); }
    else if (event.key === "End") { event.preventDefault(); setActiveIndex(Math.max(0, lastEnabledIndex(filteredOptions))); }
    else if (event.key === "Enter") {
      event.preventDefault();
      const active = filteredOptions[activeIndex];
      if (active) choose(active);
    }
  };

  const style: CSSProperties | undefined = geometry ? {
    position: "fixed",
    top: geometry.top,
    left: geometry.left,
    width: geometry.width,
    maxHeight: geometry.maxHeight,
    zIndex: 100000,
  } : undefined;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`cm-floating-select ${open ? "is-open" : ""} ${className}`.trim()}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        disabled={disabled}
        onClick={() => open ? setOpen(false) : openMenu("first")}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className={selected ? "cm-floating-select-value" : "cm-floating-select-placeholder"}>{selected?.label ?? placeholder}</span>
        <Icon name="chevron-down" className="cm-floating-select-chevron" />
      </button>
      {open && geometry && createPortal(
        <div
          ref={popoverRef}
          className={`cm-floating-select-popover placement-${geometry.placement}`}
          style={style}
          role="presentation"
          onKeyDown={handlePopoverKeyDown}
        >
          <div className="cm-floating-select-topline"><span>{ariaLabel}</span><kbd>ESC</kbd></div>
          {useSearch && <label className="cm-floating-select-search"><Icon name="search" /><input ref={searchRef} value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }} placeholder="Filter options…" aria-label={`Filter ${ariaLabel}`} /></label>}
          <div className="cm-floating-select-options" id={listboxId} role="listbox" aria-label={ariaLabel} tabIndex={-1}>
            {filteredOptions.length ? filteredOptions.map((option, index) => {
              const isSelected = option.value === value;
              const isActive = index === activeIndex;
              return (
                <button
                  ref={(node) => { optionRefs.current[index] = node; }}
                  key={`${option.value}-${index}`}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  disabled={option.disabled}
                  className={`cm-floating-select-option${isSelected ? " is-selected" : ""}${isActive ? " is-active" : ""}`}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => choose(option)}
                >
                  <span className="cm-floating-select-option-copy"><strong>{option.label || option.value}</strong>{option.description && <small>{option.description}</small>}</span>
                  <span className="cm-floating-select-option-check">{isSelected && <Icon name="check" />}</span>
                </button>
              );
            }) : <p className="cm-floating-select-empty">No matching options.</p>}
          </div>
          <div className="cm-floating-select-footer"><span>{filteredOptions.length} option{filteredOptions.length === 1 ? "" : "s"}</span><span>↑ ↓ navigate · ↵ select</span></div>
        </div>,
        document.body,
      )}
    </>
  );
}
