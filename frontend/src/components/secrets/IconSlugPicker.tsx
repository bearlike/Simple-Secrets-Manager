import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode
} from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Palette, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  getCollectionIcons,
  getIconCollections,
  searchIcons
} from '../../lib/api/iconify';
import { queryKeys } from '../../lib/api/queryKeys';
import { AppIcon } from '../icons/AppIcon';

// Tiles per grid row; keep in sync with the w-[12.5%] tile width below.
const GRID_COLS = 8;
const ROW_HEIGHT_PX = 40;
const SEARCH_DEBOUNCE_MS = 250;
// Sentinel for the pack Select; never used as a real Iconify prefix.
const ALL_PACKS = 'all';

interface IconSlugPickerProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function IconSlugPicker({ id, value, onChange, placeholder }: IconSlugPickerProps) {
  const [open, setOpen] = useState(false);
  const [pack, setPack] = useState(ALL_PACKS);
  const [search, setSearch] = useState('');
  // Index into `items` steered by hover or arrow keys; DOM focus stays in the
  // search input (aria-activedescendant pattern), so virtualized tiles never
  // hold focus and can unmount freely while scrolling.
  const [highlight, setHighlight] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const query = useDebouncedValue(search, SEARCH_DEBOUNCE_MS).trim();

  const collectionsQuery = useQuery({
    queryKey: queryKeys.iconifyCollections(),
    queryFn: getIconCollections,
    enabled: open,
    staleTime: Infinity,
    retry: 1
  });

  const packQuery = useQuery({
    queryKey: queryKeys.iconifyCollection(pack),
    queryFn: () => getCollectionIcons(pack),
    enabled: open && pack !== ALL_PACKS,
    staleTime: Infinity,
    retry: 1
  });

  const searchQuery = useQuery({
    queryKey: queryKeys.iconifySearch(query, pack),
    queryFn: () => searchIcons(query, pack === ALL_PACKS ? undefined : pack),
    enabled: open && query.length > 0,
    staleTime: Infinity,
    retry: 1,
    placeholderData: keepPreviousData
  });

  const items = useMemo<string[]>(() => {
    if (query) {
      return searchQuery.data ?? [];
    }
    if (pack !== ALL_PACKS) {
      return (packQuery.data ?? []).map((name) => `${pack}:${name}`);
    }
    return [];
  }, [query, searchQuery.data, pack, packQuery.data]);

