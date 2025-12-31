import React, { useState } from 'react';
import { SearchMode } from '@/store/useZustandStore';
import { Select, SelectContent, SelectItem, SelectTrigger } from '../ui/custom-select';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react'; // Import both
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer';

const SEARCH_MODES = [
  { value: 'fast', title: 'Lite', subtitle: 'Rapid market response and action' },
  {
    value: 'agentic-planner',
    title: 'Core',
    subtitle: 'Strategic planning through agentic modeling',
  },
  { value: 'agentic-reasoning', title: 'Pro', subtitle: 'Deep reasoning and scenario simulation' },
  {
    value: 'deep-research',
    title: 'Research',
    subtitle: 'In-depth research of markets, trends, and assets',
  },
] as const;

const DropdownItem = ({
  title,
  subtitle,
  isActive,
}: {
  title: string;
  subtitle: string;
  isActive: boolean;
}) => (
  <div className="flex w-full flex-col justify-center items-start px-3 py-2 cursor-pointer">
    <p
      className={cn(
        'text-sm font-medium transition-colors',
        isActive ? 'text-[#4B9770]' : 'text-[#373737]',
      )}
    >
      {title}
    </p>
    <p
      className={cn(
        'text-xs font-normal transition-colors',
        isActive ? 'text-black font-medium' : 'text-gray-500',
      )}
    >
      {subtitle}
    </p>
  </div>
);

export const SettingsDropdown = ({
  value,
  onValueChange,
  disabled,
  isMobile,
}: {
  value: SearchMode;
  onValueChange: (value: SearchMode) => void;
  disabled?: boolean;
  isMobile?: boolean;
}) => {
  // We use this state for both Drawer and Select to determine which icon to show
  const [open, setOpen] = useState(false);
  const currentMode = SEARCH_MODES.find((m) => m.value === value) || SEARCH_MODES[0];

  const triggerClasses = cn(
    'flex h-10 w-auto items-center justify-between gap-2 px-2 transition-all outline-none',
    'bg-transparent border-none shadow-none ring-0 focus:ring-0 focus:ring-offset-0',
    'hover:bg-black/5 active:bg-black/10 transition-colors rounded-lg',
    'disabled:opacity-50 disabled:cursor-not-allowed',
  );

  // --- MOBILE VIEW ---
  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerTrigger asChild disabled={disabled}>
          <button className={cn(triggerClasses, open && 'bg-black/5')}>
            <span className="text-[13px] font-semibold text-[#373737]">{currentMode.title}</span>
            {/* Direct icon swap */}
            {open ? (
              <ChevronUp className="size-3.5 text-gray-500" />
            ) : (
              <ChevronDown className="size-3.5 text-gray-500" />
            )}
          </button>
        </DrawerTrigger>
        <DrawerContent className="bg-[var(--primary-main-bg)] px-4 pb-8 border-t">
          <DrawerHeader className="text-left px-3 pt-6">
            <DrawerTitle className="text-xs font-bold text-gray-400 uppercase tracking-widest">
              Select Search Mode
            </DrawerTitle>
          </DrawerHeader>
          <div className="flex flex-col gap-1 mt-2">
            {SEARCH_MODES.map((mode) => (
              <div
                key={mode.value}
                onClick={() => {
                  onValueChange(mode.value as SearchMode);
                  setOpen(false);
                }}
                className={cn(
                  'rounded-xl transition-all cursor-pointer',
                  value === mode.value ? 'bg-[rgba(127,178,157,0.16)]' : 'active:bg-gray-100',
                )}
              >
                <DropdownItem
                  title={mode.title}
                  subtitle={mode.subtitle}
                  isActive={value === mode.value}
                />
              </div>
            ))}
          </div>
        </DrawerContent>
      </Drawer>
    );
  }

  // --- DESKTOP VIEW ---
  return (
    <Select
      value={value}
      onValueChange={(val) => onValueChange(val as SearchMode)}
      onOpenChange={setOpen} // Update state when dropdown opens/closes
      disabled={disabled}
    >
      <div className="relative group">
        <SelectTrigger className={triggerClasses} aria-label="Select Model">
          <span className="text-[13px] font-semibold text-[#373737] truncate">
            {currentMode.title}
          </span>
          {/* Direct icon swap */}
          {open ? (
            <ChevronUp className="size-3.5 text-gray-500 shrink-0" />
          ) : (
            <ChevronDown className="size-3.5 text-gray-500 shrink-0" />
          )}
        </SelectTrigger>
        <div className="absolute z-50 hidden group-hover:block bg-black text-white text-[10px] font-medium px-2 py-1 rounded-md -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap shadow-lg">
          Search Settings
        </div>
      </div>

      <SelectContent className="p-2 m-0 border border-border/50 rounded-[0.75rem] shadow-[0px_10px_40px_0px_rgba(0,0,0,0.08)] bg-[var(--primary-main-bg)] min-w-[240px]">
        {SEARCH_MODES.map((mode) => (
          <SelectItem
            key={mode.value}
            value={mode.value}
            className={cn(
              'rounded-lg my-0.5 transition-colors focus:bg-[var(--primary-chart-bg)]',
              value === mode.value && 'bg-[rgba(127,178,157,0.12)]',
            )}
          >
            <DropdownItem
              title={mode.title}
              subtitle={mode.subtitle}
              isActive={value === mode.value}
            />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
