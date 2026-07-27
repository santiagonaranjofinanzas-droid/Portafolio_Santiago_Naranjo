'use client'
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import { ChevronUp, ChevronDown, Search } from 'lucide-react'

interface DataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[]
  data: TData[]
  searchKey?: string
}

export function DataTable<TData>({ columns, data, searchKey }: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')

  // TanStack Table intentionally returns non-memoizable callbacks.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  })

  return (
    <div>
      {searchKey && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <Search className="w-3.5 h-3.5" style={{ color: 'var(--text-ghost)' }} />
          <input
            type="text"
            placeholder="Search..."
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="bg-transparent text-sm outline-none placeholder:text-[var(--text-ghost)]"
            style={{ color: 'var(--text-secondary)' }}
          />
        </div>
      )}
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-left border-separate border-spacing-0">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="bg-white/[0.02]">
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="px-4 py-3 text-[10px] uppercase tracking-[0.15em] font-black text-slate-500 border-b border-white/5 cursor-pointer hover:text-white transition-colors"
                  >
                    <div className="flex items-center gap-1">
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === 'asc' && <ChevronUp className="w-3 h-3 text-blue-400" />}
                      {header.column.getIsSorted() === 'desc' && <ChevronDown className="w-3 h-3 text-blue-400" />}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-white/[0.03]">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="hover:bg-white/[0.02] transition-colors group"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-2 text-xs border-b border-white/[0.02]">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.getPageCount() > 1 && (
        <div className="flex items-center justify-between pt-3 px-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {table.getFilteredRowModel().rows.length} rows
          </span>
          <div className="flex items-center gap-2">
            <button className="btn btn-ghost text-xs" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Prev</button>
            <span className="text-xs font-data" style={{ color: 'var(--text-secondary)' }}>
              {table.getState().pagination.pageIndex + 1}/{table.getPageCount()}
            </span>
            <button className="btn btn-ghost text-xs" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default DataTable
