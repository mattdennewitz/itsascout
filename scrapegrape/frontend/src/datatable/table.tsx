"use client"

import * as React from "react"
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  type SortingState,
  getFilteredRowModel,
  type ColumnFiltersState,
  getExpandedRowModel,
  type ExpandedState,
} from "@tanstack/react-table"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
}

export function DataTable<TData, TValue>({
  columns,
  data,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [expanded, setExpanded] = React.useState<ExpandedState>({})

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
    onExpandedChange: setExpanded,
    getExpandedRowModel: getExpandedRowModel(),
    getRowCanExpand: (row) => {
      const permissions = (row.original as any).terms_evaluation?.permissions;
      return permissions && permissions.length > 0;
    },
    state: {
      sorting,
      columnFilters,
      expanded,
    },
  })

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                return (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows?.length ? (
            table.getRowModel().rows.map((row) => (
              <React.Fragment key={row.id}>
                <TableRow data-state={row.getIsSelected() && "selected"}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
                {row.getIsExpanded() && (
                  <TableRow>
                    <TableCell colSpan={row.getVisibleCells().length} className="p-0">
                      <div className="p-4 bg-gray-50 max-w-full overflow-hidden expanded-details">
                        <div className="space-y-2">
                          <h4 className="font-semibold">Permissions:</h4>
                          <div className="max-h-96 overflow-y-auto">
                            {(row.original as any).terms_evaluation?.permissions?.map((permission: any, index: number) => (
                              <div key={index} className="border-l-4 border-blue-200 pl-3 py-2 mb-2">
                                <div className="font-medium break-words">{permission.activity}</div>
                                <div className={`px-2 py-1 rounded inline-block mt-1 ${
                                  permission.permission === 'explicitly_permitted' ? 'bg-green-100 text-green-800' :
                                  permission.permission === 'explicitly_prohibited' ? 'bg-red-100 text-red-800' :
                                  'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {(() => {
                                    switch (permission.permission) {
                                      case 'explicitly_permitted':
                                        return 'OK';
                                      case 'explicitly_prohibited':
                                        return 'Explicitly Forbidden';
                                      case 'conditional_ambiguous':
                                        return 'Conditionally';
                                      default:
                                        return permission.permission;
                                    }
                                  })()}
                                </div>
                                <div className="text-xs text-gray-600 mt-1 break-words">{permission.notes}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center">
                No results.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}