  const packNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const collection of collectionsQuery.data ?? []) {
      names.set(collection.prefix, collection.name);
    }
    return names;
  }, [collectionsQuery.data]);

  const rowVirtualizer = useVirtualizer({
    count: Math.ceil(items.length / GRID_COLS),
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 4
  });

  // New result set -> restart highlight/scroll at the top.
  useEffect(() => {
    setHighlight(0);
    scrollRef.current?.scrollTo({ top: 0 });
  }, [query, pack]);

  const resetPicker = () => {
    setPack(ALL_PACKS);
    setSearch('');
    setHighlight(0);
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) resetPicker();
  };

  const selectSlug = (slug: string) => {
    onChange(slug);
    handleOpenChange(false);
  };

  const moveHighlight = (delta: number) => {
    if (items.length === 0) return;
    const next = Math.min(items.length - 1, Math.max(0, highlight + delta));
    setHighlight(next);
    rowVirtualizer.scrollToIndex(Math.floor(next / GRID_COLS));
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        moveHighlight(GRID_COLS);
        break;
      case 'ArrowUp':
        event.preventDefault();
        moveHighlight(-GRID_COLS);
        break;
      // Left/Right move the grid highlight only with Alt held, so plain
      // arrows keep editing the query text without fighting the grid.
      case 'ArrowRight':
        if (event.altKey) {
          event.preventDefault();
          moveHighlight(1);
        }
        break;
      case 'ArrowLeft':
        if (event.altKey) {
          event.preventDefault();
          moveHighlight(-1);
        }
        break;
      case 'Enter': {
        // The popover is portalled outside the dialog form, but prevent
        // default anyway so Enter can never submit the surrounding form.
        event.preventDefault();
        const slug = items[highlight];
        if (slug) selectSlug(slug);
        break;
      }
      default:
        break;
    }
  };

  const highlighted: string | undefined = items[highlight];

  return (
    <div className="flex items-center gap-2">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-input">
        <AppIcon icon={value || undefined} className="h-4 w-4" />
      </div>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="font-mono"
        autoComplete="off"
      />
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Clear icon (auto-detect)"
          onClick={() => onChange('')}
        >
          <X className="h-4 w-4" />
        </Button>
      )}
      <Popover open={open} onOpenChange={handleOpenChange}>
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" size="sm" className="shrink-0">
            <Palette className="mr-2 h-4 w-4" />
            Browse
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[min(420px,calc(100vw-2rem))] p-0" align="end">
          <div className="flex items-center gap-2 border-b p-2">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={handleSearchKeyDown}
              placeholder="Search all icons…"
              className="h-9"
              autoComplete="off"
              role="combobox"
              aria-expanded="true"
              aria-controls="icon-picker-grid"
              aria-activedescendant={
                highlighted ? `icon-picker-option-${highlight}` : undefined
              }
            />
            <Select value={pack} onValueChange={setPack}>
              <SelectTrigger
                className="h-9 w-[140px] shrink-0"
                aria-label="Icon pack"
                disabled={collectionsQuery.isPending}
              >
                <SelectValue placeholder="All packs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_PACKS}>All packs</SelectItem>
                {(collectionsQuery.data ?? []).map((collection) => (
                  <SelectItem key={collection.prefix} value={collection.prefix}>
                    {collection.name} · {collection.total.toLocaleString()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div
            ref={scrollRef}
            id="icon-picker-grid"
            role="listbox"
            aria-label="Icon results"
            className="h-64 overflow-y-auto overscroll-contain p-1"
          >
            <GridStatus
              query={query}
              pack={pack}
              itemCount={items.length}
              loading={query ? searchQuery.isPending : packQuery.isPending}
              error={query ? searchQuery.isError : packQuery.isError}
            />
            <div
              className="relative w-full"
              style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
            >
              {rowVirtualizer.getVirtualItems().map((row) => (
                <div
                  key={row.key}
                  className="absolute inset-x-0 top-0 flex"
                  style={{
                    height: `${ROW_HEIGHT_PX}px`,
                    transform: `translateY(${row.start}px)`
                  }}
                >
                  {items
                    .slice(row.index * GRID_COLS, (row.index + 1) * GRID_COLS)
                    .map((slug, column) => {
                      const index = row.index * GRID_COLS + column;
                      return (
                        <button
                          key={slug}
                          id={`icon-picker-option-${index}`}
                          type="button"
                          role="option"
                          aria-selected={index === highlight}
                          aria-label={slug}
                          tabIndex={-1}
                          title={slug}
                          onMouseEnter={() => setHighlight(index)}
                          onClick={() => selectSlug(slug)}
                          className={cn(
                            'flex w-[12.5%] items-center justify-center rounded-md',
                            index === highlight && 'bg-accent text-accent-foreground'
                          )}
                        >
                          <AppIcon icon={slug} className="h-5 w-5" />
                        </button>
                      );
                    })}
                </div>
              ))}
            </div>
          </div>
          <div className="flex h-11 items-center gap-2 border-t px-3">
            {highlighted ? (
              <>
                <AppIcon icon={highlighted} className="h-5 w-5 shrink-0" />
                <span className="min-w-0 flex-1 truncate font-mono text-xs">
                  {highlighted}
                </span>
                <span className="max-w-[45%] shrink-0 truncate text-xs text-muted-foreground">
                  {packNames.get(highlighted.split(':')[0]) ?? ''}
                </span>
              </>
            ) : (
              <span className="text-xs text-muted-foreground">
                Type to search · ↑↓ to navigate · Enter to select
              </span>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

interface GridStatusProps {
  query: string;
  pack: string;
  itemCount: number;
  loading: boolean;
  error: boolean;
}

// Status copy rendered inside the grid viewport when there is nothing to
// paint; returns null the moment real results exist.
function GridStatus({ query, pack, itemCount, loading, error }: GridStatusProps) {
  if (itemCount > 0) return null;
  if (!query && pack === ALL_PACKS) {
    return <StatusRow>Search across 200,000+ icons, or pick a pack to browse.</StatusRow>;
  }
  if (error) {
    return (
      <StatusRow>
        Icon search unavailable — check connectivity. You can still type a slug manually.
      </StatusRow>
    );
  }
  if (loading) return <StatusRow>Loading icons…</StatusRow>;
  return <StatusRow>No matching icons.</StatusRow>;
}

function StatusRow({ children }: { children: ReactNode }) {
  return <p className="px-3 py-6 text-center text-sm text-muted-foreground">{children}</p>;
}
