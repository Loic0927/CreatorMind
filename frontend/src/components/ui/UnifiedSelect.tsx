"use client";

import { Key, useEffect, useId, useMemo, useRef, useState } from "react";
import { Button, Dialog, ListBox, ListBoxItem, Modal, ModalOverlay, Popover } from "react-aria-components";

export type SelectOption = { value: string; label: string; disabled?: boolean };

type UnifiedSelectProps = {
  label: string;
  helper?: string;
  options: readonly SelectOption[];
  value?: string;
  values?: readonly string[];
  onChange?: (value: string) => void;
  onValuesChange?: (values: string[]) => void;
  multiple?: boolean;
  max?: number;
  compact?: boolean;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  title?: string;
  otherOptionValue?: string;
  otherValue?: string;
  onOtherValueChange?: (value: string) => void;
  otherPlaceholder?: string;
};

const OPEN_EVENT = "postbridge:select-open";

export function UnifiedSelect({
  label, helper, options, value = "", values = [], onChange, onValuesChange,
  multiple = false, max, compact = false, placeholder = "Choose an option", disabled = false,
  error, title, otherOptionValue, otherValue = "", onOtherValueChange,
  otherPlaceholder = "Please specify",
}: UnifiedSelectProps) {
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [isSmall, setIsSmall] = useState(false);
  const [desktopPlacement, setDesktopPlacement] = useState<"bottom start" | "top start">("bottom start");
  const selected = useMemo(() => new Set(multiple ? values : options.some((option) => option.value === value) ? [value] : []), [multiple, options, value, values]);
  const selectedOptions = options.filter((option) => selected.has(option.value));
  const atMax = multiple && max != null && values.length >= max;
  const searchable = options.length > 8;
  const visibleOptions = searchable && search
    ? options.filter((option) => option.label.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
    : options;
  const showOther = Boolean(otherOptionValue && selected.has(otherOptionValue) && onOtherValueChange);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 639px)");
    const update = () => setIsSmall(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const closeOther = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== id) setOpen(false);
    };
    window.addEventListener(OPEN_EVENT, closeOther);
    return () => window.removeEventListener(OPEN_EVENT, closeOther);
  }, [id]);

  const changeOpen = (next: boolean) => {
    setOpen(next);
    if (next) {
      setSearch("");
      if (!isSmall && triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        const estimatedHeight = Math.min(280, options.length * 44 + (searchable ? 54 : 0) + 12);
        const spaceBelow = window.innerHeight - rect.bottom;
        setDesktopPlacement(spaceBelow < estimatedHeight && rect.top > spaceBelow ? "top start" : "bottom start");
      }
      window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }));
    } else {
      window.requestAnimationFrame(() => triggerRef.current?.focus());
    }
  };

  useEffect(() => {
    if (!open) return;
    const closeOnTab = (event: KeyboardEvent) => { if (event.key === "Tab") setOpen(false); };
    document.addEventListener("keydown", closeOnTab);
    return () => document.removeEventListener("keydown", closeOnTab);
  }, [open]);

  const updateSelection = (keys: "all" | Set<Key>) => {
    if (keys === "all") return;
    const next = Array.from(keys, String);
    if (multiple) {
      if (max != null && next.length > max) return;
      onValuesChange?.(options.filter((option) => next.includes(option.value)).map((option) => option.value));
    } else {
      const nextValue = next[0] ?? "";
      onChange?.(nextValue);
      changeOpen(false);
    }
  };

  const triggerText = selectedOptions[0]?.label;
  const panel = (
    <div className="unified-select-panel-inner">
      {isSmall ? <div className="unified-select-handle" aria-hidden="true" /> : null}
      {isSmall ? <h2 className="unified-select-sheet-title">{title || label}</h2> : null}
      {searchable ? (
        <input
          aria-label={`Search ${label}`}
          className="unified-select-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              listRef.current?.focus();
            }
          }}
          placeholder="Search options"
        />
      ) : null}
      <ListBox
        id={`${id}-listbox`}
        ref={listRef}
        aria-label={label}
        className="unified-select-list"
        selectionMode={multiple ? "multiple" : "single"}
        selectionBehavior="toggle"
        selectedKeys={selected}
        onSelectionChange={updateSelection}
        disallowEmptySelection={!multiple}
      >
        {visibleOptions.map((option) => {
          const maxDisabled = Boolean(atMax && !selected.has(option.value));
          return (
            <ListBoxItem
              id={option.value}
              key={option.value}
              textValue={option.label}
              isDisabled={option.disabled || maxDisabled}
              className="unified-select-option"
            >
              {({ isSelected }) => <>
                {multiple ? <span className={`unified-select-checkbox${isSelected ? " is-checked" : ""}`} aria-hidden="true"><CheckIcon /></span> : null}
                <span>{option.label}</span>
                {!multiple && isSelected ? <span className="unified-select-check" aria-hidden="true"><CheckIcon /></span> : null}
              </>}
            </ListBoxItem>
          );
        })}
      </ListBox>
      {multiple && max != null ? <div className="unified-select-footer" aria-live="polite">{values.length} of {max} selected</div> : null}
      {isSmall && multiple ? <button type="button" className="unified-select-done" onClick={() => changeOpen(false)}>Done</button> : null}
    </div>
  );

  return (
    <div className={`unified-select-field${compact ? " is-compact" : ""}${error ? " has-error" : ""}`}>
      {!compact ? <div className="unified-select-label-row"><span className="unified-select-label">{label}</span>{helper ? <span className="unified-select-helper">{helper}</span> : null}</div> : null}
      <Button
        ref={triggerRef}
        type="button"
        isDisabled={disabled}
        aria-label={compact ? label : `Choose ${label}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-listbox`}
        className="unified-select-trigger"
        onPress={() => changeOpen(!open)}
      >
        <span className={`unified-select-value${selectedOptions.length ? "" : " is-placeholder"}`}>
          {multiple && selectedOptions.length ? <span className="unified-select-chips">
            {selectedOptions.slice(0, 2).map((option) => <span className="unified-select-chip" key={option.value}>{option.label}</span>)}
            {selectedOptions.length > 2 ? <span className="unified-select-chip">+{selectedOptions.length - 2}</span> : null}
          </span> : compact && triggerText ? `${label}: ${triggerText}` : triggerText || placeholder}
        </span>
        <ChevronIcon />
      </Button>
      {isSmall ? (
        <ModalOverlay isOpen={open} onOpenChange={changeOpen} isDismissable className="unified-select-scrim">
          <Modal className="unified-select-sheet"><Dialog aria-label={title || label}>{panel}</Dialog></Modal>
        </ModalOverlay>
      ) : (
        <Popover
          triggerRef={triggerRef}
          isOpen={open}
          onOpenChange={changeOpen}
          placement={desktopPlacement}
          offset={6}
          shouldFlip
          isNonModal
          className="unified-select-popover"
        >{panel}</Popover>
      )}
      {showOther ? <input className="unified-select-other" aria-label={`${label} other value`} value={otherValue} onChange={(event) => onOtherValueChange?.(event.target.value)} placeholder={otherPlaceholder} /> : null}
      {error ? <span className="unified-select-error" role="alert">{error}</span> : null}
      {multiple ? <span className="sr-only" aria-live="polite">{values.length} selected</span> : null}
    </div>
  );
}

function ChevronIcon() {
  return <svg className="unified-select-chevron" aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="m3 6 5 5 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function CheckIcon() {
  return <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="m2.5 7 3 3 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
