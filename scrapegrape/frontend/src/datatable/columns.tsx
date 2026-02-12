"use client"

import { createColumnHelper, type ColumnDef } from "@tanstack/react-table"

type ActivityPermission = {
  notes: string;
  activity: string;
  permission: "explicitly_permitted" | "explicitly_prohibited" | "conditional_ambiguous";
};

type WAFReport = {
  firewall: string;
  manufacturer: string;
  detected: boolean;
};

type TermsDiscovery = {
  terms_of_service_url: string;
};

type TermsEvaluation = {
  permissions: ActivityPermission[];
  territorial_exceptions: string | null;
  arbitration_clauses: string | null;
  document_type: string | null;
};

export type Publisher = {
  publisher: {
    id: number;
    name: string;
    url: string;
    detected_waf: string;
  };
  waf_report: WAFReport;
  terms_discovery: TermsDiscovery;
  terms_evaluation: TermsEvaluation;
}

const columnHelper = createColumnHelper<Publisher>()

export const columns: ColumnDef<Publisher, any>[] = [
  columnHelper.display({
    id: "expander",
    header: "",
    cell: ({ row }) => {
      const permissions = (row.original as any).terms_evaluation?.permissions;
      const hasPermissions = permissions && permissions.length > 0;
      
      if (!hasPermissions) {
        return null;
      }
      
      return (
        <button
          onClick={() => row.toggleExpanded()}
          className="p-1 hover:bg-gray-100 rounded"
        >
          {row.getIsExpanded() ? "−" : "+"}
        </button>
      )
    },
  }),
  columnHelper.accessor("publisher.name", {
    header: "Publisher",
    cell: props => {
      const value = props.cell.getValue();
      return <span><a target={"_blank"} href={props.row.original.publisher.url}>{value}</a></span>
    }
  }),
  columnHelper.accessor("publisher.detected_waf", {
    header: "WAF",
  }),
  columnHelper.accessor("terms_discovery.terms_of_service_url", {
    header: "Terms URL",
    cell: props => <a href={props.getValue()}>View Terms</a>
  }),
]