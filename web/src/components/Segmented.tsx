import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface Props<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}

/**
 * Segmented is a single-choice switch (dataset, source, filter) that never deselects.
 * On a narrow screen it scrolls inside its own box rather than widening the page.
 */
export function Segmented<T extends string>({ label, value, options, onChange }: Props<T>) {
  return (
    <div className="max-w-full overflow-x-auto">
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        aria-label={label}
        value={value}
        onValueChange={(next) => {
          const found = options.find((o) => o.value === next);
          if (found) onChange(found.value);
        }}
      >
        {options.map((o) => (
          <ToggleGroupItem key={o.value} value={o.value} className="px-3">
            {o.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
