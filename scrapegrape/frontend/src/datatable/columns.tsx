"use client"

import { createColumnHelper, type ColumnDef } from "@tanstack/react-table"
import { Link } from "@inertiajs/react"
import { PublisherSheet } from "@/components/PublisherSheet"

export type Permission = {
  notes: string
  activity: string
  permission: "explicitly_permitted" | "explicitly_prohibited" | "conditional_ambiguous"
}

export type Publisher = {
  id: number
  name: string
  domain: string
  url: string
  waf_detected: boolean
  waf_type: string
  tos_url: string
  tos_permissions: Permission[] | null
  robots_txt_found: boolean | null
  robots_txt_url_allowed: boolean | null
  sitemap_urls: string[]
  rss_urls: string[]
  rsl_detected: boolean | null
  fetch_strategy: string
  last_checked_at: string | null
}

const columnHelper = createColumnHelper<Publisher>()

function tosLabel(permissions: Permission[] | null) {
  if (!permissions || permissions.length === 0) {
    return "Unknown"
  }
  const prohibited = permissions.filter(p => p.permission === "explicitly_prohibited").length
  const permitted = permissions.filter(p => p.permission === "explicitly_permitted").length
  if (prohibited > 0) {
    return `${prohibited} prohibited`
  }
  if (permitted === permissions.length) {
    return `${permitted} permitted`
  }
  return `${permitted} ok / ${permissions.length - permitted} other`
}

export const columns: ColumnDef<Publisher, any>[] = [
  columnHelper.accessor("name", {
    header: "Publisher",
    cell: props => (
      <Link
        href={`/publishers/${props.row.original.id}`}
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        {props.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("domain", {
    header: "Domain",
  }),
  columnHelper.accessor("waf_detected", {
    header: "WAF",
    cell: props => {
      const detected = props.getValue()
      const type = props.row.original.waf_type
      return detected ? (type || "Detected") : "None"
    },
  }),
  columnHelper.display({
    id: "tos",
    header: "ToS",
    cell: ({ row }) => tosLabel(row.original.tos_permissions),
  }),
  columnHelper.display({
    id: "actions",
    header: "",
    cell: ({ row }) => <PublisherSheet publisher={row.original} />,
  }),
]
